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
Base state machine for auto installation of operating systems
"""

#
# IMPORTS
#
from tessia_baselib.common.ssh.client import SshClient
from socket import inet_ntoa
from tessia_engine.config import Config
from tessia_engine.db.connection import MANAGER
from tessia_engine.state_machines.install.plat_lpar import PlatLpar
from tessia_engine.state_machines.install.plat_kvm import PlatKvm
from time import sleep
from urllib.parse import urljoin

import abc
import jinja2
import logging
import os

#
# CONSTANTS AND DEFINITIONS
#
PLATFORMS = {
    'lpar': PlatLpar,
    'kvm': PlatKvm,
}

#
# CODE
#
class SmBase(metaclass=abc.ABCMeta):
    """
    This is the base machine defining each state that the machine goes through
    during an automated installation process. Actions that are operating system
    agnostic go here.
    """
    @abc.abstractmethod
    def __init__(self, os_entry, profile_entry, template_entry):
        """
        Store the objects and create the right platform object
        """
        self._os = os_entry
        self._profile = profile_entry
        self._template = template_entry
        self._system = profile_entry.system_rel
        self._logger = logging.getLogger(__name__)

        # TODO: allow usage of multiple/additional repositories
        try:
            self._repo = self._os.repository_rel[0]
        except IndexError:
            raise RuntimeError('No repository available for the specified OS')

        gw_iface = self._profile.gateway_rel
        # gateway interface not defined: use first available
        if gw_iface is None:
            try:
                gw_iface = self._profile.system_ifaces_rel[0]
            except IndexError:
                msg = 'No network interface attached to perform installation'
                raise RuntimeError(msg)
        self._gw_iface = self._parse_iface(gw_iface, True)

        # make sure the system has a hypervisor profile defined otherwise
        # usage of platform object will fail
        if self._profile.hypervisor_profile_rel is None:
            raise RuntimeError(
                'System profile must have a required hypervisor profile '
                'defined')

        # Create the appropriate platform object according to the system being
        # installed.
        hyp_type = self._system.type_rel.name.lower()
        try:
            plat_class = PLATFORMS[hyp_type]
        except KeyError:
            raise RuntimeError('Platform type {} is not supported'.format(
                hyp_type))
        self._platform = plat_class(
            self._profile.hypervisor_profile_rel,
            self._profile,
            self._os,
            self._repo,
            self._gw_iface)

        # The path and url for the auto file.
        config = Config.get_config()
        autofile_name = '{}-{}'.format(self._system.name, self._profile.name)
        autofile_name = autofile_name.replace(' ', '-')
        self._autofile_url = urljoin(
            config["auto_install"]["url"], autofile_name)
        self._autofile_path = os.path.join(
            config["auto_install"]["dir"], autofile_name)
        # set during collect_info state
        self._info = None
    # __init__()

    @abc.abstractmethod
    def _get_kargs(self):
        """
        This method should be implemented by children classes and return a
        string containing the cmdline used for the os installer.
        """
        raise NotImplementedError()
    # _get_kargs()

    def _get_ssh_conn(self):
        """
        Auxiliary method to get a ssh connection and shell to the target system
        being installed.
        """
        timeout_trials = [5, 10, 20, 40]

        hostname = self._profile.system_rel.hostname
        user = self._profile.credentials['user']
        password = self._profile.credentials['passwd']

        for timeout in timeout_trials:
            try:
                ssh_client = SshClient()
                ssh_client.login(hostname, user=user, passwd=password)
                ssh_shell = ssh_client.open_shell()
                return ssh_client, ssh_shell
            except ConnectionError:
                self._logger.warning("connection not available yet, "
                                     "retrying in %d seconds.", timeout)
                sleep(timeout)

        raise ConnectionError("Error while trying to connect"
                              " to the target system.")
    # _get_ssh_conn()

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
        result = {"attributes": iface.attributes}
        result["type"] = iface.type
        result["mac_addr"] = iface.mac_address
        # iface has no ip associated: set empty values
        if iface.ip_address_rel is None:
            result["ip"] = None
            result["subnet"] = None
            result["mask_bits"] = None
            result["mask"] = None
        else:
            result["ip"] = iface.ip_address_rel.address
            cidr_addr = iface.ip_address_rel.subnet_rel.address
            result["subnet"], result["mask_bits"] = cidr_addr.split("/")
            # We need to convert the network mask from the cidr prefix format
            # to an ip mask format.
            result["mask"] = inet_ntoa(
                ((0xffffffff << (32 - int(result["mask_bits"])))
                 & 0xffffffff).to_bytes(4, byteorder="big")
            )
        result["osname"] = iface.osname
        result["is_gateway"] = gateway_iface
        if gateway_iface:
            # gateway interface was checked in parse for ip address existence
            result["gateway"] = iface.ip_address_rel.subnet_rel.gateway
            result["dns_1"] = iface.ip_address_rel.subnet_rel.dns_1
            result["dns_2"] = iface.ip_address_rel.subnet_rel.dns_2

        # osa: add some sensitive defaults
        if result['type'] == 'OSA':
            result['attributes'].setdefault('portno', '0')
            result['attributes'].setdefault('portname', 'OSAPORT')

        return result
    # _parse_iface()

    def _parse_svol(self, storage_vol):
        """
        Auxiliary method to parse the information of a storage volume,
        (eg: type of disk, partition table, etc).

        Args:
            storage_vol (StorageVolume): a StorageVolume instance.

        Returns:
            dict: a dictionary with all the parsed information.
        """
        result = {}
        result["type"] = storage_vol.type_rel.name
        result["volume_id"] = storage_vol.volume_id
        result["server"] = storage_vol.server
        result["system_attributes"] = storage_vol.system_attributes.copy()
        result["specs"] = storage_vol.specs.copy()

        result["part_table"] = storage_vol.part_table
        result["is_root"] = False
        for entry in result["part_table"]["table"]:
            if entry["mp"] == "/":
                result["is_root"] = True
                break

        # device path not user-defined: determine it based on the platform
        if "device" not in result["system_attributes"]:
            result["system_attributes"]["device"] = \
                self._platform.get_vol_devpath(storage_vol)

        return result
    # _parse_svol()

    def init(self):
        """
        Initialization, clean the current OS in the SystemProfile.
        """
        self._profile.operating_system_id = None
        MANAGER.session.commit()
    # init()

    def check_installation(self):
        """
        Make sure that the installation was successfully completed.
        """
        ssh_client, shell = self._get_ssh_conn()

        ret, _ = shell.run("echo 1")
        if ret != 0:
            raise RuntimeError("Error while checking the installed system.")

        shell.close()
        ssh_client.logoff()
    # check_installation()

    def cleanup(self):
        """
        Called upon job cancellation or end. Deletes the autofile if it exists.
        """
        if os.path.exists(self._autofile_path):
            try:
                os.remove(self._autofile_path)
            except OSError:
                raise RuntimeError("Unable to delete the autofile during"
                                   " cleanup.")
    # cleanup()

    def collect_info(self):
        """
        Prepare all necessary information for the template rendering by
        populating the self._info dict. Can be implemented by children classes.
        """
        info = {
            'ifaces': [],
            'repos': [],
            'svols': [],
            'system_type': self._system.type
        }

        # iterate over all available volumes and ifaces and filter data for
        # template processing later
        for svol in self._profile.storage_volumes_rel:
            info['svols'].append(self._parse_svol(svol))
        for iface in self._profile.system_ifaces_rel:
            info['ifaces'].append(self._parse_iface(
                iface, iface.osname == self._gw_iface['osname']))

        info['repos'].append(self._repo.url)

        self._info = info
    # collect_info()

    def create_autofile(self):
        """
        Fill the template and create the autofile in the target location
        """
        self._logger.info("generating autofile")
        template = jinja2.Template(self._template.content)

        autofile_content = template.render(config=self._info)

        # Write the autofile for usage during installation
        # by the distro installer.
        with open(self._autofile_path, "w") as autofile:
            autofile.write(autofile_content)
        # Write the autofile in the directory that the state machine
        # is executed.
        with open("./" + os.path.basename(
            self._autofile_path), "w") as autofile:
            autofile.write(autofile_content)
    # create_autofile()

    def post_install(self):
        """
        Perform post installation activities.
        """
        # Change the operating system in the profile.
        self._profile.operating_system_id = self._os.id
        MANAGER.session.commit()

        self.cleanup()
    # post_install()

    def target_boot(self):
        """
        Performs the boot of the target system to initiate the installation
        """
        self._platform.boot(self._get_kargs())
    # target_boot()

    def target_reboot(self):
        """
        Performs a reboot of the target system after installation is done
        """
        self._platform.reboot(self._profile)
    # target_reboot()

    @abc.abstractmethod
    def wait_install(self):
        """
        Each system has its heuristic to follow the installation progress and
        determine when it's done therefore this function should be implemented
        by children classes.
        """
        raise NotImplementedError()
    # wait_install()

    def start(self):
        """
        Start the states' transition.
        """
        self._logger.info('new state: init')
        self.init()

        self._logger.info('new state: collect_info')
        self.collect_info()

        self._logger.info('new state: create_autofile')
        self.create_autofile()

        self._logger.info('new state: target_boot')
        self.target_boot()

        self._logger.info('new state: wait_install')
        self.wait_install()

        self._logger.info('new state: target_reboot')
        self.target_reboot()

        self._logger.info('new state: check_installation')
        self.check_installation()

        self._logger.info('new state: post_install')
        self.post_install()

        self._logger.info('Installation finished successfully')
        return 0
    # start()
# SmBase
