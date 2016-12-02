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
from socket import inet_ntoa
from sqlalchemy.orm.exc import NoResultFound
from tessia_engine.config import Config
from tessia_engine.db.models import SystemIface
from tessia_engine.state_machines.install.plat_lpar import PlatLpar
from tessia_engine.state_machines.install.plat_kvm import PlatKvm

import abc
import jinja2
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
        self._template = profile_entry
        self._system = profile_entry.system_rel

        # the network iface used as gateway
        # TODO: check gateway_iface early (before job is started)
        try:
            gw_iface = SystemIface.query.filter_by(
                system_id=self._system.id,
                name=self._profile.parameters['gateway_iface'],
            ).one()
        except KeyError:
            raise RuntimeError('No gateway interface defined for profile')
        except NoResultFound:
            msg = 'Gateway interface {} does not exist'.format(
                self._profile.parameters['gateway_iface'])
            raise RuntimeError(msg)
        if gw_iface is None:
            raise RuntimeError(
                'System has no gateway network interface configured')
        self._gw_iface = self._parse_iface(gw_iface, True)

        # create the appropriate platform object according to the system being
        # installed
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
            self._gw_iface)

        # the path and url for the auto file
        config = Config.get_config()
        autofile_name = '{}-{}'.format(self._system.name, self._profile.name)
        self._autofile_url = (config.get("install_machine").get("url") + "/"
                              + autofile_name)
        self._autofile_path = (config.get("install_machine").get("www_dir")
                               + "/" + autofile_name)

        # set during collect_info state
        self._info = None
    # __init__()

    def _get_kargs(self): # pylint: disable=no-self-use
        """
        Return the cmdline used for the os installer

        Returns:
            str: kernel cmdline string
        """
        return ''
    # _get_kargs()

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
        result["ip"] = iface.ip_address_rel.address
        cidr_addr = iface.ip_address_rel.subnet_rel.address
        result["subnet"], cidr_prefix = cidr_addr.split("/")
        # We need to convert the network mask from the cidr prefix format
        # to an ip mask format.
        result["mask"] = inet_ntoa(
            ((0xffffffff << (32 - int(cidr_prefix)))
             & 0xffffffff).to_bytes(4, byteorder="big")
        )
        result["osname"] = iface.osname
        result["is_gateway"] = gateway_iface
        if gateway_iface:
            result["gateway"] = iface.ip_address_rel.subnet_rel.gateway
            result["dns_1"] = iface.ip_address_rel.subnet_rel.dns_1
            result["dns_2"] = iface.ip_address_rel.subnet_rel.dns_2

        return result
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
        result = {}
        # TODO: remove the following remap between the Information in the
        # tessia-engine database and the tessia_baselib.
        remap = {"ECKD": "DASD", "SCSI": "SCSI"}

        disk_type = storage_vol.type_rel.name
        result["disk_type"] = remap[disk_type]
        result["volume_id"] = storage_vol.volume_id
        result["system_attributes"] = storage_vol.system_attributes
        result["specs"] = storage_vol.specs

        result["part_table"] = storage_vol.part_table
        result["is_root"] = False
        for entry in result["part_table"]["table"]:
            if entry["mp"] == "/":
                result["is_root"] = True
                break

        return result
    # _parse_svol()

    def init(self):
        """
        Initialization, currently is nop
        """
        pass
    # init()

    def cleanup(self):
        """
        Called upon job cancellation or end. Deletes the autofile if it exists.
        """
        if os.path.exists(self._autofile_path):
            try:
                os.remove(self._autofile_path)
            except OSError:
                print("warning: unable to delete the autofile during cleanup.")
                return 1
        return 0
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
        }

        # iterate over all available volumes and ifaces and filter data for
        # template processing later
        for svol in self._profile.storage_volumes_rel:
            info['svols'].append(self._parse_svol(svol))
        for iface in self._profile.system_ifaces_rel:
            info['ifaces'].append(self._parse_iface(
                iface, iface.osname is self._gw_iface['osname']))

        # TODO: allow usage of additional repositories
        repo_url = self._profile.operating_system_rel.repository_rel.url
        info['repos'].append(repo_url)

        self._info = info
    # collect_info()

    def create_autofile(self):
        """
        Fill the template and create the autofile in the target location
        """
        print("info: generating autofile")
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

    def target_boot(self):
        """
        Performs the boot of the target system to initiate the installation
        """
        self._platform.target_boot(
            self._profile, self._os, self._get_kargs())
    # target_boot()

    def target_reboot(self):
        """
        Performs a reboot of the target system after installation is done
        """
        self._platform.target_reboot(self._profile)
    # target_reboot()

    def wait_install(self):
        """
        Each system has its heuristic to follow the installation progress and
        determine when it's done therefore this function should be implemented
        by children classes.
        """
        pass
    # wait_install()

    def start(self):
        """
        Start the states' transition.
        """
        print('new state: init')
        self.init()

        print('new state: collect_info')
        self.collect_info()

        print('new state: create_autofile')
        self.create_autofile()

        print('new state: target_boot')
        self.target_boot()

        print('new state: wait_install')
        self.wait_install()

        print('new state: target_reboot')
        self.target_reboot()

        print('new state: cleanup')
        self.cleanup()
    # start()
