# Copyright 2016, 2017 IBM Corp.
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
State machine that performs the installation of Linux Distros.
"""

#
# IMPORTS
#
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from tessia_engine.config import CONF
from tessia_engine.db.connection import MANAGER
from tessia_engine.db.models import OperatingSystem
from tessia_engine.db.models import Template
from tessia_engine.db.models import System, SystemProfile
from tessia_engine.state_machines.base import BaseMachine
from tessia_engine.state_machines.autoinstall.sm_anaconda import SmAnaconda
from tessia_engine.state_machines.autoinstall.sm_autoyast import SmAutoyast
from tessia_engine.state_machines.autoinstall.sm_debian import SmDebianInstaller

import json
import logging

#
# CONSTANTS AND DEFINITIONS
#
MACHINE_DESCRIPTION = 'Auto installation of OS {}'

# Schema for the installation request
INSTALL_REQ_PARAMS_SCHEMA = {
    "type": "object",
    "properties": {
        "os": {"type": "string"},
        "profile": {"type": "string"},
        "template": {"type": "string"},
        "system": {"type": "string"}
    },
    "required": [
        "template",
        "system"
    ],
    "additionalProperties": False
}

SUPPORTED_DISTROS = {
    'rhel': SmAnaconda,
    'sles': SmAutoyast,
    'ubuntu': SmDebianInstaller
}

#
# CODE
#
class AutoInstallMachine(BaseMachine):
    """
    Facade to represent the auto install state machine, in fact acts as a proxy
    to the real machine since at instantiation time we don't know which distro
    is being installed and thus can't determine the right class to use.
    """
    def __init__(self, params):
        """
        See base class docstring.

        Args:
            params (str): A string containing a json in the format:
            {
                "template": "<name of the template>",
                "os": "<name of the operating system>",
                "profile": "<system_name>[/<name of the profile>]"
            }
        """
        super(AutoInstallMachine, self).__init__(params)

        # Create the first connection
        MANAGER.connect()

        CONF.log_config()
        self._logger = logging.getLogger(__name__)
        # The content of the request is validated in the parse method.
        # so it is not checked here.
        self._params = json.loads(params)

        self._machine = self._create_machine()
    # __init__()

    def _create_machine(self):
        """
        Create the correct state machine based on the operating system being
        installed.
        """
        # get template entry in db
        template_entry = self._get_template(self._params['template'])
        # get the os entry in db
        os_entry = self._get_os(template_entry, self._params.get('os'))
        # get the profile entry in db
        prof_entry = self._get_profile(
            self._params['system'], self._params.get("profile"))

        if os_entry != template_entry.operating_system_rel:
            self._logger.warning('warning: custom OS specified by user,'
                                 ' template might not work properly.'
                                 ' Use at your own RISK!')

        try:
            sm_class = SUPPORTED_DISTROS[os_entry.type]
        except KeyError:
            msg = 'OS {} is not supported by this install machine'.format(
                os_entry.desc)
            raise RuntimeError(msg)
        return sm_class(os_entry, prof_entry, template_entry)
    # _create_machine()

    @staticmethod
    def _get_os(template, os_name=None):
        """
        Return the OS type to be used for the installation
        """
        # os not specified: use the default associated with the template
        if os_name is None:
            return template.operating_system_rel
        # os specified by user: override one defined in database and issue a
        # warning
        os_entry = OperatingSystem.query.filter_by(
            name=os_name).one_or_none()
        if os_entry is None:
            raise ValueError('OS {} not found'.format(
                os_name))

        return os_entry
    # _get_os()

    @staticmethod
    def _get_profile(system_name, profile_name):
        """
        Get a SystemProfile instance based on the system and profile names
        passed in the request parameters. In case only the system name is
        provided, the default profile will be used.

        Args:
            system_name (str): system name in db
            profile_name (str): profile name in db

        Raises:
            ValueError: in case instance cannot be found

        Returns:
            SystemProfile: a SystemProfile instance.
        """
        if profile_name is not None:
            profile = SystemProfile.query.join(
                'system_rel'
            ).filter(
                SystemProfile.name == profile_name
            ).filter(
                System.name == system_name
            ).one_or_none()
            if profile is None:
                raise ValueError('Profile {} not found'.format(profile_name))
        else:
            profile = SystemProfile.query.join(
                'system_rel'
            ).filter(
                SystemProfile.default == bool(True)
            ).filter(
                SystemProfile.system == system_name
            ).one_or_none()
            if profile is None:
                raise ValueError(
                    'Default profile for system {} not available'.format(
                        system_name)
                )

        return profile
    # _get_profile()

    @staticmethod
    def _get_template(template_name):
        """
        Get template entry in db
        """
        template_entry = Template.query.filter_by(
            name=template_name).one_or_none()
        if template_entry is None:
            raise ValueError('Template {} not found'.format(
                template_name))

        return template_entry
    # _get_template()

    def cleanup(self):
        """
        Proxy the call to the real machine to perform cleanup.
        """
        return self._machine.cleanup()
    # cleanup()

    @classmethod
    def parse(cls, params):
        """
        Args:
            params(str): A string containing a json in the format:
               {
                   "os": "<name of the operating system>",
                   "template": "<name of the template>",
                   "profile": "<system_name>[/<name of the profile>]"
               }

        Returns:
            dict: Resources allocated for the installation.

        Raises:
            SyntaxError: if content is in wrong format.
            ValueError: if certain properties are not defined.
        """
        try:
            params = json.loads(params)
            validate(params, INSTALL_REQ_PARAMS_SCHEMA)
        except Exception as exc:
            raise SyntaxError("Invalid request parameters") from exc

        template_entry = cls._get_template(params['template'])
        os_entry = cls._get_os(template_entry, params.get('os'))

        result = {
            'resources': {'shared': [], 'exclusive': []},
            'description': MACHINE_DESCRIPTION.format(os_entry.name)
        }

        # check which format the profile parameter is using
        profile = cls._get_profile(params['system'], params.get("profile"))
        system = profile.system_rel

        # check required FCP parameters- use schema to validate specs field
        volumes = profile.storage_volumes_rel
        for vol in volumes:
            if vol.type_rel.name == 'FCP':
                fcp_schema = vol.get_schema('specs')['oneOf'][0]
                try:
                    validate(vol.specs, fcp_schema)
                except ValidationError as exc:
                    raise ValueError(
                        'failed to validate FCP parameters {} of volume {}: '
                        '{}'.format(vol.specs, vol.volume_id, exc.message))
            try:
                vol.part_table['table']
            except (TypeError, KeyError):
                raise ValueError(
                    'volume {} has no partition table defined'.format(
                        vol.volume_id))

        # make sure we have a valid network interface to perform installation
        gw_iface = profile.gateway_rel
        # gateway interface not defined: use first available
        if gw_iface is None:
            try:
                gw_iface = profile.system_ifaces_rel[0]
            except IndexError:
                msg = 'No network interface attached to perform installation'
                raise ValueError(msg)
            if gw_iface.ip_address_rel is None:
                raise ValueError(
                    "Gateway interface '{}' has no IP address assigned".format(
                        gw_iface.name)
                )

        # make sure the system has a hypervisor profile defined
        if profile.hypervisor_profile_rel is None:
            raise ValueError(
                'System profile must have a required hypervisor profile '
                'defined')

        # the system being installed is considered an exclusive resource
        result['resources']['exclusive'].append(system.name)
        system = system.hypervisor_rel

        # the nested hypervisor hierarchy is considered a shared resource
        while system != None:
            result.get("resources").get("shared").append(system.name)
            system = system.hypervisor_rel

        return result
    # parse()

    def start(self):
        """
        Proxy the call to the real machine to start execution.
        """
        return self._machine.start()
    # start()
# AutoInstallMachine
