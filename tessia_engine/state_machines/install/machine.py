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
#pylint: disable=import-error
from tessia_baselib.common.ssh.client import SshClient
from tessia_baselib.hypervisors import Hypervisor
#pylint: enable=import-error
from jsonschema import validate
from socket import inet_ntoa
from tessia_engine.config import Config
#pylint: disable=unused-import
# Import SESSION so there is connection to the Database
from tessia_engine.db.connection import MANAGER
#pylint: enable=unused-import
from tessia_engine.db.models import SystemProfile, Template, SystemIface
from tessia_engine.state_machines.base import BaseMachine
from time import sleep

import jinja2
import json
#
# CONSTANTS AND DEFINITIONS
#
MACHINE_DESCRIPTION = 'Automatic Distro Installation State Machine'

# Schema for the installation request
INSTALL_REQ_PARAMS_SCHEMA = {
    "type": "object",
    "properties": {
        "template": {"type": "string"},
        "profile": {"type": "string"}
    },
    "required": [
        "template",
        "profile"
    ]
}
#
# CODE
#
class InstallMachine(BaseMachine):
    """
    Class for the Install Machine. This state machine performs the
    installation of Linux Distros in a system, with the configuration
    according to the system profile and a template file for a autofile.
    We consider a autofile to be a file that is used to describe the
    automatic installation process of a Linux Dirsto, without user
    intervention: in case of RHEL, it is the Kickstart file, in case of
    Ubuntu, it is the preseed file and for SLES it is the autoyast file.
    """
    NAME = 'install'

    def __init__(self, params):
        """
        See base class docstring.

        Args:
            params (str): A string containing a json in the format:
            {
                "template": "<name of the template>",
                "profile": "<name of the profile>"}
            }
        """
        super(InstallMachine, self).__init__(params)

        self._autofile_url = None
        self._autofile_path = None
        self._hyp_type = None
        self._hyp_user = None
        self._hyp_pwd = None
        self._hyp_name = None
        self._hyp_hostname = None
        self._config = None
        self._template = None
        self._cmdline = None
        self._template_type = None

        # Create the first connection
        MANAGER.session()
        params = json.loads(params)
        # In this case we don't call static method parse because we have more
        # information to fetch from the database, besides the required
        # resources.
        self._parse_config(params)
    # __init__()

    def _create_autofile(self):
        """
        Auxiliary method to create the autofile from the template.
        """
        print("Creating autofile")
        template = jinja2.Template(self._template)

        autofile_content = template.render(config=self._config)
        with open(self._autofile_path, "w") as autofile:
            autofile.write(autofile_content)
    # _create_autofile()

    def _parse_config(self, params):
        """
        Auxiliary method that parses the configuration based on the
        name of the template and name of the system profile.

        Args:
            params (dict): a dictionary containing the following information:
               {
                   "template": "<name of the template>",
                   "profile": "<name of the profile>"
               }
        """
        ret = {
            "guest_name": None,
            "cpu": None,
            "memory": None,
            "parameters": { # parameters for the start command
                "storage_volumes": [],
                "ifaces": [],
                "default_iface": None,
                "repo_url": None,
                "hostname": None,
                "parameters": {
                    "boot_method": "network",
                    "boot_options": {
                        "kernel_uri": None,
                        "initrd_uri": None,
                        "cmdline": None
                    }
                }
            }
        }

        # Get the content of the template
        template_name = params.get("template")
        template = Template.query.filter_by(name=template_name).one()
        self._template = template.content
        self._template_type = template.template_type

        # Get the guest information from the profile
        profile_name = params.get("profile")
        profile = SystemProfile.query.filter_by(name=profile_name).one()
        ret["cpu"] = profile.cpu
        ret["memory"] = profile.memory
        ret["guest_name"] = profile.system_rel.name
        ret["parameters"]["hostname"] = profile.system_rel.hostname

        # Get the credentials for the hypervisor
        hyper_profile = profile.hypervisor_profile_rel
        hyper_credentials = hyper_profile.credentials
        self._hyp_user = hyper_credentials.get("username")
        self._hyp_pwd = hyper_credentials.get("password")

        # Get the type of Hypervisor to be used in tessia-baselib
        # maybe there is an inconsistency between hypervisor type and
        # system type in tessia-baselib.
        self._hyp_type = profile.system_rel.type_rel.name
        self._hyp_name = hyper_profile.system_rel.name
        self._hyp_hostname = hyper_profile.system_rel.hostname

        # Get the name of the default gateway interface
        gateway_iface_name = profile.parameters.get("gateway_iface")
        system_id = profile.system_id
        gateway_iface = (
            SystemIface.query.filter_by(system_id=system_id,
                                        name=gateway_iface_name).one())

        # Iterate over all available storages and gather information
        storage_volumes_lst = ret.get("parameters").get("storage_volumes")
        for storage_volume in profile.storage_volumes_rel:
            storage_volumes_lst.append(
                self._parse_svol(storage_volume))

        # Iterate over all available network interfaces and gather information
        ifaces_lst = ret.get("parameters").get("ifaces")
        for system_iface in profile.system_ifaces_rel:
            ifaces_lst.append(
                self._parse_iface(system_iface,
                                  system_iface is gateway_iface))

        # Get the configuration of the default network interface
        # to be used in the generation of the cmdline
        ret.get("parameters")["default_iface"] = (
            self._parse_iface(gateway_iface, True))

        repo_url = profile.operating_system_rel.repository_rel.url
        ret.get("parameters")["repo_url"] = repo_url

        boot_options = (
            ret.get("parameters").get("parameters").get("boot_options"))

        config = Config.get_config()
        autofile_name = profile.system_rel.name + "-" + profile.name

        self._autofile_url = (config.get("install_machine").get("url") + "/"
                              + autofile_name)
        self._autofile_path = (config.get("install_machine").get("www_dir")
                               + "/" + autofile_name)

        self._update_boot_options(profile, gateway_iface, self._autofile_url,
                                  boot_options)
        self._config = ret
    # _parse_config()

    @staticmethod
    def _parse_iface(iface, gateway_iface):
        """
        Auxiliary method to parse the information of a network interface

        Args:
            iface (SystemIface):  a SystemIface instance.
            gateway_iface (bool): a flag to indicate that the interface being
                                  parsed is the default gateway interface.

        Returns:
            dict: a dictionary containing the parsed information.
        """
        ret = {}
        ret["attributes"] = iface.attributes
        ret["ip"] = iface.ip_address_rel.address
        ret["cidr_addr"] = iface.ip_address_rel.subnet_rel.address
        ret["subnet"], ret["cidr_prefix"] = ret["cidr_addr"].split("/")
        # We need to convert the network mask from the cidr prefix format
        # to a ip mask format.
        ret["mask"] = inet_ntoa(
            ((0xffffffff << (32 - int(ret["cidr_prefix"])))
             & 0xffffffff).to_bytes(4, byteorder="big")
        )
        ret["osname"] = iface.osname
        ret["is_gateway"] = gateway_iface
        if gateway_iface:
            ret["gateway"] = iface.ip_address_rel.subnet_rel.gateway
            ret["dns_1"] = iface.ip_address_rel.subnet_rel.dns_1
            ret["dns_2"] = iface.ip_address_rel.subnet_rel.dns_2

        return ret
    # _parse_iface()

    @staticmethod
    def _parse_svol(storage_vol):
        """
        Auxiliary method to parse the information of a storage volume,
        (eg: type of disk, partition table, etc).

        Args:
            storage_vol (StorageVolume): a StorageVolume instance.

        Returns:
            dict: a dictionary with all the parsed information.
        """
        ret = {}
        # TODO: remove the following remap between the Information in the
        # tessia-engine database and the tessia_baselib.
        remap = {"ECKD": "DASD", "SCSI": "SCSI"}

        disk_type = storage_vol.type_rel.name
        ret["disk_type"] = remap[disk_type]
        ret["volume_id"] = storage_vol.volume_id
        ret["system_attributes"] = storage_vol.system_attributes
        ret["specs"] = storage_vol.specs

        ret["part_table"] = storage_vol.part_table
        ret["is_root"] = False
        for entry in ret["part_table"]["table"]:
            if entry["mp"] == "/":
                ret["is_root"] = True
                break

        return ret
    # _parse_svol()

    def _start_guest_for_installation(self):
        """
        Auxiliary method to start the Guest for installation.
        """
        print("Starting guest")
        hyp = Hypervisor(self._hyp_type, self._hyp_name, self._hyp_hostname,
                         self._hyp_user, self._hyp_pwd, None)
        hyp.login()

        hyp.start(self._config["guest_name"], self._config["cpu"],
                  self._config["memory"], self._config["parameters"])
    # _start_guest_for_installation()

    @staticmethod
    def _update_boot_options(profile, gateway_iface, autofile, boot_options):
        """
        Auxiliary method tha update the boot_options dictionary.

        Args:
            profile (SystemProfile):     A SystemProfile instance.
            gateway_iface (SystemIface): A SystemIface instance containing the
                                         the default gateway interface.
            autofile (str):              Url to the autofile.
            boot_options (dict):         The dictionary containing the boot
                                         options to be updated.
        """
        operating_system = profile.operating_system_rel
        repo = operating_system.repository_rel

        kernel_uri = repo.url + repo.kernel
        initrd_uri = repo.url + repo.initrd

        boot_options["kernel_uri"] = kernel_uri
        boot_options["initrd_uri"] = initrd_uri

        repo_url = repo.url
        hostname = profile.system_rel.hostname
        ip_addr = gateway_iface.ip_address_rel.address
        gateway_ip = gateway_iface.ip_address_rel.subnet_rel.gateway
        iface_osname = gateway_iface.osname
        cidr_prefix = (
            gateway_iface.ip_address_rel.subnet_rel.address.split("/")[1])
        nameserver = gateway_iface.ip_address_rel.subnet_rel.dns_1

        cmdline = repo.cmdline.format(
            repo=repo_url, ip=ip_addr, gateway=gateway_ip,
            cidr_prefix=cidr_prefix, hostname=hostname,
            iface_name=iface_osname, nameserver=nameserver, autofile=autofile)

        boot_options["cmdline"] = cmdline
    # _update_boot_options()

    def _wait_for_installation_end(self, shell):
        """
        Auxiliary method that waits for the installation of a Distro.
        A specific handler is called depending on the type of the Distro.

        Args:
           shell (SshShell): a SshShell instance, used to issue commands.

        Returns:
           bool: True in case the installation has successfully finished.
        """
        print("Waiting the end of the installation.")
        wait_installation_handlers = {
            "RHEL": self._wait_for_installation_end_rhel
        }

        try:
            return wait_installation_handlers[self._template_type](shell)
        except KeyError:
            print("Invalid handler '{}' for waiting for installation".format(
                self._template_type))
            return False
    # _wait_for_installation_end()

    @staticmethod
    def _wait_for_installation_end_rhel(shell):
        """
        Auxiliary method that waits for the installation of RHEL in a guest.
        This method periodically checks the /tmp/anaconda.log file in the
        the guest and looks for a string that indicates that the process
        has finished. There is a timeout of 10 minutes.

        Args:
           shell (SshShell): a SshShell instance, used to issue commands.

        Returns:
           bool: True in case the installation has successfully finished.
        """
        timeout_installation = 600
        frequency_check = 10
        termination_string = "Thread Done: AnaConfigurationThread"
        initial_line = 1
        cmd_read_line = "tail -n +{} /tmp/anaconda.log"
        elapsed_time = 0
        # Performs successive calls to tail to extract the end of the file
        # from a previous start point.
        while elapsed_time < timeout_installation:
            ret, out = shell.run(cmd_read_line.format(initial_line))
            if ret != 0:
                print("Error while reading the installation log.")
                return False
            lines = out.split("\n")
            if len(lines) > 1 or lines[0] != "":
                initial_line += len(lines)
                print(out)
            if out.find(termination_string) != -1:
                return True
            sleep(frequency_check)
            elapsed_time += frequency_check

        return False
    # _wait_for_installation_end_rhel()

    def _wait_for_ssh_connection(self):
        """
        Auxiliary method that waits for the ssh connectivity to the guest
        after starting it.

        Returns:
            SshClient: an instance of SshClient connected to the host or None
                       in case the connection fails.
        """
        timeout_trials = [5, 10, 20, 40]

        ssh_client = SshClient()

        for timeout in timeout_trials:
            try:
                ssh_client.login(self._config["parameters"]["hostname"],
                                 user="root", passwd="")
                return ssh_client
            except ConnectionError:
                print("Connection not available yet."
                      " Waiting {} seconds.".format(timeout))
                sleep(timeout)
        return None
    # _wait_for_ssh_connection()

    #pylint:disable=no-self-use
    def cleanup(self):
        """
        See base class docstring
        """
        print('cleanup done')
    # cleanup()

    @staticmethod
    def parse(params):
        """
        Args:
            params(str): A string containing a json in the format:
               {
                   "template": "<name of the template>",
                   "profile": "<name of the profile>"
               }

        Returns:
            dict: Resources allocated for the installation.

        Raises:
            SyntaxError: if content is in wrong format.
        """
        ret = {
            'resources': {'shared': [], 'exclusive': []},
            'description': MACHINE_DESCRIPTION,
        }

        try:
            # It does not matter if it is an invalid json or an
            # invalid install request parameter (validate by the schema)
            # so we catch all exceptions
            params = json.loads(params)
            validate(params, INSTALL_REQ_PARAMS_SCHEMA)
        except Exception as exc:
            raise SyntaxError("Invalid request parameters") from exc

        profile_name = params.get("profile")
        system_profile = SystemProfile.query.filter_by(
            name=profile_name).one()
        system = system_profile.system_rel

        # The system being installed is considered a exclusive resource
        ret.get("resources").get("exclusive").append(system.name)
        system = system.hypervisor_rel

        # The nested hypervisor hierarchy is considered a shared resource
        while system != None:
            ret.get("resources").get("shared").append(system.name)
            system = system.hypervisor_rel

        return ret
    # parse()

    def start(self):
        """
        Entry point for the installation state machine.

        Returns:
            int: 0 if the machine executed successfully, and
                 1 otherwise.
        """
        success = 0
        fail = 1

        self._create_autofile()
        self._start_guest_for_installation()

        ssh_client = self._wait_for_ssh_connection()

        if ssh_client is None:
            print("Error while waiting for connection")
            return fail

        shell = ssh_client.open_shell()

        if self._wait_for_installation_end(shell):
            print("Installation successful")
            return success

        print("Installation failed")

        return fail
    # start()
# Echomachine
