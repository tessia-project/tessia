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
from tessia.baselib.common.ssh.client import SshClient
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import SystemProfile
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from urllib.parse import urljoin
from xml.etree import ElementTree

from time import sleep
import logging

#
# CONSTANTS AND DEFINITIONS
#
DISK_TEMPLATE = """
    <disk type="{disk_type}" device="disk">
      <driver name="qemu" type="{driver}" cache='none'/>
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
    def __init__(self, *args, **kwargs):
        """
        Perform libvirt processing of the guest devices.
        """
        super().__init__(*args, **kwargs)
        # create our own logger so that the right module name is in output
        self._logger = logging.getLogger(__name__)

        # determine the type of devpath prefix used for devices, certain
        # distros use virtio-pci-* naming
        p_name = self._os.pretty_name
        if p_name.startswith(UBUNTU_ID) or (
                p_name.startswith(RHEL_ID) and self._os.major == 7
                and self._os.minor == 4):
            self._devpath_prefix = '/dev/disk/by-path/virtio-pci-0.{}.{}'
        else:
            self._devpath_prefix = '/dev/disk/by-path/ccw-0.{}.{}'

        # define a mapping of volumes and their stable device paths
        self._devpath_by_vol = {}

        guest_prof = SystemProfile.query.filter_by(
            id=self._guest_prof.id).one()
        self._vols = list(guest_prof.storage_volumes_rel)
        self._kvm_vol_init(self._vols)
    # __init__()

    @staticmethod
    def _kvm_get_vol_devpath_on_host(vol_obj):
        """
        Given a volume entry, return the correspondent device path on operating
        system.

        Args:
            vol_obj (StorageVolume): volume sqlsa object

        Returns:
            str: device path

        Raises:
            ValueError: in case volume type is not supported
        """
        if vol_obj.type == 'DASD':
            vol_id = vol_obj.volume_id
            if vol_id.find('.') < 0:
                vol_id = '0.0.' + vol_id
            return '/dev/disk/by-path/ccw-{}'.format(vol_id)

        elif vol_obj.type == 'FCP':
            if vol_obj.specs['multipath']:
                prefix = '/dev/disk/by-id/dm-uuid-mpath-{}'
            else:
                prefix = '/dev/disk/by-id/scsi-{}'
            return prefix.format(vol_obj.specs['wwid'])
        else:
            raise ValueError(
                'Unsupported volume type {}'.format(vol_obj.type))
    # _kvm_get_vol_devpath_on_host()

    @staticmethod
    def _kvm_jsonify_iface(iface_entry):
        """
        Format an iface object to a json format expected by baselib.
        """
        result = {
            "attributes": iface_entry.attributes,
            "mac_address": iface_entry.mac_address,
            "type": iface_entry.type
        }
        return result
    # _kvm_jsonify_iface()

    @staticmethod
    def _kvm_jsonify_vol(vol_entry):
        """
        Format a volume object to a json format expected by baselib.
        """
        result = {
            "type": vol_entry.type_rel.name,
            "volume_id": vol_entry.volume_id,
            "system_attributes": vol_entry.system_attributes,
            "specs": vol_entry.specs,
        }
        return result
    # _kvm_jsonify_vol()

    def _kvm_vol_create_libvirt(self, vol_obj, target_dev, devno):
        """
        Create a libvirt definition for the given volume.

        Args:
            vol_obj (StorageVolume): volume sqlsa object
            target_dev (str): vda, vdb, etc.
            devno (int): 1, 500, etc.

        Returns:
            str: libvirt xml definition
        """
        if vol_obj.type in ('FCP', 'DASD'):
            disk_type = 'block'
            src_type = 'dev'
            driver = 'raw'
        # The handling of the following disks is not supported yet,
        # so we are disabling it temporally.
        #elif vol_obj.type == 'RAW':
        #    disk_type = 'file'
        #    src_type = 'file'
        #    driver = 'raw'
        #elif vol_obj.type == 'QCOW2':
        #    disk_type = 'file'
        #    src_type = 'file'
        #    driver = 'qcow2'
        boot_tag = ''
        for part in vol_obj.part_table['table']:
            if part['mp'] == '/':
                boot_tag = '<boot order="1"/>'
                break

        hex_devno = '{:04x}'.format(devno)
        vol_libvirt = DISK_TEMPLATE.format(
            disk_type=disk_type,
            driver=driver,
            src_type=src_type,
            src_dev=self._kvm_get_vol_devpath_on_host(vol_obj),
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

    def _kvm_vol_init(self, vols):
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
        # We need to test for valid types before anything so that we avoid
        # checking the device type twice.
        valid_vol_types = ["FCP", "DASD", "RAW", "QCOW2"]
        for vol in vols:
            if vol.type_rel.name not in valid_vol_types:
                raise RuntimeError(
                    "Unknown volume type'{}'".format(vol.type))
            # no libvirt definition: process it later
            if vol.system_attributes.get('libvirt') is None:
                dyn_vols.append(vol)
                continue

            # parse the user-defined xml
            self._logger.info(
                'Applying user-defined libvirt xml for volume %s',
                vol.human_name
            )
            result = self._kvm_vol_parse_libvirt(
                vol.system_attributes['libvirt'])
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
            self._devpath_by_vol[vol.id] = result['devpath']

        # no volumes without libvirt definition: nothing more to do
        # There is no need to return right away since it will not
        # enter in the following loop if there is no dyn_vols.

        # generator for valid libvirt device names
        dev_generate = self._kvm_vol_devs_generator()
        devno_counter = 1
        # create libvirt definitions
        for vol in dyn_vols:
            self._logger.info(
                'Volume %s has no libvirt xml, generating one',
                vol.human_name)

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
            vol.system_attributes['libvirt'] = result['libvirt']
            # to make sure sqlalchemy sees the object has changed
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(vol, 'system_attributes')
            MANAGER.session.add(vol)
            # store the devpath corresponding to the libvirt definition
            self._devpath_by_vol[vol.id] = result['devpath']

            self._logger.debug('Libvirt xml for volume %s is:\n%s',
                               vol.human_name, result['libvirt'])

        MANAGER.session.commit()
    # _kvm_vol_init()

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

            # at the moment only s390 is supported
            arch = self._guest_prof.system_rel.type_rel.arch
            if arch != 's390x':
                raise RuntimeError(
                    'Unsupported system architecture {}'.format(arch))

            # for s390 we use ccw addressing to determine device path
            try:
                address = libvirt_tree.find('address')
                ssid = int(address.get('ssid'), 16)
                devno = int(address.get('devno'), 16)
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

    def boot(self, kargs):
        """
        Perform a boot operation so that the installation process can start.

        Args:
            kargs (str): kernel command line args for os' installer
        """
        # basic information
        cpu = self._guest_prof.cpu
        memory = self._guest_prof.memory
        guest_name = self._guest_prof.system_rel.name

        # prepare entries in the format expected by baselib
        svols = []
        for svol in self._vols:
            svols.append(self._kvm_jsonify_vol(svol))
        ifaces = []
        for iface in self._guest_prof.system_ifaces_rel:
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
    # boot()

    def get_vol_devpath(self, vol_obj):
        """
        Given a volume entry, return the correspondent device path on operating
        system.

        Args:
            vol_obj (StorageVolume): sqlsa object

        Returns:
            str: device path in the form /dev/xxxx
        """
        # devpath was already determined during initialization time, just
        # return it
        return self._devpath_by_vol[vol_obj.id]
    # get_vol_devpath()

    def reboot(self, system_profile):
        """
        Restart the guest after installation is finished.

        Args:
            system_profile (SystemProfile): db's entry
        """
        # On kvm a soft reboot does not work as it only starts the distro
        # installer again. Instead we do a shutdown and then boot from
        # the hypervisor level
        self._logger.info('rebooting the system now')

        hostname = system_profile.system_rel.hostname
        user = system_profile.credentials['user']
        password = system_profile.credentials['passwd']

        ssh_client = SshClient()
        ssh_client.login(hostname, user=user, passwd=password,
                         timeout=10)
        shell = ssh_client.open_shell()
        # in certain installations files created by post-install scripts don't
        # get written to disk if we don't call sync before rebooting
        shell.run('sync')
        try:
            shell.run('nohup shutdown; nohup killall sshd', timeout=1)
        except TimeoutError:
            pass
        shell.close()
        ssh_client.logoff()

        # TODO: when baselib has support to provide guest status, replace this
        # sleep by polling until guest is off
        sleep(5)

        self._hyp_obj.reboot(system_profile.system_rel.name, None)
    # reboot()
# PlatKvm
