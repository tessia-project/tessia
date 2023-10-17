# Copyright 2021 IBM Corp.
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
Autoinstall machine model

Data that is used during automatic installation is represented in this model.

Code using the model should follow the convention:
- all reads can be done from public members
- all changes are made through method calls

For all fields a value of None means field is unset,
and its handling is defined by implementation.

Validation shall check if the model is consistent and all required fields
are present
"""

#
# IMPORTS
#
from enum import Enum
import ipaddress


#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


class AutoinstallMachineModel:
    """
    Data model for autoinstall machine
    """
    class Template:
        """
        Template model
        """

        def __init__(self, name: str, content: str):
            self.name = name
            self.content = content

    class OperatingSystem:
        """
        OperatingSystem model
        """

        def __init__(self, name: str, _type: str, major: int, minor: int,
                     pretty_name: str, template_name: str):
            self.name = name
            self.type = _type
            self.major = major
            self.minor = minor
            self.pretty_name = pretty_name
            self.template_name = template_name

        def __repr__(self):
            return "OperatingSystem<{}>".format(self.name)

    class OsRepository:
        """
        OsRepository model
        """

        def __init__(self, name: str, url: str, kernel: str, initrd: str,
                     install_image: str, installable_os: str,
                     description: str):
            self.name = name
            self.url = url
            self.kernel = kernel
            self.initrd = initrd
            self.install_image = install_image
            self.installable_os = installable_os
            self.desc = description

        def __repr__(self):
            return "OsRepository<{}>".format(self.name)

    class PackageRepository:
        """
        PackageRepository model
        """

        def __init__(self, name: str, url: str,
                     description: str):
            self.name = name
            self.url = url
            self.desc = description

        def __repr__(self):
            return "PackageRepository<{}>".format(self.name)

    class Volume:
        """
        Volume representation
        """

        class Partition:
            """
            Partition table entry
            """

            def __init__(self, mount_point: str, size: int, filesystem: str,
                         part_type: str, mount_opts: str):
                self.mount_point = mount_point
                self.size = size
                self.filesystem = filesystem
                self.part_type = part_type
                self.mount_opts = mount_opts

        def __init__(self, device_path: str = None):
            self.partition_table_type = 'gpt'
            self.partitions = []
            self._libvirt_definition = ''
            self._device_path = device_path

        def set_partitions(self, part_type: str, part_table: "list[dict]"):
            """
            Set partition information
            """
            self.partition_table_type = part_type
            self.partitions = [self.Partition(**entry) for entry in part_table]

        @property
        def libvirt_definition(self):
            """
            libvirt definition
            """
            return self._libvirt_definition

        @libvirt_definition.setter
        def libvirt_definition(self, libvirt: str):
            """
            Set libvirt definition
            """
            self._libvirt_definition = libvirt

        @property
        def volume_type(self):
            """
            Volume type (override in specializations)
            """
            return 'UNKNOWN'

        @property
        def device_path(self):
            """
            Device path on target machine
            """
            return self._device_path

        @device_path.setter
        def device_path(self, value):
            """
            Set device path on target machine
            """
            self._device_path = value

    class DasdVolume(Volume):
        """
        DASD volume
        """

        def __init__(self, device_id: str, size: int, **kwargs):
            super().__init__(**kwargs)
            self.device_id = device_id
            self.size = size
            if not self.device_path:
                if device_id.find('.') < 0:
                    device_id = '0.0.' + device_id
                self.device_path = '/dev/disk/by-path/ccw-{}'.format(device_id)

        @property
        def volume_type(self):
            return 'DASD'

        def __repr__(self):
            return "DasdVolume<{}>".format(self.device_id)

        def __str__(self):
            return "DasdVolume<{}>".format(self.device_id)

    class HpavVolume(Volume):
        """
        HPAV volume or alias
        """

        def __init__(self, device_id: str, **kwargs):
            super().__init__(**kwargs)
            self.device_id = device_id
            if not self.device_path:
                if device_id.find('.') < 0:
                    device_id = '0.0.' + device_id
                self.device_path = '/dev/disk/by-path/ccw-{}'.format(device_id)

        @property
        def volume_type(self):
            return 'HPAV'

        def __repr__(self):
            return "HpavVolume<{}>".format(self.device_id)

        def __str__(self):
            return "HpavVolume<{}>".format(self.device_id)

    class ZfcpVolume(Volume):
        """
        zFCP volume
        """

        def __init__(self, lun: str, size: int, multipath: bool,
                     wwid: str, **kwargs):
            super().__init__(**kwargs)
            self.lun = lun.lower()
            self.size = size
            self.multipath = multipath
            self.paths = []
            self.wwid = wwid.lower()

            if not self.device_path:
                if self.multipath:
                    self.device_path = (
                        '/dev/disk/by-id/dm-uuid-mpath-{}'.format(
                            self.wwid))
                else:
                    self.device_path = (
                        '/dev/disk/by-id/scsi-{}'.format(
                            self.wwid))

        def add_path(self, adapter: str, wwpn: str):
            """
            Add a single FCP path
            """
            self.paths.append((adapter, wwpn))

        def create_paths(self, adapters: "list[str]", wwpns: "list[str]"):
            """
            Generate paths by connecting every wwpn to every adapter
            """
            for adapter in adapters:
                for wwpn in wwpns:
                    self.add_path(adapter, wwpn)

        @property
        def uuid(self):
            """
            UUID from WWID
            """
            return self.wwid[1:]

        @property
        def volume_type(self):
            """
            Static volume type
            """
            return 'FCP'

        def __repr__(self):
            return "ZfcpVolume<{}>".format(self.lun)

        def __str__(self):
            return "ZfcpVolume<{}>".format(self.lun)

    class NvmeVolume(Volume):
        """
        NVMe volume
        """

        def __init__(self, device_id: str, size: int,
                    wwn: str, **kwargs):
            super().__init__(**kwargs)
            self.device_id = device_id.lower()
            self.size = size
            self.wwn = wwn.lower()

            if not self.device_path:
                self.device_path = (
                    '/dev/disk/by-id/nvme-eui.{}'.format(
                        self.wwn))

        @property
        def uuid(self):
            """
            UUID from device_id
            """
            return self.device_id

        @property
        def volume_type(self):
            """
            Static volume type
            """
            return 'NVME'

        def __repr__(self):
            return "NVMEVolume<{}>".format(self.device_id)

        def __str__(self):
            return "NVMEVolume<{}>".format(self.device_id)

    class SubnetAffiliation:
        """
        IP address representation
        """

        def __init__(self, ip_address: str, subnet: str,
                     gateway: str = '',
                     vlan: int = 0,
                     dns: "list[str]" = None,
                     search_list: str = None):
            self.ip_address = ipaddress.ip_address(ip_address)
            self.subnet = ipaddress.ip_network(subnet)
            self.vlan = vlan
            self.gateway = gateway
            self.dns = (dns + [''])[0:2] if dns else ['', '']
            self.search_list = search_list

    class NetworkInterface:
        """
        Network interface representation
        """

        def __init__(self, os_device_name: str, mac_address: str = None,
                     subnets: 'list[SubnetAffiliation]' = None):
            """
            Basic network interface properties
            """
            self.os_device_name = os_device_name
            self.mac_address = mac_address
            self.subnets = []

            if subnets:
                for subnet in subnets:
                    self.add_to_subnet(subnet)

        def add_to_subnet(self, subnet_properties: 'SubnetAffiliation'):
            """
            Assign a network address
            """
            self.subnets.append(subnet_properties)

        @property
        def gateway_subnets(self) -> "list[SubnetAffiliation]":
            """
            Return list of subnets that have gateway route
            """
            return [subnet for subnet in self.subnets
                    if subnet.gateway and subnet.ip_address]

        def validate(self):
            """
            Internal state validation
            """

    class OsaInterface(NetworkInterface):
        """
        OSA interface
        """

        def __init__(self, ccwgroup: str, layer2: bool, portno: int = None,
                     portname: str = None, **kwargs):
            """
            OSA + basic network interface properties
            """
            super().__init__(**kwargs)
            self.ccwgroup = ccwgroup
            self.layer2 = layer2
            self.portno = portno
            self.portname = portname

        def validate(self):
            """
            Internal state validation
            """
            if not self.layer2 and self.mac_address:
                raise ValueError(
                    'When layer2 is off no MAC address should be defined')

    class HipersocketsInterface(NetworkInterface):
        """
        Hipersockets interface
        """

        def __init__(self, ccwgroup: str, layer2: bool, **kwargs):
            """
            HSI + basic network interface properties
            """
            super().__init__(**kwargs)
            self.ccwgroup = ccwgroup
            self.layer2 = layer2

        def validate(self):
            """
            Internal state validation
            """
            if not self.layer2 and self.mac_address:
                raise ValueError(
                    'When layer2 is off no MAC address should be defined')

    class MacvtapLibvirtInterface(NetworkInterface):
        """
        MACVTAP with libvirt
        """

        def __init__(self, libvirt_definition: str, **kwargs):
            """
            Macvtap + basic network interface properties
            """
            super().__init__(**kwargs)
            self.libvirt = libvirt_definition

        def validate(self):
            """
            Internal state validation
            """
            if not self.mac_address:
                raise ValueError('A MAC address must be defined')

    class MacvtapHostInterface(NetworkInterface):
        """
        MACVTAP without libvirt
        """

        def __init__(self, hostiface: str, **kwargs):
            """
            Macvtap + basic network interface properties
            """
            super().__init__(**kwargs)
            self.hostiface = hostiface

        def validate(self):
            """
            Internal state validation
            """
            if not self.mac_address:
                raise ValueError('A MAC address must be defined')

    class RoceInterface(NetworkInterface):
        """
        RoCE card
        """

        def __init__(self, pci_fid: str, **kwargs):
            """
            RoCE + basic network interface properties
            """
            super().__init__(**kwargs)
            self.fid = pci_fid

        def validate(self):
            """
            Internal state validation
            """
            if not self.mac_address:
                raise ValueError('A MAC address must be defined')

    class SystemHypervisor:
        """
        Hypervisor for a system
        """

        def __init__(self, name: str):
            self.name = name

        def validate(self):
            """
            Check hypervisor model parameters
            """

    class HmcHypervisor(SystemHypervisor):
        """
        HMC
        """

        def __init__(self, name: str,
                     hmc_address: str, credentials: dict,
                     boot_options: dict):
            super().__init__(name)
            self.hmc_address = hmc_address
            self.credentials = credentials
            self.boot_options = boot_options

        def validate(self):
            """
            Check hypervisor model parameters
            """
            if not self.hmc_address:
                raise ValueError("No HMC address provided")
            if (not self.credentials['user']
                    or not self.credentials['password']):
                raise ValueError(
                    "No CPC credentials set. Please provide 'admin-user' and "
                    "'admin-password' in hypervisor profile")
            if not self.boot_options:
                raise ValueError(
                    "No CPC boot method configured. Please set "
                    "'liveimg-insfile-url' in CPC profile parameters or "
                    "attach a volume with live image")

    class ZvmHypervisor(SystemHypervisor):
        """
        ZVM
        """

        def __init__(self, name: str,
                     zvm_address: str, credentials: dict,
                     connection_paramters: dict):
            super().__init__(name)
            self.zvm_address = zvm_address
            self.credentials = credentials
            self.connection_parameters = connection_paramters

        def validate(self):
            """
            Check hypervisor model parameters
            """
            if not self.credentials['password']:
                raise ValueError(
                    'An empty z/VM guest password is trying to be used. '
                    'Please set the correct password.')

    class KvmHypervisor(SystemHypervisor):
        """
        KVM
        """

        def __init__(self, name: str,
                     kvm_host: str, credentials: dict):
            super().__init__(name)
            self.kvm_host = kvm_host
            self.credentials = credentials

    class SystemProfile:
        """
        System profile representation
        """
        SystemTypes = Enum('SystemTypes', 'LPAR ZVM KVM GENERIC')

        def __init__(self, system_name: str, profile_name: str,
                     hypervisor: 'SystemHypervisor',
                     hostname: str, cpus: int, memory: int,
                     volumes: 'list[Volume]' = None,
                     interfaces: 'list[tuple[NetworkInterface, bool]]' = None):
            """
            System profile data

            We choose to only have one hypervisor (direct controller),
            rather than the whole chain, to not duplicate functionality
            with power machine
            """
            self.system_name = system_name
            self.profile_name = profile_name
            self.hypervisor = hypervisor
            self.hostname = hostname
            self.cpus = cpus
            self.memory = memory
            self.ifaces = []
            self.volumes = []

            # gateway interface
            self._gateway = None

            if volumes:
                for vol in volumes:
                    self.add_volume(vol)
            if interfaces:
                for iface, is_default in interfaces:
                    self.add_network_interface(iface, is_default)

        @property
        def gateway_interface(self) -> "NetworkInterface":
            """
            Return gateway interface
            """
            return self._gateway

        @property
        def system_type(self):
            """
            System type
            """
            if isinstance(self.hypervisor,
                          AutoinstallMachineModel.HmcHypervisor):
                return self.SystemTypes.LPAR
            if isinstance(self.hypervisor,
                          AutoinstallMachineModel.ZvmHypervisor):
                return self.SystemTypes.ZVM
            if isinstance(self.hypervisor,
                          AutoinstallMachineModel.KvmHypervisor):
                return self.SystemTypes.KVM

            return self.SystemTypes.GENERIC

        def add_volume(self, volume: 'Volume'):
            """
            Attach a volume for use in installation
            """
            self.volumes.append(volume)

        def add_network_interface(self, iface: 'NetworkInterface',
                                  is_gateway: bool = False):
            """
            Attach a volume for use in installation
            """
            self.ifaces.append(iface)
            if is_gateway:
                self._gateway = iface

        def get_boot_device(self):
            """
            Get the boot device from system profile

            Returns:
                StorageVolume: if found or None
            """
            root_vol = None
            boot_vol = None
            for volume in self.volumes:
                if not volume.partitions:
                    continue
                for partition in volume.partitions:
                    if partition.mount_point == "/":
                        root_vol = volume
                    elif partition.mount_point == '/boot':
                        boot_vol = volume

            if not boot_vol:
                return root_vol
            return boot_vol

        def list_gateway_networks(self):
            """
            List subnets that machine has access to via gateway interface
            """
            if self._gateway:
                return self._gateway.gateway_subnets
            return []

    def __init__(self, os: OperatingSystem, os_repos: "list[OsRepository]",
                 template: Template, installer_template: Template,
                 custom_os_repos: "list[OsRepository]",
                 custom_package_repos: "list[PackageRepository]",
                 system_profile: SystemProfile,
                 installation_options: dict):
        """
        Create model from controller data
        """
        self.operating_system = os
        self.template = template
        self.installer_template = installer_template

        self.system_profile = system_profile
        self.installer_cmdline = installation_options.get(
            'linux-kargs-installer')
        self.target_cmdline = installation_options.get('linux-kargs-target')

        # UBUNTU 20.04 has two installers, legacy (pre-20) and new (subiquity)
        # New is default, but users can choose former by specifying a flag
        # in installer command line
        self.ubuntu20_legacy_installer = (
            self.installer_cmdline
            and 'tessia_option_installer=legacy' in self.installer_cmdline)
        if self.ubuntu20_legacy_installer:
            # remove option from installer cmdline
            self.installer_cmdline = self.installer_cmdline.replace(
                'tessia_option_installer=legacy', '').strip()

        self.os_credentials = {
            'user': installation_options.get('user'),
            'password': installation_options.get('password'),
            'installation-password': installation_options.get(
                'installation-password'),
        }

        # Custom repositories come first, but require more checks

        # Some of the os repos may provide to a different OS,
        # so make sure we only pick ones we want to install from
        # The rest goes to package repos
        self.os_repos, self.package_repos = self._spread_repos_by_os(
            os.name, custom_os_repos)

        # Add the rest of package repos
        self.package_repos.extend(custom_package_repos)

        # Extend list from custom repositories with verified ones
        self.os_repos.extend([repo for repo in os_repos
                              if repo.installable_os == os.name])

    @classmethod
    def _spread_repos_by_os(cls, os_name: str, repos: "list[OsRepository]"):
        """
        Having a list of repos, choose those that install current os

        Args:
            os_name (str): os that defines list splitting
            repos (List[OsRepository]):
                list of repositories

        Returns:
            Tuple[List[OsRepository], List[OsRepository]]:
                split os and package repositories
        """
        this_os_repos = []
        other_os_repos = []
        for repo in repos:
            if (isinstance(repo, cls.OsRepository) and
                    repo.installable_os == os_name):
                this_os_repos.append(repo)
            else:
                other_os_repos.append(repo)
        return (this_os_repos, other_os_repos)

    def validate(self):
        """
        Assert model is valid

        Raises:
            ValueError: model is inconsistent or inapplicable
        """
        if not self.os_repos:
            raise ValueError("No OS repository available for OS {}".format(
                self.operating_system.name))
        if not self.template:
            raise ValueError("No autoinstallation template specified")
        if not self.installer_template:
            raise ValueError("No installer command line template specified")
        if not self.system_profile._gateway:
            raise ValueError("No gateway interface present")

        self.system_profile.hypervisor.validate()

        for iface in self.system_profile.ifaces:
            iface.validate()

        # verify gateway interface has IP address and gateways
        if not self.system_profile.list_gateway_networks():
            raise ValueError(
                "Gateway interface {} has no IP address"
                " or gateway route".format(
                    self.system_profile._gateway.os_device_name
                ))

        # verify that total partition size is not bigger than disk size
        failing_volume_ids = []
        for volume in [volume for volume in self.system_profile.volumes
                       if isinstance(volume, (self.DasdVolume,
                                              self.ZfcpVolume,
                                              self.NvmeVolume))]:
            total_part_size = sum(
                [partition.size for partition in volume.partitions])
            if total_part_size > volume.size:
                failing_volume_ids.append(str(volume))

        if failing_volume_ids:
            raise ValueError(
                "Partitioning exceeds volume size for volumes {}".format(
                    failing_volume_ids))
# AutoinstallMachineModel
