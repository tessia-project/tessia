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
from tessia.baselib.common.ssh.client import SshClient
from socket import inet_ntoa
from tessia.server.config import Config
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import System, SystemProfile
from tessia.server.lib.post_install import PostInstallChecker
from tessia.server.state_machines.autoinstall.plat_lpar import PlatLpar
from tessia.server.state_machines.autoinstall.plat_kvm import PlatKvm
from tessia.server.state_machines.autoinstall.plat_zvm import PlatZvm
from time import sleep
from time import time
from urllib.parse import urlsplit

import abc
import crypt
import jinja2
import logging
import os
import random
import string

#
# CONSTANTS AND DEFINITIONS
#
# timeout used for ssh connection attempts
CONNECTION_TIMEOUT = 600
PLATFORMS = {
    'lpar': PlatLpar,
    'kvm': PlatKvm,
    'zvm': PlatZvm,
}
# directory containing the kernel cmdline templates
TEMPLATES_DIR = os.path.dirname(os.path.abspath(__file__)) + "/templates/"

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

        # sanity check, without hypervisor it's not possible to manage
        # system
        if not self._system.hypervisor_id:
            raise ValueError(
                'System {} cannot be installed because it has no '
                'hypervisor defined'.format(self._system.name))

        hyp_profile_obj = self._profile.hypervisor_profile_rel
        # no hypervisor profile defined: use default
        if not hyp_profile_obj:
            hyp_profile_obj = SystemProfile.query.join(
                'system_rel'
            ).filter(
                System.id == self._system.hypervisor_id
            ).filter(
                SystemProfile.default == bool(True)
            ).first()
            if not hyp_profile_obj:
                raise ValueError(
                    'Hypervisor {} of system {} has no default profile '
                    'defined'.format(self._system.hypervisor_rel.name,
                                     self._system.name))

        # Create the appropriate platform object according to the system being
        # installed.
        hyp_type = self._system.type_rel.name.lower()
        try:
            plat_class = PLATFORMS[hyp_type]
        except KeyError:
            raise RuntimeError('Platform type {} is not supported'.format(
                hyp_type))
        self._platform = plat_class(
            hyp_profile_obj,
            self._profile,
            self._os,
            self._repo,
            self._gw_iface)

        # The path and url for the auto file.
        config = Config.get_config()
        autofile_name = '{}-{}'.format(self._system.name, self._profile.name)
        autofile_name = autofile_name.replace(' ', '-')
        self._autofile_url = '{}/{}'.format(
            config["auto_install"]["url"], autofile_name)
        self._autofile_path = os.path.join(
            config["auto_install"]["dir"], autofile_name)
        # set during collect_info state
        self._info = None
    # __init__()

    def _get_ssh_conn(self):
        """
        Auxiliary method to get a ssh connection and shell to the target system
        being installed.
        """
        hostname = self._profile.system_rel.hostname
        user = self._profile.credentials['user']
        password = self._profile.credentials['passwd']

        conn_timeout = time() + CONNECTION_TIMEOUT
        self._logger.info('Waiting for connection to be available (%s secs)',
                          CONNECTION_TIMEOUT)
        while time() < conn_timeout:
            try:
                ssh_client = SshClient()
                ssh_client.login(hostname, user=user, passwd=password)
                ssh_shell = ssh_client.open_shell()
                return ssh_client, ssh_shell
            # different errors can happen depending on the state of the
            # target system, so we just catch them all and try again until
            # system is stable
            except Exception:
                sleep(5)

        raise ConnectionError(
            "Timeout occurred while trying to connect to the target system.")
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
        result["size"] = storage_vol.size

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

    @property
    @classmethod
    @abc.abstractmethod
    def DISTRO_TYPE(cls): # pylint: disable=invalid-name
        """
        Return the type of linux distribution supported. The entry should match
        the column 'type' in the operating_systems table.
        """
        raise NotImplementedError()
    # DISTRO_TYPE

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
        # make sure a connection is possible before we use the checker
        ssh_client, shell = self._get_ssh_conn()

        ret, _ = shell.run("echo 1")
        if ret != 0:
            raise RuntimeError("Error while checking the installed system.")

        shell.close()
        ssh_client.logoff()

        if self._system.type == 'KVM':
            self._logger.info('Skipping installation check as KVM guests are '
                              'currently unsupported')
            return

        self._logger.info(
            "Verifying if installed system match expected parameters")
        checker = PostInstallChecker(self._profile, self._os, permissive=True)
        checker.verify()
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
            'svols': [],
            'repos': [],
            'server_hostname': urlsplit(self._autofile_url).hostname,
            'system_type': self._system.type,
            'credentials': self._profile.credentials,
            'sha512rootpwd': crypt.crypt(self._profile.credentials["passwd"]),
            'hostname': self._system.hostname,
            'autofile': self._autofile_url,
            'gw_iface': self._gw_iface,
        }
        # add repo entries - as of today only one repo is supported
        repo = {'url': self._repo.url, 'desc': self._repo.desc,
                'name': self._repo.name.replace(' ', '_')}
        if not repo['desc']:
            repo['desc'] = repo['name']
        info['repos'].append(repo)

        # generate pseudo-random password for vnc session
        info['credentials']['vncpasswd'] = ''.join(
            random.sample(string.ascii_letters + string.digits, 8))

        # iterate over all available volumes and ifaces and filter data for
        # template processing later
        has_root = False
        for svol in self._profile.storage_volumes_rel:
            svol_dict = self._parse_svol(svol)
            if svol_dict['is_root']:
                if has_root:
                    raise ValueError(
                        'Partitioning scheme has multiple root disks defined')
                has_root = True
            info['svols'].append(svol_dict)
        if not has_root:
            raise ValueError('Partitioning scheme has no root disk defined')
        for iface in self._profile.system_ifaces_rel:
            info['ifaces'].append(self._parse_iface(
                iface, iface.osname == self._gw_iface['osname']))

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
        # try to find a template specific to this OS version
        template_filename = '{}.cmdline.jinja'.format(self._os.name)
        try:
            with open(TEMPLATES_DIR + template_filename, "r") as template_file:
                template_content = template_file.read()
        except FileNotFoundError:
            # specific template does not exist: use the distro type template
            self._logger.debug(
                "No template found for OS '%s', using generic template for "
                "type '%s'", self._os.name, self._os.type)
            template_filename = '{}.cmdline.jinja'.format(self._os.type)
            # generic template always exists, if for some reason it is not
            # there it's a server installation error which must be fixed so let
            # the exception go up
            with open(TEMPLATES_DIR + template_filename, "r") as template_file:
                template_content = template_file.read()

        template_obj = jinja2.Template(template_content)
        kargs = template_obj.render(config=self._info)
        self._logger.info('kernel cmdline for installer is: %s', kargs)

        self._platform.boot(kargs)
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
