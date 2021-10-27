# Copyright 2021 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
===============================
Detached Tessia instance runner
===============================

Create, start and stop a tessia mesh instance in detached mode.

Detached mode is temporary in nature: the runner spawns instances of Flask for
every local component in configuration, and stops them after instance object
gets out of scope (see usage). As a result, this mode is useful for
non-persisting setups, such as testing new components or one-time partial
deployments.

Usage
-----

Recommended approach is to use "with" statement::

    with DetachedInstance(configuration) as instance:
        instance.setup()
        instance.run()
        ...

Components that were started will stop upon exit. Without "with" scoping
the processes will be left running, but can be stopped through ``.stop()`` and
``.cleanup()`` methods.
"""

#
# IMPORTS
#
import json
import logging
import os
import subprocess
import time

import requests

# TODO: update to 2020 validator
from jsonschema import Draft7Validator

from .errors import StartInstanceError, ComponentProbeError, ValidationError

#
# CONSTANTS AND DEFINITIONS
#

# Wait at most COMPONENT_START_TIMEOUT seconds for component to start responding
COMPONENT_START_TIMEOUT = 10.0

# Component list
COMPONENT_LIST = ('control_node', 'permission_manager',
                  'resource_manager', 'scheduler')

SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object',
    'title': 'Detached instance configuration',
    '$defs': {
        'local_component': {
            'type': 'object',
            'properties': {
                'listen': {'type': 'string'},
                'port': {'type': 'integer'},
                'configuration': {
                    'type': 'object',
                    'additionalProperties': True
                }
            },
            'required': ['listen', 'port'],
            'additionalProperties': True
        }
    },
    'properties': {
        component: {
            '$ref': '#/$defs/local_component'
        } for component in COMPONENT_LIST
    },
    'additionalProperties': True
}

#
# CODE
#


# Schema validator
_VALIDATOR = Draft7Validator(SCHEMA)


class DetachedInstance:
    """Detached tessia instance"""

    def __init__(self, configuration) -> None:
        # global configuration
        self._logger = logging.getLogger('mesh-control')

        if not _VALIDATOR.is_valid(configuration):
            raise ValidationError(_VALIDATOR.iter_errors(configuration))

        self._conf = configuration

        # configuration files created for components
        self._conf_files = {}

        # spawned processes
        self._processes = {}
    # __init__()

    def __enter__(self):
        """Scope enter"""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Scope exit"""
        self.cleanup()

    def _get_component_url(self, component_name) -> str:
        """
        Get component server url
        """
        if component_name in self._conf:
            if 'listen' in self._conf[component_name]:
                listen = (self._conf[component_name]['listen'],
                          self._conf[component_name]['port'])
                return f"http://{listen[0]}:{listen[1]}"

            if 'remote' in self._conf[component_name]:
                return self._conf[component_name]['remote']
        return ''
    # _get_component_url()

    def _start_local_component(self, component_name):
        """
        Start a local component

        Args:
            component_name (str): standard component name
            listen (tuple): bind address and port
            config_path (str): path to component configuration file

        Returns:
            Popen: process object
        """
        env = os.environ.copy()
        env['FLASK_APP'] = f'{component_name}.api'
        if component_name in self._conf_files:
            env[f"{component_name}_CONF".upper()] = \
                self._conf_files[component_name]

        listen = (self._conf[component_name]['listen'],
                  self._conf[component_name]['port'])

        # use different log files for different instances
        with open(f'.{component_name}.log',
                  'w', encoding='utf-8') as logfile:
            return subprocess.Popen(
                ['flask', 'run',
                 '--host', str(listen[0]),
                 '--port', str(listen[1])],
                env=env, stdout=logfile, stderr=subprocess.STDOUT)
    # _start_local_component()

    def _validate_component_response(self, component_name, timeout=0.) -> None:
        """
        Validate that component response is as expected
        """
        target = self._get_component_url(component_name)
        probe_start_time = time.monotonic()
        while True:
            try:
                resp = requests.get(f"{target}/").json()
                if resp['name'] != component_name:
                    raise ComponentProbeError(
                        f'Probe failed: {str(resp)}')
                break
            except requests.ConnectionError:
                # component is not yet up
                if time.monotonic() < probe_start_time + timeout:
                    time.sleep(0.5)
                else:
                    raise ComponentProbeError("Probe failed: no connection") \
                        from None
            except requests.HTTPError as err:
                raise ComponentProbeError(f"Probe failed: {err.response}") \
                    from err
            except RuntimeError as err:
                raise ComponentProbeError(
                    f"Probe failed: wrong response {str(err)}") from None
    # _validate_component_response()

    def setup(self) -> None:
        """
        Create configuration files for components, check prerequisites etc.
        """
        work_dir = os.getcwd()
        for component in COMPONENT_LIST:
            if (component in self._conf
                    and 'configuration' in self._conf[component]):
                # component configuration defined, enable it
                conf_name = os.path.join(work_dir, f'tessia_{component}.conf')
                with open(conf_name, 'w', encoding='utf-8') as conf_file:
                    json.dump(self._conf[component].get('configuration', {}),
                              conf_file)
                self._conf_files[component] = conf_name
    # setup()

    def run(self) -> None:
        """
        Start all local components

        Raises:
            StartInstanceError: not all components could be started
        """
        enabled_components = [component for component in COMPONENT_LIST
                              if component in self._conf]
        self._logger.info("Starting components locally: %s",
                          enabled_components)
        for component in enabled_components:
            if component in self._conf and 'listen' in self._conf[component]:
                proc = self._start_local_component(component)

                if not proc:
                    # process not created - abort
                    self._logger.error(
                        "Could not start component %s", component)
                    raise StartInstanceError(
                        f'Component {component} could not be started')

                # process started, probe for status
                self._processes[component] = proc

                self._logger.info("Probing %s", component)
                try:
                    self._validate_component_response(
                        component, COMPONENT_START_TIMEOUT)
                except ComponentProbeError as exc:
                    raise StartInstanceError from exc
    # run()

    def stop(self) -> None:
        """
        Stop all local processes
        """
        for proc in self._processes.values():
            proc.terminate()
        self._processes = {}
    # stop()

    def cleanup(self) -> None:
        """
        Stop processes and remove configuration files from setup phase
        """
        self.stop()

        for filename in self._conf_files.values():
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass
        self._conf_files = {}
    # cleanup()

    def verify(self) -> dict:
        """
        Verify that current configuration is active

        Returns:
            dict: probe results per component (true/false)
        """
        result = {component: False for component in COMPONENT_LIST
                  if component in self._conf}
        for component in result.keys():
            try:
                self._validate_component_response(component)
                result[component] = True
            except ComponentProbeError:
                # probe failed - component inactive
                pass

            # verify that process, if started, is still active
            if component in self._processes:
                retcode = self._processes[component].poll()
                if retcode is not None:
                    self._logger.info("Component %s terminated (return code %d)",
                                      component, retcode)
                    result[component] = False

        return result
    # verify()

# DetachedInstance
