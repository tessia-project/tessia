# Copyright 2016, 2017, 2018 IBM Corp.
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
from collections import OrderedDict
from functools import cmp_to_key
from shutil import rmtree
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from tessia.server.state_machines.autoinstall.dbcontroller import DbController
from tessia.baselib.common.ssh.client import SshClient
from tessia.server.config import Config
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from tessia.server.state_machines.autoinstall.plat_kvm import PlatKvm
from time import sleep, monotonic
from urllib.parse import urlsplit

import abc
import crypt
import ipaddress
import jinja2
import logging
import os

#
# CONSTANTS AND DEFINITIONS
#
# timeout used for ssh connection attempts
CONNECTION_TIMEOUT = 1800

# interval between ssh connection attempts
CONNECTION_RETRY_INTERVAL = 20

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
    def __init__(self, model: AutoinstallMachineModel,
                 platform: PlatBase,
                 post_install_checker=None):
        """
        Store the objects and create the right platform object
        """
        self._model = model
        self._os = model.operating_system
        self._profile = model.system_profile
        self._template = model.template
        # self._system = profile_entry.system_rel
        self._logger = logging.getLogger(__name__)

        self._gw_iface = model.system_profile._gateway

        # prepare the list of repositories
        self._repos = [model.os_repos[0]] + model.package_repos

        self._platform = platform
        self._post_install_checker = post_install_checker

        # The path and url for the auto file.
        autoinstall_config = Config.get_config().get('auto_install')
        if not autoinstall_config:
            raise RuntimeError('No auto_install configuration provided')
        autofile_name = '{}-{}'.format(self._profile.system_name,
                                       self._profile.profile_name)
        autofile_name = autofile_name.replace(' ', '-')
        self._autofile_url = '{}/{}'.format(
            autoinstall_config["url"], autofile_name)
        self._autofile_path = os.path.join(
            autoinstall_config["dir"], autofile_name)
        self._work_dir = os.getcwd()
        # set during fill_template_vars state
        self._info = None
    # __init__()

    def _get_ssh_conn(self, connect_after_install: bool = False):
        """
        Auxiliary method to get a ssh connection and shell to the target system
        being installed.

        Args:
            connect_after_install (bool): connection is made after installation
                stage

        Returns:
            SshClient: ssh connection to the target system
            SshShell: ssh shell to the target system

        Raises:
            ConnectionError: connection could not be established
        """
        # get the credentials to connect to the target system
        user, password = (self._model.os_credentials['user'],
                          self._model.os_credentials['installation-password'])
        if connect_after_install:
            password = self._model.os_credentials['password']

        def _get_shell_connection():
            """Logon to shell"""
            ssh_client = SshClient()
            ssh_client.login(self._profile.hostname,
                             user=user, passwd=password)
            ssh_shell = ssh_client.open_shell()
            return ssh_client, ssh_shell
        # _get_shell_connection()

        self._logger.info('Waiting for connection to be available (%s secs)',
                          CONNECTION_TIMEOUT)
        try:
            return self._repeat_with_timeout(_get_shell_connection)
        except TimeoutError as exc:
            raise ConnectionError(
                "Could not connect to the target system.") from exc
    # _get_ssh_conn()

    def _parse_iface(self, iface: AutoinstallMachineModel.NetworkInterface,
                     is_gateway_iface: bool):
        """
        Auxiliary method to parse the information of a network interface

        Args:
            iface: model's NetworkInterface instance.

        Returns:
            dict: a dictionary containing the parsed information.

        Raises:
            ValueError: unknown interface type
        """
        result = {"attributes": {}}
        if isinstance(iface, AutoinstallMachineModel.OsaInterface):
            result['attributes'] = {
                'ccwgroup': iface.ccwgroup,
                'layer2': iface.layer2,
                'portno': iface.portno if iface.portno is not None else '0',
                # portname is no longer used, but left for compatibility
                'portname': iface.portname if iface.portname else 'OSAPORT',
            }
            result["type"] = 'OSA'
        elif isinstance(iface, AutoinstallMachineModel.HipersocketsInterface):
            result["type"] = 'HSI'
            result['attributes'] = {
                'ccwgroup': iface.ccwgroup,
                'layer2': iface.layer2
            }
        elif isinstance(iface,
                        AutoinstallMachineModel.MacvtapLibvirtInterface):
            result["type"] = 'MACVTAP'
            result['attributes'] = {
                'libvirt': iface.libvirt
            }
        elif isinstance(iface, AutoinstallMachineModel.MacvtapHostInterface):
            result["type"] = 'MACVTAP'
            result['attributes'] = {
                'hostiface': iface.hostiface
            }
        elif isinstance(iface, AutoinstallMachineModel.RoceInterface):
            result["type"] = 'ROCE'
            result['attributes'] = {
                'fid': iface.fid
            }
        else:
            raise ValueError('Unexpected interface type {}'.format(
                iface.__class__.__qualname__))

        result["mac_addr"] = iface.mac_address
        # iface has no ip associated: set empty values
        if not iface.subnets:
            result["ip"] = None
            result["subnet"] = None
            result["mask_bits"] = None
            result["mask"] = None
            result["vlan"] = None
        else:
            # only use first available subnet by default
            subnet_model = iface.subnets[0]
            result["ip"] = str(subnet_model.ip_address)
            result["ip_type"] = ("ipv6" if isinstance(subnet_model.subnet,
                                                      ipaddress.IPv6Network)
                                 else "ipv4")
            result["subnet"] = str(subnet_model.subnet.network_address)
            result["mask"] = str(subnet_model.subnet.netmask)
            result["mask_bits"] = str(subnet_model.subnet.prefixlen)
            result["search_list"] = subnet_model.search_list
            result["vlan"] = subnet_model.vlan
            result["dns_1"], result["dns_2"] = subnet_model.dns[0:2]

        # determine whether device name must be truncated due to kernel limit
        result["osname"] = iface.os_device_name
        if result["vlan"]:
            osname_maxlen = 15 - (len(str(result["vlan"])) + 1)
            trunc_name = '{}.{}'.format(
                result["osname"][:osname_maxlen], result["vlan"])
        else:
            osname_maxlen = 15
            trunc_name = result["osname"][:osname_maxlen]
        if len(result["osname"]) > osname_maxlen:
            result["osname"] = result["osname"][:osname_maxlen]
            self._logger.warning(
                "Truncating network interface device name '%s' "
                "to '%s' to fit the 15 characters limit of the Linux kernel. "
                "Consider setting a device name for the interface within that "
                "limit.", iface.os_device_name, trunc_name)

        result["is_gateway"] = is_gateway_iface
        if is_gateway_iface:
            # gateway interface was checked in parse for ip address existence
            result["gateway"] = str(iface.gateway_subnets[0].gateway)

        return result
    # _parse_iface()

    def _parse_svol(self, storage_vol: AutoinstallMachineModel.Volume):
        """
        Auxiliary method to parse the information of a storage volume,
        (eg: type of disk, partition table, etc).

        Args:
            storage_vol: a StorageVolume instance.

        Returns:
            dict: a dictionary with all the parsed information.
        """
        # make a copy of the dicts to avoid changing the db object
        result = {}
        result["type"] = storage_vol.volume_type
        if (isinstance(storage_vol, (AutoinstallMachineModel.DasdVolume,
                                     AutoinstallMachineModel.HpavVolume,
                                     AutoinstallMachineModel.NvmeVolume))):
            result["volume_id"] = storage_vol.device_id
        elif isinstance(storage_vol, AutoinstallMachineModel.ZfcpVolume):
            result["volume_id"] = storage_vol.lun
        result["system_attributes"] = {
            "device": storage_vol.device_path
        }
        result["specs"] = {}
        if isinstance(storage_vol, AutoinstallMachineModel.ZfcpVolume):
            # compatibility layer to existing templates:
            # provide paths grouped by adapters
            adapters = {}
            for adapter, wwpn in storage_vol.paths:
                if not adapter in adapters:
                    adapters[adapter] = [wwpn]
                else:
                    adapters[adapter].append(wwpn)

            result["specs"] = {
                'adapters': [{'devno': adapter, 'wwpns': wwpns}
                             for adapter, wwpns in adapters.items()],
                'multipath': storage_vol.multipath,
                'wwid': storage_vol.wwid
            }
        if isinstance(storage_vol, AutoinstallMachineModel.NvmeVolume):
            result["specs"] = {'wwn':storage_vol.wwn}
        if not isinstance(storage_vol, AutoinstallMachineModel.HpavVolume):
            result["size"] = storage_vol.size
        result["part_table"] = None
        result["is_root"] = False

        if storage_vol.partitions:
            result['part_table'] = {'type': storage_vol.partition_table_type}
            result['part_table']['table'] = [
                {
                    'mp': partition.mount_point,
                    'size': partition.size,
                    'fs': partition.filesystem,
                    'type': partition.part_type,
                    'mo': partition.mount_opts,
                } for partition in storage_vol.partitions
            ]

        try:
            part_table = result["part_table"]["table"]
        except (TypeError, KeyError):
            # no partition table, nothing more to do
            return result

        scheme_size = 0
        for entry in part_table:
            scheme_size += entry['size']
            if entry["mp"] == "/":
                result["is_root"] = True
        # partitions use the whole disk: distro installers begin creating
        # partitions at 1 so we remove 1 from the end to make sure the scheme
        # fits
        if scheme_size == result['size']:
            result['part_table']['table'][-1]['size'] -= 1
        elif scheme_size > result['size']:
            self._logger.warning(
                "Partition table for device '%s' is larger than device size. "
                "This may cause installation to fail. Please update device "
                "size or partition table acordingly", result['volume_id']
            )

        return result
    # _parse_svol()

    def _remove_autofile(self):
        """
        Remove an autofile
        """
        if os.path.exists(self._autofile_path):
            try:
                if os.path.isdir(self._autofile_path):
                    rmtree(self._autofile_path)
                else:
                    os.remove(self._autofile_path)
            except OSError:
                raise RuntimeError("Unable to delete the autofile during"
                                   " cleanup.")
    # _remove_autofile()

    def _render_installer_cmdline(self):
        """
        Returns installer kernel command line from the template
        """
        template_obj = jinja2.Template(self._model.installer_template.content)
        return template_obj.render(config=self._info).strip()
    # _render_installer_cmdline()

    def _repeat_with_timeout(self, conn_method):
        """
        Try several times to establish a connection

        Args:
            conn_method (callable): method that potentially makes a connection

        Returns:
            any: result of the connection method

        Raises:
            TimeoutError: connection method fails after several attempts
        """
        conn_timeout = monotonic() + CONNECTION_TIMEOUT
        max_attempts = CONNECTION_TIMEOUT // CONNECTION_RETRY_INTERVAL
        for attempt in range(1, 1 + max_attempts):
            # there will likely be fewer attempts due to timing overhead
            self._logger.info('Connection attempt %d', attempt)
            attempt_start = monotonic()
            try:
                return conn_method()
            # different errors can happen depending on the state of the
            # target system, so we just catch them all and try again until
            # system is stable
            except Exception as exc:
                attempt_end = monotonic()
                if attempt_end >= conn_timeout:
                    raise TimeoutError("No connection after"
                                       f" {attempt} attempts") from exc

                duration = attempt_end - attempt_start
                # sleep through part of retry interval
                # with some guaranteed sleep time
                sleep(max(CONNECTION_RETRY_INTERVAL / 4,
                          CONNECTION_RETRY_INTERVAL - duration))

        raise TimeoutError(f"No connection after {max_attempts} attempts")
    # _repeat_with_timeout()

    @property
    @classmethod
    @abc.abstractmethod
    def DISTRO_TYPE(cls):  # pylint: disable=invalid-name
        """
        Return the type of linux distribution supported. The entry should match
        the column 'type' in the operating_systems table.
        """
        raise NotImplementedError()
    # DISTRO_TYPE

    def boot_installer(self):
        """
        Performs the boot of the target system to initiate the installation
        """
        self._logger.debug("Auto-generated installation password: %s",
                           self._info['credentials']['installation-password'])

        kargs = self._render_installer_cmdline()
        if self._model.installer_cmdline:
            custom_kargs = self._model.installer_cmdline
            # below we use a dict to remove duplicated parameters, the code
            # assumes no kernel params have empty spaces as values
            # (i.e. param="foo bar") so if this is ever to be supported
            # the implementation below needs to be improved
            kargs_dict = OrderedDict()
            for param in kargs.split() + custom_kargs.split():
                try:
                    name, value = param.split('=', 1)
                except ValueError:
                    name, value = param, None
                kargs_dict[name] = value
            custom_kargs = []
            for name, value in kargs_dict.items():
                if value is None:
                    custom_kargs.append(name)
                else:
                    custom_kargs.append('{}={}'.format(name, value))
            kargs = ' '.join(custom_kargs)
        self._logger.info('kernel cmdline for installer is: %s', kargs)

        self._platform.start_installer(kargs)
    # boot_installer()

    def check_installation(self):
        """
        Make sure that the installation was successfully completed.
        """
        if not self._post_install_checker:
            self._logger.info("Skipping post-installation checks")
            return

        def _fail_check(exception: Exception):
            """
            Inform about a failed check

            Depending on post install checker settings, we may want to
            continue with the installation process or raise an exception.
            """
            if self._post_install_checker.permissive:
                self._logger.warning(
                    "Post-installation check failed: %s", exception)
            else:
                raise exception
        # _fail_check()

        # make sure a connection is possible before we use the checker
        ssh_client, shell = self._get_ssh_conn(connect_after_install=True)

        ret, _ = shell.run("echo 1")
        if ret != 0:
            _fail_check(
                RuntimeError("Error while checking the installed system.")
            )
            return

        shell.close()
        ssh_client.logoff()

        self._logger.info(
            "Verifying if installed system matches expected parameters")
        # with certain distros the connection comes up and down during the
        # boot process so we perform multiple tries until we get a connection
        try:
            self._repeat_with_timeout(self._post_install_checker.verify)
        except TimeoutError as exc:
            _fail_check(exc)

    # check_installation()

    def cleanup(self):
        """
        Called upon job cancellation or end. Deletes the autofile if it exists.

        Do not call this method directly but indirectly from machine.py to make
        sure that the cleaning_up variable is set.
        """
        self._remove_autofile()
    # cleanup()

    def create_autofile(self):
        """
        Fill the template and create the autofile in the target location
        """
        self._logger.info("generating autofile")
        self._remove_autofile()
        template = jinja2.Template(self._template.content)
        self._logger.info(
            "autotemplate will be used: '%s'", self._template.name)

        autofile_content = template.render(config=self._info)

        # Write the autofile for usage during installation
        # by the distro installer.
        with open(self._autofile_path, "w", encoding='utf-8') as autofile:
            autofile.write(autofile_content)
        # Write the autofile in the directory that the state machine
        # is executed.
        with open(os.path.join(self._work_dir, os.path.basename(
                self._autofile_path)), "w", encoding='utf-8') as autofile:
            autofile.write(autofile_content)
    # create_autofile()

    def fill_template_vars(self):
        """
        Prepare all necessary information for the template rendering by
        populating the self._info dict. Can be implemented by children classes.
        """
        info = {
            'ifaces': [],
            'svols': [],
            'repos': [],
            'server_hostname': urlsplit(self._autofile_url).hostname,
            'system_type': self._profile.system_type.name,
            'credentials': {
                'admin-user': self._model.os_credentials['user'],
                'admin-password': self._model.os_credentials['password'],
                'installation-password': self._model.os_credentials[
                    'installation-password']
            },
            'sha512rootpwd': (crypt.crypt(
                self._model.os_credentials["password"])),
            'sha512installpwd': (crypt.crypt(
                self._model.os_credentials["installation-password"])),
            'hostname': self._profile.hostname,
            'autofile': self._autofile_url,
            'operating_system': {
                'major': self._os.major,
                'minor': self._os.minor,
                'pretty_name': self._os.pretty_name,
            },
            'profile_parameters': {}
        }
        if self._model.installer_cmdline:
            info['profile_parameters']['linux-kargs-installer'] = \
                self._model.target_cmdline
        if self._model.target_cmdline:
            info['profile_parameters']['linux-kargs-target'] = \
                self._model.target_cmdline

        # add repo entries
        for repo_obj in self._repos:
            repo = {
                'url': repo_obj.url,
                'desc': repo_obj.desc,
                'name': repo_obj.name.replace(' ', '_'),
                'os': ''
            }
            if not repo['desc']:
                repo['desc'] = repo['name']

            if isinstance(repo_obj, AutoinstallMachineModel.OsRepository):
                repo.update({
                    'os': repo_obj.installable_os,
                    'install_image': repo_obj.install_image,
                })
            info['repos'].append(repo)

        # iterate over all available volumes and ifaces and filter data for
        # template processing later
        info['svols'] = [self._parse_svol(svol)
                         for svol in self._profile.volumes]

        num_roots = sum([vol['is_root'] for vol in info['svols']])
        if num_roots < 1:
            raise ValueError('Partitioning scheme has no root disk defined')
        if num_roots > 1:
            raise ValueError(
                'Partitioning scheme has multiple root disks defined')

        # make sure hpav aliases come after dasds so that the templates always
        # activate the base devices first

        def compare(item_1, item_2):
            """Helper to sort hpav as last"""
            if (item_1['type'] == 'HPAV' or
                    item_1['type'] > item_2['type']):
                return 1
            if item_1['type'] == item_2['type']:
                return 0
            return -1
        # compare()
        info['svols'].sort(key=cmp_to_key(compare))

        for iface in self._profile.ifaces:
            is_gateway = (iface == self._profile.gateway_interface)
            info['ifaces'].append(self._parse_iface(iface, is_gateway))
            if is_gateway:
                info['gw_iface'] = info['ifaces'][-1]

        self._info = info
    # fill_template_vars()

    def init_target(self):
        """
        Initialize target machine (configure, activate etc.)
        without booting into installer
        """
        self._platform.prepare_guest()
    # init_target()

    def persist_init_data(self, dbctrl: DbController):
        """
        Store model changes if necessary. Called after initialization

        Args:
            dbctrl: database controller
        """
        if isinstance(self._platform, PlatKvm):
            # KVM needs to store device paths and libvirt configuration
            num_update_volumes = dbctrl.update_libvirt_on_volume(
                self._model, self._profile.volumes)
            self._logger.debug("Updated libvirt definitions on %d volumes",
                               num_update_volumes)
            for volume_model in self._profile.volumes:
                self._logger.debug("system_attributes: %s",
                                   volume_model.libvirt_definition)
    # persist_init_data()

    def post_install(self):
        """
        Perform post installation activities.
        """
    # post_install()

    def target_reboot(self):
        """
        Performs a reboot of the target system after installation is done
        """
        # set boot device to the boot device from used profile
        self._platform.set_boot_device(self._profile.get_boot_device())

        # reboot the system
        self._platform.reboot()
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
        self._logger.info('new state: init_target')
        self.init_target()

        self._logger.info('new state: fill_template_vars')
        self.fill_template_vars()

        self._logger.info('new state: create_autofile')
        self.create_autofile()

        self._logger.info('new state: boot_installer')
        self.boot_installer()

        self._logger.info('new state: wait_install')
        self.wait_install()

        self._logger.info('new state: target_reboot')
        self.target_reboot()

        self._logger.info('new state: check_installation')
        self.check_installation()

        self._logger.info('new state: post_install')
        self.post_install()

        self._logger.info('Installation finished successfully')
    # start()
# SmBase
