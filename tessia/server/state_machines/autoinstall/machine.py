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
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import OperatingSystem
from tessia.server.db.models import Template
from tessia.server.db.models import System, SystemProfile
from tessia.server.state_machines.base import BaseMachine
from tessia.server.state_machines.autoinstall.sm_anaconda import SmAnaconda
from tessia.server.state_machines.autoinstall.sm_autoyast import SmAutoyast
from tessia.server.state_machines.autoinstall.sm_debian import \
    SmDebianInstaller
from tessia.server.state_machines.autoinstall.sm_subiquity import \
    SmSubiquityInstaller

import json
import logging

#
# CONSTANTS AND DEFINITIONS
#
MACHINE_DESCRIPTION = 'Autoinstall {} with OS {}'

# Schema for the installation request
INSTALL_REQ_PARAMS_SCHEMA = {
    "type": "object",
    "properties": {
        "os": {"type": "string"},
        "profile": {"type": "string"},
        "template": {"type": "string"},
        "repos": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "system": {"type": "string"},
        "verbosity": {"type": "string", "enum": list(BaseMachine._LOG_LEVELS)}
    },
    "required": [
        "os",
        "system"
    ],
    "additionalProperties": False
}

SUPPORTED_TYPES = {
    SmAnaconda.DISTRO_TYPE: SmAnaconda,
    SmAutoyast.DISTRO_TYPE: SmAutoyast,
    SmDebianInstaller.DISTRO_TYPE: SmDebianInstaller,
    SmSubiquityInstaller.DISTRO_TYPE: SmSubiquityInstaller,
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

        # open the db connection
        MANAGER.connect()

        self._params = self.parse(params)['params']

        # apply custom log level if specified
        self._log_config(self._params.get('verbosity'))
        self._logger = logging.getLogger(__name__)

        self._machine = self._create_machine()
    # __init__()

    def _create_machine(self):
        """
        Create the correct state machine based on the operating system being
        installed.
        """
        # get the os entry in db
        os_entry = self._get_os(self._params['os'])
        # get template entry in db
        template_entry = self._get_template(
            os_entry, self._params.get('template'))
        # get the profile entry in db
        prof_entry = self._get_profile(
            self._params['system'], self._params.get("profile"))
        # get user defined repositories, if any
        custom_repos = self._params.get('repos', None)

        option_legacy = (prof_entry.parameters and
                         "tessia_option_installer=legacy" in
                         prof_entry.parameters.get('linux-kargs-installer', '')
                        )

        try:
            if os_entry.type == 'debian' and os_entry.major >= 2004:
                if option_legacy:
                    self._logger.info("NOTE: tessia_option_installer=legacy"
                                      " is specified in the profile")
                    self._logger.info("NOTE: please make sure that repo and"
                                      " template are set accordingly")
                    self._logger.info("NOTE: failure to do so will result in"
                                      " cryptic error messages")
                    sm_class = SUPPORTED_TYPES[os_entry.type]
                else:
                    sm_class = SmSubiquityInstaller
            else:
                sm_class = SUPPORTED_TYPES[os_entry.type]
        except KeyError:
            raise ValueError("OS type '{}' is not supported for installation"
                             .format(os_entry.type))
        return sm_class(os_entry, prof_entry, template_entry, custom_repos)
    # _create_machine()

    @staticmethod
    def _get_os(os_name):
        """
        Return the OS version to be used for the installation

        Args:
            os_name (str): os identifier

        Returns:
            OperatingSystem: db entry

        Raises:
            ValueError: in case specified os does not exist
        """
        os_entry = OperatingSystem.query.filter_by(
            name=os_name).one_or_none()
        if os_entry is None:
            raise ValueError('OS {} not found'.format(os_name))
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
    def _get_template(os_entry, template_name=None):
        """
        Get template entry in db

        Args:
            os_entry (OperatingSystem): db entry
            template_name (str): template identifier

        Returns:
            Template: db entry

        Raises:
            ValueError: if template name does not exist
        """
        # template not specified: use OS' default
        if not template_name:
            if os_entry.template_rel is None:
                raise ValueError('OS {} has no default template defined'
                                 .format(os_entry.name))
            return os_entry.template_rel

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
        # When the job is canceled during a cleanup the routine
        # is not executed again by the scheduler.
        self.cleaning_up = True
        self._logger.info("AutoInstall cleanup is running")
        return self._machine.cleanup()
    # cleanup()

    @classmethod
    def parse(cls, params):
        """
        Args:
            params(str): A string containing a json in the format defined by
            the INSTALL_REQ_PARAMS_SCHEMA variable.

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

        os_entry = cls._get_os(params['os'])
        cls._get_template(os_entry, params.get('template'))

        if os_entry.type not in SUPPORTED_TYPES:
            raise ValueError("OS type '{}' is not supported for installation"
                             .format(os_entry.type))

        # check which format the profile parameter is using
        profile = cls._get_profile(params['system'], params.get("profile"))
        system = profile.system_rel

        result = {
            'resources': {'shared': [], 'exclusive': []},
            'description': MACHINE_DESCRIPTION.format(
                system.name, os_entry.name),
            'params': params
        }

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

        # make sure we have a valid network interface to perform installation
        gw_iface = profile.gateway_rel
        # gateway interface not defined: use first available
        if gw_iface is None:
            try:
                gw_iface = profile.system_ifaces_rel[0]
            except IndexError:
                msg = 'No network interface attached to perform installation'
                raise ValueError(msg)
            if not gw_iface.ip_address_rel:
                raise ValueError(
                    "Gateway network interface <{}> has no IP address assigned"
                    .format(gw_iface.name)
                )
            elif not gw_iface.ip_address_rel.subnet_rel.gateway:
                raise ValueError(
                    "Subnet <{}> of the gateway network interface <{}> has no "
                    "gateway route defined".format(
                        gw_iface.ip_address_rel.subnet_rel.name, gw_iface.name)
                )

        # sanity check, without hypervisor it's not possible to manage
        # system
        if not system.hypervisor_id:
            raise ValueError(
                'System {} cannot be installed because it has no '
                'hypervisor defined'.format(system.name))

        # in case the system profile has no hypervisor profile defined the
        # machine's constructor will use the hypervisor's default profile,
        # therefore there is no need to check it here.

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
        ret_val = self._machine.start()
        # To make sure the cleaning_up variable is set correctly,
        # run the cleanup here.
        self.cleanup()
        return ret_val
    # start()
# AutoInstallMachine
