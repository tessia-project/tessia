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
from tessia_engine.db.connection import MANAGER
from tessia_engine.db.models import OperatingSystem
from tessia_engine.db.models import Template
from tessia_engine.db.models import System
from tessia_engine.db.models import SystemProfile
from tessia_engine.state_machines.base import BaseMachine
from tessia_engine.state_machines.install.sm_anaconda import SmAnaconda
from tessia_engine.state_machines.install.sm_autoyast import SmAutoyast

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
        "template": {"type": "string"},
        "profile": {"type": "string"}
    },
    "required": [
        "template",
        "profile"
    ],
    "additionalProperties": False
}

SUPPORTED_DISTROS = {
    'rhel': SmAnaconda,
    'sles': SmAutoyast,
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
    NAME = 'autoinstall'

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
        MANAGER.session()

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
        template_entry = Template.query.filter_by(
            name=self._params['template']).one_or_none()
        if template_entry is None:
            raise RuntimeError('Template {} not found'.format(
                self._params['template']))

        # get the os entry in db
        os_entry = self._get_os(template_entry, self._params.get('os'))
        # get the profile entry in db
        prof_entry = self._get_profile(self._params.get("profile"))
        try:
            sm_class = SUPPORTED_DISTROS[os_entry.type]
        except KeyError:
            msg = 'OS {} is not supported by this install machine'.format(
                os_entry.desc)
            raise RuntimeError(msg)
        return sm_class(os_entry, prof_entry, template_entry)
    # _create_machine()

    def _get_os(self, template, os_name=None):
        """
        Return the OS type to be used for the installation
        """
        # os not specified: use the default associated with the template
        if os_name is None:
            return template.operating_system_rel
        # os specified by user: override one defined in database and issue a
        # warning
        os_entry = OperatingSystem.query.filter_by(
            name=os_name.upper()).one_or_none()
        if os_entry is None:
            raise RuntimeError('OS {} not found'.format(
                os_name))
        if os_entry != template.operating_system_rel:
            self._logger.warning('warning: custom OS specified by user,'
                                 ' template might not work properly.'
                                 ' Use at your own RISK!')

        return os_entry
    # _get_os()

    @staticmethod
    def _get_profile(profile_param):
        """
        Get a SystemProfile instance based on the profile_param
        passed in the request parameters.

        Args:
            profile_param (str): Identifier for a profile in the format
                                 <system_name>[/<profile_name>]

        Returns:
            SystemProfile: a SystemProfile instance.
        """
        if profile_param.find("/") != -1:
            system_name, profile_name = profile_param.split("/")
            profile = SystemProfile.query.filter_by(
                name=profile_name, system=system_name).one()
        else:
            system_name = profile_param
            system = System.query.filter_by(name=system_name).one()
            profile = SystemProfile.query.filter_by(
                system_id=system.id, default=True).one()

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
            raise RuntimeError('Template {} not found'.format(
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
        profile = cls._get_profile(params['profile'])
        system = profile.system_rel

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
