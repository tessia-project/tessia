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
from socket import gethostbyname
from tessia.server.db.connection import MANAGER
from tessia.server.lib.post_install import PostInstallChecker
from tessia.server.state_machines.base import BaseMachine
from tessia.server.state_machines.autoinstall.dbcontroller import \
    DbController
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from tessia.server.state_machines.autoinstall.plat_lpar import PlatLpar
from tessia.server.state_machines.autoinstall.plat_kvm import PlatKvm
from tessia.server.state_machines.autoinstall.plat_zvm import PlatZvm
from tessia.server.state_machines.autoinstall.sm_anaconda import SmAnaconda
from tessia.server.state_machines.autoinstall.sm_autoyast import SmAutoyast
from tessia.server.state_machines.autoinstall.sm_debian import \
    SmDebianInstaller
from tessia.server.state_machines.autoinstall.sm_subiquity import \
    SmSubiquityInstaller
from urllib.parse import urlsplit

import ipaddress
import json
import logging
import os
import random
import string

#
# CONSTANTS AND DEFINITIONS
#
MACHINE_DESCRIPTION = 'Autoinstall {} with OS {}'

# directory containing the kernel cmdline templates
CMDLINE_TEMPLATES_DIR = os.path.dirname(
    os.path.abspath(__file__)) + "/templates/"

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
            params (str): string representation of JSON object
                          with schema INSTALL_REQ_PARAMS_SCHEMA
        """
        super().__init__(params)

        # open the db connection
        MANAGER.connect()

        parsed = self.parse(params)
        self._params = parsed['params']

        # apply custom log level if specified
        self._log_config(self._params.get('verbosity'))
        self._logger = logging.getLogger(__name__)

        self._model = self._model_from_params(self._params)
        self._machine = self._create_machine()
    # __init__()

    def _create_platform(self):
        """
        Create an instance of machine platform, which is linked to
        baselib's hypervisor
        """
        hyp_profile_obj = self._model.system_profile.hypervisor
        if isinstance(hyp_profile_obj,
                      AutoinstallMachineModel.HmcHypervisor):
            plat_class = PlatLpar
        elif isinstance(hyp_profile_obj,
                        AutoinstallMachineModel.ZvmHypervisor):
            plat_class = PlatZvm
        elif isinstance(hyp_profile_obj,
                        AutoinstallMachineModel.KvmHypervisor):
            plat_class = PlatKvm
        else:
            raise RuntimeError('Support for {} is not implemented'.format(
                hyp_profile_obj.__class__.__qualname__))

        hyp_obj = plat_class.create_hypervisor(self._model)
        platform = plat_class(self._model, hyp_obj)
        return platform
    # _create_platform()

    def _create_machine(self):
        """
        Create the correct state machine based on the operating system being
        installed.
        """
        self._model.validate()

        # model can accept any OS type, but we have only this many implemented
        os_entry = self._model.operating_system
        if os_entry.type not in SUPPORTED_TYPES:
            raise ValueError("OS type '{}' is not supported for installation"
                             .format(os_entry.type))

        if os_entry.type == 'debian' and os_entry.major >= 2004:
            if os_entry.minor == 0 and self._model.ubuntu20_legacy_installer:
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

        dbctrl = DbController(MANAGER)
        platform = self._create_platform()
        # PostInstallChecker expects database objects, so we fetch them again
        _, profile_obj = dbctrl._get_sysprof_entries(
            self._model.system_profile.system_name,
            self._model.system_profile.profile_name)

        # we pass os_entry, which is compatible to database entry
        post_install = PostInstallChecker(profile_obj, os_entry,
                                          permissive=True)
        self._logger.debug("Creating machine class %s for %s",
                           sm_class.__name__, str(os_entry))
        machine = sm_class(self._model, platform,
                           post_install_checker=post_install)
        machine.persist_init_data(dbctrl)
        return machine
    # _create_machine()

    @staticmethod
    def _filter_os_repos_by_subnet(
            os_repos: "list[AutoinstallMachineModel.OsRepository]",
            # pylint: disable=line-too-long
            subnets: "list[union[ipaddress.IPv4Network,ipaddress.IPv6Network]]"):
        """
        From os repos choose those that are in specified subnets
        """
        result = []
        for os_repo in os_repos:
            try:
                repo_addr = gethostbyname(
                    urlsplit(os_repo.url).netloc.rsplit('@', 1)[-1])
                address_pyobj = ipaddress.ip_address(repo_addr)
            # can't resolve repo's hostname: skip it
            except Exception:
                continue
            if any(address_pyobj in subnet for subnet in subnets):
                result.append(os_repo)

        return result
    # _filter_os_repos_by_subnet()

    @staticmethod
    def _get_installer_cmdline_template(
            os_entry: AutoinstallMachineModel.OperatingSystem):
        """
        Retrieve installation kernel command line
        """
        # use a corresponding generic template for the OS type
        # Note that actual template may be overridden by state machine
        template_filename = '{}.cmdline.jinja'.format(os_entry.type)

        with open(CMDLINE_TEMPLATES_DIR + template_filename,
                  "r", encoding='utf-8') as template_file:
            template_content = template_file.read()

        return AutoinstallMachineModel.Template(template_filename,
                                                template_content)
    # _get_installer_cmdline_template()

    def _model_from_params(self, params):
        """
        Create model from machine params
        """
        # we can use static class, not an instance,
        # because instance only makes sure database is connected
        dbctrl = DbController(MANAGER)
        os_entry, os_repos = dbctrl.get_os(params['system'],
                                           params['os'])

        if 'template' in params:
            template_entry = dbctrl.get_template(params['template'])
        elif os_entry.template_name:
            template_entry = dbctrl.get_template(os_entry.template_name)
        else:
            raise ValueError("No installation template for OS '{}' specified"
                             .format(os_entry.name))

        # get installer template
        installer_template = self._get_installer_cmdline_template(os_entry)

        system_model = dbctrl.get_system(params['system'],
                                         params.get("profile"))
        # from all the os repos choose those that can be accessed
        # via gateway interface define on the system
        gateway_subnets = [network.subnet for network in
                           system_model.list_gateway_networks()]
        accessible_os_repos = self._filter_os_repos_by_subnet(
            os_repos, gateway_subnets)
        if not accessible_os_repos:
            # fallback if no "better" repo was found
            accessible_os_repos = os_repos

        custom_os_repos, custom_package_repos = dbctrl.get_custom_repos(
            params.get('repos', []))
        install_opts = dbctrl.get_install_opts(params['system'],
                                               params.get("profile"))
        # generate pseudo-random password for vnc and ssh installer sessions
        install_opts['installation-password'] = ''.join(
            random.sample(string.ascii_letters + string.digits, 8))

        model = AutoinstallMachineModel(os_entry, accessible_os_repos,
                                        template_entry, installer_template,
                                        custom_os_repos, custom_package_repos,
                                        system_model, install_opts)

        return model
    # _model_from_params()

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
            dict: Resources allocated for the installation
                  Has "resources" and "description" entries
                  (tp be conusmed by scheduler)
                  and "params" as a an object according to schema

        Raises:
            SyntaxError: if content is in wrong format.
            ValueError: if certain properties are not defined.
        """
        try:
            params = json.loads(params)
            validate(params, INSTALL_REQ_PARAMS_SCHEMA)
        except Exception as exc:
            raise SyntaxError("Invalid request parameters") from exc

        # make a few requests to get necessary parameters
        dbctrl = DbController(MANAGER)
        # check which format the profile parameter is using
        system, _ = dbctrl._get_sysprof_entries(params['system'], None)
        os_entry, _ = dbctrl.get_os(params['system'],
                                    params['os'])
        result = {
            'resources': {'shared': [], 'exclusive': []},
            'description': MACHINE_DESCRIPTION.format(
                system.name, os_entry.name),
            'params': params
        }

        # the system being installed is considered an exclusive resource
        result['resources']['exclusive'].append(system.name)
        system = system.hypervisor_rel

        # the nested hypervisor hierarchy is considered a shared resource
        while system is not None:
            result.get("resources").get("shared").append(system.name)
            system = system.hypervisor_rel

        # check required FCP parameters- use schema to validate specs field
        # -- should be checked in API instead

        # in case the system profile has no hypervisor profile defined the
        # machine's constructor will use the hypervisor's default profile,
        # therefore there is no need to check it here.

        return result
    # parse()

    def start(self):
        """
        Proxy the call to the real machine to start execution.
        """
        try:
            self._machine.start()
        except:
            DbController(MANAGER).clear_target_os_field(self._model)
            raise

        # if we got here, machine executed successfully
        # update OS field on the target system
        DbController(MANAGER).set_target_os_field(self._model)

        # To make sure the cleaning_up variable is set correctly,
        # run the cleanup here.
        self.cleanup()
        return 0
    # start()
# AutoInstallMachine
