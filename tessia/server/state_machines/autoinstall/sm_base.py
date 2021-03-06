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
from copy import deepcopy
from datetime import datetime
from functools import cmp_to_key
from shutil import rmtree
from socket import gethostbyname
from tessia.baselib.common.ssh.client import SshClient
from tessia.server.config import Config
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import Repository, System, SystemProfile
from tessia.server.lib.post_install import PostInstallChecker
from tessia.server.state_machines.autoinstall.plat_lpar import PlatLpar
from tessia.server.state_machines.autoinstall.plat_kvm import PlatKvm
from tessia.server.state_machines.autoinstall.plat_zvm import PlatZvm
from time import sleep
from time import time
from urllib.parse import urlsplit

import abc
import crypt
import ipaddress
import jinja2
import logging
import os
import random
import re
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
    def __init__(self, os_entry, profile_entry, template_entry,
                 custom_repos=None):
        """
        Store the objects and create the right platform object
        """
        self._os = os_entry
        self._profile = profile_entry
        self._template = template_entry
        self._system = profile_entry.system_rel
        self._logger = logging.getLogger(__name__)

        self._gw_iface = self._get_gw_iface()

        # prepare the list of repositories
        self._repos = self._get_repos(custom_repos)

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
            self._repos[0],
            self._gw_iface)

        # The path and url for the auto file.
        autoinstall_config = Config.get_config().get('auto_install')
        if not autoinstall_config:
            raise RuntimeError('No auto_install configuration provided')
        autofile_name = '{}-{}'.format(self._system.name, self._profile.name)
        autofile_name = autofile_name.replace(' ', '-')
        self._autofile_url = '{}/{}'.format(
            autoinstall_config["url"], autofile_name)
        self._autofile_path = os.path.join(
            autoinstall_config["dir"], autofile_name)
        # set during collect_info state
        self._info = None
    # __init__()

    def _get_gw_iface(self):
        """
        Return the gateway interface object assigned to this installation
        """
        gw_iface = self._profile.gateway_rel
        # gateway interface not defined: use first available
        if gw_iface is None:
            try:
                gw_iface = self._profile.system_ifaces_rel[0]
            except IndexError:
                msg = 'No network interface attached to perform installation'
                raise RuntimeError(msg)
        return gw_iface
    # _get_gw_iface()

    def _get_repos(self, custom_repos):
        """
        Prepare the list of repositories to be used for the installation.

        Args:
            custom_repos (list): user defined repositories

        Returns:
            list: list of repository db objects

        Raises:
            ValueError: in case user specified a repo which doesn't exist
            RuntimeError: if no install repository is available for the OS
        """
        if not custom_repos:
            custom_repos = []

        repos = []
        # after processing we must have the repo to use during installation
        install_repo = None
        # check the repositories specified by the user
        for repo_entry in custom_repos:
            repo_obj = None
            for scheme in ('http', 'https', 'ftp', 'file'):
                if not repo_entry.startswith('{}://'.format(scheme)):
                    continue
                try:
                    urlsplit(repo_entry).hostname
                except Exception:
                    raise ValueError(
                        'Repository <{}> specified by user is not a valid URL'
                        .format(repo_entry))
                # sanitize to avoid invalid syntax problems with distro package
                # managers
                repo_name = re.sub('[^a-zA-Z0-9]', '_', repo_entry)
                repo_obj = Repository(
                    name=repo_name,
                    desc='User defined repo {}'.format(repo_name),
                    url=repo_entry,
                    owner='admin', project='Admins', modifier='admin'
                )
                repos.append(repo_obj)
                break
            # entry was a url: there's no need to query the db
            if repo_obj:
                continue

            # see if name refers to a registered repository
            repo_obj = Repository.query.filter_by(name=repo_entry).first()
            if not repo_obj:
                raise ValueError(
                    "Repository <{}> specified by user does not exist"
                    .format(repo_entry))
            # user specified an install repository: use it
            if repo_obj.operating_system_rel == self._os:
                install_repo = repo_obj
            # package repository: don't use for installation, just add to the
            # list
            else:
                repos.append(repo_obj)
        # no install repo defined by user: try to find one automatically
        if not install_repo:
            # no install repos available for this os: abort, can't install
            if not self._os.repository_rel:
                raise RuntimeError(
                    'No install repository available for the specified OS')

            # preferably use a repository in the same subnet as the system
            for repo_obj in self._os.repository_rel:
                try:
                    repo_addr = gethostbyname(
                        urlsplit(repo_obj.url).netloc.rsplit('@', 1)[-1])
                    address_pyobj = ipaddress.ip_address(repo_addr)
                # can't resolve repo's hostname: skip it
                except Exception:
                    continue
                for iface_obj in self._profile.system_ifaces_rel:
                    # no ip assigned: skip iface
                    if not iface_obj.ip_address_rel:
                        continue
                    subnet_pyobj = ipaddress.ip_network(
                        iface_obj.ip_address_rel.subnet_rel.address,
                        strict=True)
                    # ip assigned to iface is in same subnet as repo's
                    # hostname: use this repo as install media
                    if address_pyobj in subnet_pyobj:
                        install_repo = repo_obj
                        break
                if install_repo:
                    break
            # no repo in same subnet as system's interfaces: simply use first
            # in the list
            if not install_repo:
                install_repo = self._os.repository_rel[0]

        # install repo is the first entry in the repo list
        repos.insert(0, install_repo)

        return repos
    # _get_repos()

    def _get_ssh_conn(self):
        """
        Auxiliary method to get a ssh connection and shell to the target system
        being installed.
        """
        hostname = self._profile.system_rel.hostname
        user = self._profile.credentials['admin-user']
        password = self._profile.credentials['admin-password']

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

    def _parse_iface(self, iface, gateway_iface):
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
            result["vlan"] = None
        else:
            subnet_pyobj = ipaddress.ip_network(
                iface.ip_address_rel.subnet_rel.address, strict=True)
            result["ip"] = iface.ip_address_rel.address
            result["ip_type"] = (
                "ipv6" if isinstance(subnet_pyobj, ipaddress.IPv6Network)
                else "ipv4")
            result["subnet"] = str(subnet_pyobj.network_address)
            result["mask"] = str(subnet_pyobj.netmask)
            result["mask_bits"] = str(subnet_pyobj.prefixlen)
            result["search_list"] = iface.ip_address_rel.subnet_rel.search_list
            result["vlan"] = iface.ip_address_rel.subnet_rel.vlan
            result["dns_1"] = iface.ip_address_rel.subnet_rel.dns_1
            result["dns_2"] = iface.ip_address_rel.subnet_rel.dns_2

        # determine whether device name must be truncated due to kernel limit
        result["osname"] = iface.osname
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
                "Truncating device name of network interface '%s' from '%s' "
                "to '%s' to fit the 15 characters limit of the Linux kernel. "
                "Consider setting a device name for the interface within that "
                "limit.", iface.name, iface.osname, trunc_name)

        result["is_gateway"] = gateway_iface
        if gateway_iface:
            # gateway interface was checked in parse for ip address existence
            result["gateway"] = iface.ip_address_rel.subnet_rel.gateway

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
        # make a copy of the dicts to avoid changing the db object
        result = {}
        result["type"] = storage_vol.type_rel.name
        result["volume_id"] = storage_vol.volume_id
        result["server"] = storage_vol.server
        result["system_attributes"] = deepcopy(storage_vol.system_attributes)
        result["specs"] = deepcopy(storage_vol.specs)
        result["size"] = storage_vol.size
        result["part_table"] = deepcopy(storage_vol.part_table)
        result["is_root"] = False

        # device path not user-defined: determine it based on the platform
        if "device" not in result["system_attributes"]:
            result["system_attributes"]["device"] = \
                self._platform.get_vol_devpath(storage_vol)

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
        return template_obj.render(config=self._info).strip()

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

        self._logger.info(
            "Verifying if installed system matches expected parameters")
        # with certain distros the connection comes up and down during the
        # boot process so we perform multiple tries until we get a connection
        conn_timeout = time() + CONNECTION_TIMEOUT
        while True:
            try:
                checker = PostInstallChecker(
                    self._profile, self._os, permissive=True)
                checker.verify()
            except ConnectionError:
                if time() > conn_timeout:
                    raise ConnectionError('Timeout occurred while trying to '
                                          'connect to target system')
                self._logger.debug('post install failed:', exc_info=True)
                sleep(5)
                continue
            break
    # check_installation()

    def cleanup(self):
        """
        Called upon job cancellation or end. Deletes the autofile if it exists.

        Do not call this method directly but indirectly from machine.py to make
        sure that the cleaning_up variable is set.
        """
        self._remove_autofile()
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
            'sha512rootpwd': (
                crypt.crypt(self._profile.credentials["admin-password"])),
            'hostname': self._system.hostname,
            'autofile': self._autofile_url,
            'operating_system': {
                'major': self._os.major,
                'minor': self._os.minor,
                'pretty_name': self._os.pretty_name,
            },
            'profile_parameters': self._profile.parameters,
        }
        # add repo entries
        for repo_obj in self._repos:
            repo = {
                'url': repo_obj.url, 'desc': repo_obj.desc,
                'name': repo_obj.name.replace(' ', '_'),
                'os': repo_obj.operating_system,
                'install_image': repo_obj.install_image,
            }
            if not repo['desc']:
                repo['desc'] = repo['name']
            info['repos'].append(repo)

        # generate pseudo-random password for vnc session
        info['credentials']['vnc-password'] = ''.join(
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
        # make sure hpav aliases come after dasds so that the templates always
        # activate the base devices first

        def compare(item_1, item_2):
            """Helper to sort hpav as last"""
            if item_1['type'] == 'HPAV' or item_1['type'] > item_2['type']:
                return 1
            if item_1['type'] == item_2['type']:
                return 0
            return -1
        # compare()
        info['svols'].sort(key=cmp_to_key(compare))

        for iface in self._profile.system_ifaces_rel:
            info['ifaces'].append(self._parse_iface(
                iface, iface == self._gw_iface))
            if info['ifaces'][-1]['is_gateway']:
                info['gw_iface'] = info['ifaces'][-1]

        self._info = info
    # collect_info()

    def create_autofile(self):
        """
        Fill the template and create the autofile in the target location
        """
        self._logger.info("generating autofile")
        self._remove_autofile()
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
        self._system.modified = datetime.utcnow()
        MANAGER.session.commit()
    # post_install()

    def target_boot(self):
        """
        Performs the boot of the target system to initiate the installation
        """
        kargs = self._render_installer_cmdline()
        if self._profile.parameters and (
                self._profile.parameters.get('linux-kargs-installer')):
            custom_kargs = self._profile.parameters['linux-kargs-installer']
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
                elif name.startswith("tessia_option"):
                    pass
                else:
                    custom_kargs.append('{}={}'.format(name, value))
            kargs = ' '.join(custom_kargs)
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
