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
Module to deal with operations on KVM guests
"""

#
# IMPORTS
#
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from tessia.baselib.common.ssh.client import SshClient
from tessia.baselib.hypervisors.kvm import HypervisorKvm
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from urllib.parse import urljoin
from xml.etree import ElementTree

import logging

#
# CONSTANTS AND DEFINITIONS
#
DISK_TEMPLATE = """
    <disk type="{disk_type}" device="disk">
      <driver name="qemu" type="{driver}" cache="none"/>
      <source {src_type}="{src_dev}"/>
      <target dev="{target_dev}" bus="virtio"/>
      <address type="ccw" cssid="0xfe" ssid="0x0" devno="{devno}"/>
      {boot_tag}
    </disk> 
"""
RHEL_ID = 'Red Hat Enterprise Linux'
UBUNTU_ID = 'Ubuntu '

#
# CODE
#


class PlatKvm(PlatBase):
    """
    Handling for KVM guests
    """

    def __init__(self, model: AutoinstallMachineModel,
                 hypervisor: HypervisorKvm = None):
        """
        Perform libvirt processing of the guest devices.
        """
        super().__init__(model)
        # create our own logger so that the right module name is in output
        self._logger = logging.getLogger(__name__)

        if hypervisor:
            self._hyp_obj = hypervisor
        else:
            self._hyp_obj = PlatKvm.create_hypervisor(model)

        # create virsh session
        self._hyp_obj.login()

        # determine the type of devpath prefix used for devices, certain
        # distros use virtio-pci-* naming
        p_name = self._os.pretty_name
        if (p_name.startswith(UBUNTU_ID) and self._os.major <= 1610) or (
                p_name.startswith(RHEL_ID) and self._os.major == 7
                and self._os.minor == 4):
            self._devpath_prefix = '/dev/disk/by-path/virtio-pci-0.{}.{}'
        else:
            self._devpath_prefix = '/dev/disk/by-path/ccw-0.{}.{}'

        self._kvm_vol_init(self._guest_prof.volumes)
    # __init__()

    @classmethod
    def create_hypervisor(cls, model: AutoinstallMachineModel):
        """
        Create an instance of baselib's hypervisor. Here we have no
        knowledge about parameters so _create_hyp can be re-implemented
        by children classes
        """
        return HypervisorKvm(
            model.system_profile.hypervisor.name,
            model.system_profile.hypervisor.kvm_host,
            model.system_profile.hypervisor.credentials['user'],
            model.system_profile.hypervisor.credentials['password'],
            None)
    # create_hypervisor()

    @staticmethod
    def _kvm_jsonify_iface(
            iface_entry: AutoinstallMachineModel.NetworkInterface):
        """
        Format an iface object to a json format expected by baselib.
        """
        if isinstance(iface_entry,
                      AutoinstallMachineModel.MacvtapHostInterface):
            return {
                "attributes": {
                    'hostiface': iface_entry.hostiface
                },
                "mac_address": iface_entry.mac_address,
                "type": 'MACVTAP'
            }
        if isinstance(iface_entry,
                      AutoinstallMachineModel.MacvtapLibvirtInterface):
            return {
                "attributes": {
                    'libvirt': iface_entry.libvirt
                },
                "mac_address": iface_entry.mac_address,
                "type": 'MACVTAP'
            }
        if isinstance(iface_entry, AutoinstallMachineModel.OsaInterface):
            return {
                'ccwgroup': iface_entry.ccwgroup,
                'layer2': iface_entry.layer2,
                'portno': iface_entry.portno,
                'portname': iface_entry.portname,
                'type': 'OSA'
            }
        return {
            "mac_address": iface_entry.mac_address,
            "type": 'UNKNOWN'
        }
    # _kvm_jsonify_iface()

    @staticmethod
    def _kvm_jsonify_vol(storage_vol):
        """
        Format a volume object to a json format expected by baselib.
        """
        if isinstance(storage_vol, AutoinstallMachineModel.ZfcpVolume):
            result = {
                "type": storage_vol.volume_type,
                "volume_id": storage_vol.lun,
                "system_attributes": {
                    'libvirt': storage_vol.libvirt_definition
                },
                "specs": {},
            }
            # compatibility layer to baselib:
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
        else:
            result = {
                "type": storage_vol.volume_type,
                "volume_id": storage_vol.device_id,
                "system_attributes": {
                    'libvirt': storage_vol.libvirt_definition
                },
                "specs": {},
            }
        return result
    # _kvm_jsonify_vol()

    def _kvm_vol_create_libvirt(self, vol_obj: AutoinstallMachineModel.Volume,
                                target_dev: str, devno: int):
        """
        Create a libvirt definition for the given volume.

        Args:
            vol_obj: volume sqlsa object
            target_dev: vda, vdb, etc.
            devno: 1, 500, etc.

        Returns:
            str: libvirt xml definition
        """
        if isinstance(vol_obj, (AutoinstallMachineModel.DasdVolume,
                                AutoinstallMachineModel.ZfcpVolume)):
            disk_type = 'block'
            src_type = 'dev'
            driver = 'raw'
        else:
            disk_type = ''
            src_type = ''
            driver = 'unsupported-{}'.format(vol_obj.volume_type)
        # The handling of the following disks is not supported yet,
        # so we are disabling it temporally.
        # elif vol_obj.type == 'RAW':
        #    disk_type = 'file'
        #    src_type = 'file'
        #    driver = 'raw'
        # elif vol_obj.type == 'QCOW2':
        #    disk_type = 'file'
        #    src_type = 'file'
        #    driver = 'qcow2'
        boot_tag = ''
        if vol_obj.partitions:
            for part in vol_obj.partitions:
                if part.mount_point == '/':
                    boot_tag = '<boot order="1"/>'
                    break

        hex_devno = '{:04x}'.format(devno)
        vol_libvirt = DISK_TEMPLATE.format(
            disk_type=disk_type,
            driver=driver,
            src_type=src_type,
            src_dev=vol_obj.device_path,
            target_dev=target_dev,
            devno='0x' + hex_devno,
            boot_tag=boot_tag,
        )
        result = {
            'devpath': self._devpath_prefix.format('0', hex_devno),
            'libvirt': vol_libvirt
        }
        return result
    # _kvm_vol_create_libvirt()

    @staticmethod
    def _kvm_vol_devs_generator():
        """
        Auxiliary generator used to generate valid libvirt device names.
        """
        letters = [chr(i) for i in range(ord('a'), ord('z') + 1)]

        for i in [''] + letters:
            for j in [''] + letters:
                for k in letters:
                    yield "vd{}{}{}".format(i, j, k)
    # _kvm_vol_devs_generator()

    def _kvm_vol_init(self, vols: "list[AutoinstallMachineModel.Volume]"):
        """
        Receive a list of volumes and process them, this means:
        - if a libvirt definition exists, parse its xml and extract devpath
        - if it has no libvirt definition, create one dynamically

        Args:
            vols (list): list of StorageVolume objects

        Raises:
            ValueError: in case there is a conflict with resources used
            RuntimeError: if max number of devnos is reached
        """
        # keep track of used devnos and devs (i.e. vda) to avoid conflicts
        # when dynamically generating definitions as well as for sanity check
        # of user definitions
        used_devnos = {}
        used_devs = {}

        # create a list of vols without libvirt definition to process them
        # later to avoid conflicts with volumes that have libvirt defined
        # by user.
        dyn_vols = []
        for vol in vols:
            # no libvirt definition: process it later
            if not vol.libvirt_definition:
                dyn_vols.append(vol)
                continue

            # parse the user-defined xml
            self._logger.info(
                'Applying user-defined libvirt xml for volume %s',
                str(vol)
            )
            result = self._kvm_vol_parse_libvirt(vol.libvirt_definition)
            # device is of same type used for dynamic entries: add it to the
            # used map
            if result['bus'] == 'virtio' and result['ssid'] == 0:
                # devno already used: report conflict
                if result['devno'] in used_devnos:
                    raise ValueError(
                        'devno {:04x} is used by more than one device'.format(
                            result['devno'])
                    )
                used_devnos[result['devno']] = True

            # target dev already used: report conflict
            if result['dev'] in used_devs:
                raise ValueError(
                    'dev {} is used by more than one device'.format(
                        result['dev'])
                )
            used_devs[result['dev']] = True

            # store the devpath of the parsed volume
            vol.device_path = result['devpath']
            # self._devpath_by_vol[vol.id] = result['devpath']

        # no volumes without libvirt definition: nothing more to do
        # There is no need to return right away since it will not
        # enter in the following loop if there is no dyn_vols.

        # generator for valid libvirt device names
        dev_generate = self._kvm_vol_devs_generator()
        devno_counter = 1
        # create libvirt definitions
        for vol in dyn_vols:
            self._logger.info(
                'Volume %s has no libvirt xml, generating one', str(vol))

            # generate a valid target dev
            target_dev = next(dev_generate)
            while target_dev in used_devs:
                target_dev = next(dev_generate)
            # generate a valid devno
            while devno_counter in used_devnos:
                if devno_counter == 0xffff:
                    raise RuntimeError("devno limit reached (0xffff)")
                devno_counter += 1
            used_devs[target_dev] = True
            used_devnos[devno_counter] = True

            result = self._kvm_vol_create_libvirt(
                vol, target_dev, devno_counter)
            # Add libvirt definition to the object, it has to be stored in
            # database so that future poweron actions have a way to reconstruct
            # the same setup, otherwise the operating system might not find the
            # expected disks anymore as they might have different device paths.
            vol.libvirt_definition = result['libvirt']
            vol.device_path = result['devpath']
            # self._devpath_by_vol[vol.id] = result['devpath']

            self._logger.debug('Libvirt xml for volume %s is:\n%s',
                               str(vol), result['libvirt'])

    # _kvm_vol_init()``

    def _kvm_vol_parse_libvirt(self, libvirt_xml):
        """
        Process a user-defined disk libvirt definition to extract relevant
        information and validate it.

        Args:
            libvirt_xml (str): xml content

        Raises:
            ValueError: in case xml is invalid
            RuntimeError: in case guest has unsupported archictecture

        Returns:
            dict: containing extracted volume data
        """
        try:
            libvirt_tree = ElementTree.fromstring(libvirt_xml)
        except Exception:
            msg = 'Libvirt xml is invalid'
            self._logger.debug(msg, exc_info=True)
            raise ValueError(msg)
        try:
            bus = libvirt_tree.find('target').attrib['bus']
            dev = libvirt_tree.find('target').attrib['dev']
        except (AttributeError, KeyError):
            msg = 'Libvirt xml has missing or invalid <target> tag'
            self._logger.debug(msg, exc_info=True)
            raise ValueError(msg)

        # determine the device based on bus and arch type, this can be extended
        # for more buses and arch types over time
        if bus == 'virtio':
            # for s390 we use ccw addressing to determine device path
            try:
                address = libvirt_tree.find('address')
                ssid = int(address.get('ssid', '<unspecified>'), 16)
                devno = int(address.get('devno', '<unspecified>'), 16)
            except (AttributeError, KeyError, ValueError):
                msg = 'Libvirt xml has missing or invalid <address> tag'
                self._logger.debug(msg, exc_info=True)
                raise ValueError(msg)

            result = {
                'bus': bus,
                'dev': dev,
                'ssid': ssid,
                'devno': devno,
                'devpath': self._devpath_prefix.format(
                    '{:x}'.format(ssid), '{:04x}'.format(devno))
            }
            return result

        raise RuntimeError('Unsupported bus type {}'.format(bus))
    # _kvm_vol_parse_libvirt()

    def prepare_guest(self):
        """
        Initialize guest (activate, prepare hardware etc.)

        Does nothing in current implementation; requires support in baselib
        """
    # prepare_guest()

    def reboot(self):
        """
        Restart the guest after installation is finished.
        """
        self._logger.info('rebooting the system now')

        hostname = self._model.system_profile.hostname
        user = self._model.os_credentials['user']
        password = self._model.os_credentials['installation-password']

        ssh_client = SshClient()
        ssh_client.login(hostname, user=user, passwd=password, timeout=10)
        shell = ssh_client.open_shell()
        # in certain installations files created by post-install scripts don't
        # get written to disk if we don't call sync before rebooting
        shell.run('sync')
        shell.close()
        ssh_client.logoff()

        self._hyp_obj.reboot(self._model.system_profile.system_name, None)
    # reboot()

    def start_installer(self, kargs):
        """
        Perform a boot operation so that the installation process can start.

        Args:
            kargs (str): kernel command line args for os' installer
        """
        # basic information
        cpu = self._guest_prof.cpus
        memory = self._guest_prof.memory
        guest_name = self._guest_prof.system_name

        # prepare entries in the format expected by baselib
        svols = []
        for svol in self._guest_prof.volumes:
            svols.append(self._kvm_jsonify_vol(svol))
        ifaces = []
        for iface in self._guest_prof.ifaces:
            ifaces.append(self._kvm_jsonify_iface(iface))

        # repository related information
        repo = self._repo
        kernel_uri = urljoin(repo.url + '/', repo.kernel.strip('/'))
        initrd_uri = urljoin(repo.url + '/', repo.initrd.strip('/'))

        # parameters argument, see baselib schema for details
        params = {
            'ifaces': ifaces,
            'storage_volumes': svols,
            'parameters': {
                "boot_method": "network",
                "boot_options": {
                    "kernel_uri": kernel_uri,
                    "initrd_uri": initrd_uri,
                    "cmdline": kargs,
                }
            }
        }

        self._hyp_obj.start(guest_name, cpu, memory, params)
    # start_installer()

    def set_boot_device(self, boot_device):
        """
        Set boot device to perform later boot

        Args:
            boot_device (dict): boot device description
                "storage" (StorageVolume): volume
                "network" (string): URI with boot source
        """
        self._logger.debug("set_boot_device on KVM is a no-op")

    # set_boot_device()
# PlatKvm
