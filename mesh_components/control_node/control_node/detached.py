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
import base64
import json
import logging
import os
import secrets
import subprocess
import tempfile
import time

from signal import SIGINT

import requests

# TODO: update to 2020 validator
from jsonschema import Draft7Validator

from .certificate_authority import CertificateAuthority, export_key_cert_bundle
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

    def __init__(self, configuration,
                 ca_root: CertificateAuthority = None) -> None:
        """
        Initialize a Detached Instance runner with a specified configuration.

        Args:
            configuration (dict): configuration per schema
            ca_root (CertificateAuthority): common CA for issuing server and
                                            client TLS certificates
        """
        # global configuration
        self._logger = logging.getLogger('mesh-control')

        if not _VALIDATOR.is_valid(configuration):
            raise ValidationError(_VALIDATOR.iter_errors(configuration))

        self._conf = configuration

        # configuration directories created for components
        self._conf_dirs = {}

        # spawned processes
        self._processes = {}

        # CA for certificates
        if not ca_root:
            self._ca = CertificateAuthority.create_self_signed()
        else:
            self._ca = ca_root

        # we need own certificates for the probe
        key, crt = self._ca.create_component_client_certificate('probe')

        # We want the temporary directory to be available
        # for the whole duration of DetachedInstance
        # pylint:disable=consider-using-with
        self._tmp_dir = tempfile.TemporaryDirectory()
        key_path, crt_path, ca_path = self._ca.export_key_cert_to_directory(
            self._tmp_dir.name, key, crt)

        self._session = requests.Session()
        self._session.cert = (crt_path, key_path)
        self._session.verify = ca_path
    # __init__()

    def __enter__(self):
        """Scope enter"""
        return self
    # __enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        """Scope exit"""
        self.cleanup()
    # __exit__()

    def _get_component_url(self, component_name) -> str:
        """
        Get component server url
        """
        if component_name in self._conf:
            if 'listen' in self._conf[component_name]:
                listen = (self._conf[component_name]['listen'],
                          self._conf[component_name]['port'])
                return f"https://{listen[0]}:{listen[1]}"
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
        conf_dir = self._conf_dirs[component_name].name

        listen = (self._conf[component_name]['listen'],
                  self._conf[component_name]['port'])

        # create certificates for the server
        key_crt_tuple = self._ca.create_component_server_certificate(
            component_name, listen[0])

        key_path, crt_path, ca_path = self._ca.export_key_cert_to_directory(
            conf_dir, *key_crt_tuple)

        uwsgi_fifo = os.path.join(conf_dir, 'fifo')

        args = [
            '--https',
            f'{listen[0]}:{listen[1]},{crt_path},{key_path},HIGH,!{ca_path}',
            '--mount', f'/={self._conf[component_name]["api_app"]}',
            '-M', '--master-fifo', uwsgi_fifo
        ]
        self._logger.info('Starting uwsgi with args %s', args)
        with open(f'.{component_name}.log', 'w', encoding='utf-8') as logfile:
            return subprocess.Popen(
                ['uwsgi', *args],
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
                resp = self._session.get(f"{target}/").json()
                if resp['name'] != component_name:
                    raise ComponentProbeError(
                        f'Probe failed: {str(resp)}')
                break
            except requests.ConnectionError as exc:
                # component is not yet up
                if time.monotonic() < probe_start_time + timeout:
                    time.sleep(0.5)
                else:
                    raise ComponentProbeError("Probe failed: no connection") \
                        from exc
            except requests.HTTPError as err:
                raise ComponentProbeError(f"Probe failed: {err.response}") \
                    from err
            except RuntimeError as err:
                raise ComponentProbeError(
                    f"Probe failed: wrong response {str(err)}") from None
    # _validate_component_response()

    @property
    def ca_root(self):
        """Return our certificate authority"""
        return self._ca
    # ca_root()

    def setup(self) -> None:
        """
        Create configuration files for components, check prerequisites etc.
        """
        for component in COMPONENT_LIST:
            if (component in self._conf
                    and 'configuration' in self._conf[component]):
                # create client certificate
                key, crt = self._ca.create_component_client_certificate(
                    component)
                export_phrase = secrets.token_urlsafe()
                pkcs = export_key_cert_bundle(
                    key, crt, self._ca.root, export_phrase)

                component_configuration = self._conf[component].get(
                    'configuration', {})
                component_configuration['request_authorization'] = {
                    'pkcs12-bundle': {
                        'type': 'base85',
                        'value': base64.b85encode(pkcs).decode('utf-8')
                    },
                    'import-key': {
                        'type': 'raw',
                        'value': export_phrase
                    }
                }

                # component configuration defined, enable it
                conf_dir = tempfile.TemporaryDirectory(prefix=f'{component}.')
                self._conf_dirs[component] = conf_dir
                conf_name = os.path.join(conf_dir.name, f'{component}.conf')
                with open(conf_name, 'w', encoding='utf-8') as conf_file:
                    json.dump(component_configuration, conf_file)
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
            proc.send_signal(SIGINT)
        self._processes = {}
    # stop()

    def cleanup(self) -> None:
        """
        Stop processes and remove configuration files from setup phase
        """
        self.stop()

        for directory in self._conf_dirs.values():
            try:
                directory.cleanup()
            except FileNotFoundError:
                pass
        self._conf_dirs = {}
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
