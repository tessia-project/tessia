# Copyright 2017 IBM Corp.
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
Module for the TestPlatKvm class.
"""

#
# IMPORTS
#

from tessia_engine.db.connection import MANAGER
from tessia_engine.state_machines.install import plat_base, plat_kvm
from tessia_engine.state_machines.install.sm_base import SmBase
from tests.unit.state_machines.install import utils
from unittest import mock, TestCase
from unittest.mock import patch

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class TestPlatKvm(TestCase):
    """
    Class for unit testing the PlatKvm class.
    """
    @classmethod
    def setUpClass(cls):
        """
        Called once for the setup of DbUnit.
        """
        utils.setup_dbunit()
    # setUpClass()

    def setUp(self):
        """
        Setup all the mocks used for the execution of the tests.
        """
        # We cannot use autospec here because the Hypervisor class does not
        # really have all the methods since it is a factory class.
        patcher = patch.object(plat_base, 'Hypervisor')
        self._mock_hypervisor_cls = patcher.start()
        self.addCleanup(patcher.stop)

        self._os_entry = utils.get_os("rhel7.2")
        self._profile_entry = utils.get_profile(
            "kvm054/kvm_kvm054_install_dasd")
        self._hyper_profile_entry = self._profile_entry.hypervisor_profile_rel
        self._repo_entry = self._os_entry.repository_rel[0]
        self._gw_iface_entry = self._profile_entry.gateway_rel
        # gateway interface not defined: use first available
        if self._gw_iface_entry is None:
            self._gw_iface_entry = self._profile_entry.system_ifaces_rel[0]

        # TODO: this is very ugly, but it is the only way to create
        # the parameters necessary for the creation of the PlatKvm.
        self._parsed_gw_iface = (
            SmBase._parse_iface(self._gw_iface_entry, True))
    # setUp()

    def _create_plat_kvm(self):
        """
        Auxiliary method that create a PlatKvmChild instance based on
        the testcase inforamtion.
        """
        return plat_kvm.PlatKvm(self._hyper_profile_entry,
                                self._profile_entry,
                                self._os_entry, self._repo_entry,
                                self._parsed_gw_iface)
    # _create_plat_base()

    def test_boot(self):
        """
        Test the correct initialization and the operations of a
        PlatKvm boot operation.
        """
        # The instance of the Hypervisor class.
        mock_hyp = self._mock_hypervisor_cls.return_value
        plat = self._create_plat_kvm()

        # Performs the reboot operation.
        plat.boot("SOME PARAM")
        guest_name = self._profile_entry.system_rel.name
        cpu = self._profile_entry.cpu
        memory = self._profile_entry.memory

        # We don't test the params argument since it is a complex
        # dictionary generated inside the init function.
        mock_hyp.start.assert_called_with(guest_name, cpu, memory,
                                          mock.ANY)
    # test_boot()

    def test_get_vol_devpath(self):
        """
        Test the correct creation of the device paths for the volumes.
        """
        plat = self._create_plat_kvm()
        volumes = self._profile_entry.storage_volumes_rel

        # Here we used specifc test cases, since we know the content
        # ot the database.
        devpaths = [
            "/dev/disk/by-path/ccw-0.0.0002",
            "/dev/disk/by-path/ccw-0.0.0001",
            "/dev/disk/by-path/ccw-0.0.0003",
            "/dev/disk/by-path/ccw-0.0.0004",
        ]

        for vol, devpath in zip(volumes, devpaths):
            self.assertEqual(plat.get_vol_devpath(vol), devpath)
    # test_get_vol_devpath()

    def test_get_vol_devpath_old_style(self):
        """
        Test the correct creation of the device paths for the volumes
        when using operting systems that use udev version 228 or newer.
        """
        self._os_entry.major = 8
        self.addCleanup(MANAGER.session.rollback)

        volumes = self._profile_entry.storage_volumes_rel
        # To test the other branch, we remove all libvirt definitions
        for vol in volumes:
            vol.system_attributes = {}

        plat = self._create_plat_kvm()
        # Here we used specifc test cases, since we know the content
        # ot the database.
        devpaths = [
            "/dev/disk/by-path/virtio-pci-0.0.0001",
            "/dev/disk/by-path/virtio-pci-0.0.0002",
            "/dev/disk/by-path/virtio-pci-0.0.0003",
            "/dev/disk/by-path/virtio-pci-0.0.0004",
        ]

        for vol, devpath in zip(volumes, devpaths):
            self.assertEqual(plat.get_vol_devpath(vol), devpath)
    # test_get_vol_devpath()

    def test_invalid_libvirt_xml(self):
        """
        Test the case a storage volume has an invalid libvirt xml.
        """
        self.addCleanup(MANAGER.session.rollback)
        libvirt_dev1 = ("<disk type='block' device='disk'>"
                        "<driver name='qemu' type"
                        "<target dev='vda' bus='virtio'/>"
                        "<address type='ccw' cssid='0xfe'"
                        " ssid='0x0' devno='0x0001'/></disk>")

        volumes = self._profile_entry.storage_volumes_rel
        volumes[1].system_attributes["libvirt"] = libvirt_dev1

        self.assertRaisesRegex(ValueError, "Libvirt xml is invalid",
                               self._create_plat_kvm)
    # test_invalid_libvirt_xml()

    def test_missing_address_tag(self):
        """
        Test the case the livbirt xml of a storage volume does not have
        the address tag.
        """
        self.addCleanup(MANAGER.session.rollback)
        libvirt_dev = ("<disk type='block' device='disk'>"
                       "<driver name='qemu' type='raw'/>"
                       "<source dev='/dev/disk/by-id/dm-uuid-mpath-"
                       "11002076305aac1a0000000000002409'/>"
                       "<target dev='vda' bus='virtio'/></disk>")

        volumes = self._profile_entry.storage_volumes_rel
        volumes[1].system_attributes["libvirt"] = libvirt_dev

        self.assertRaisesRegex(ValueError, ".*address.*tag",
                               self._create_plat_kvm)
    # test_missing_address_tag()

    def test_missing_target_tag(self):
        """
        Test the case the livbirt xml of a storage volume does not have
        the target tag.
        """
        self.addCleanup(MANAGER.session.rollback)
        libvirt_dev = ("<disk type='block' device='disk'>"
                       "<driver name='qemu' type='raw'/>"
                       "<source dev='/dev/disk/by-id/dm-uuid-mpath-"
                       "11002076305aac1a0000000000002409'/>"
                       "<address type='ccw' cssid='0xfe'"
                       " ssid='0x0' devno='0x0001'/></disk>")

        volumes = self._profile_entry.storage_volumes_rel
        volumes[1].system_attributes["libvirt"] = libvirt_dev

        self.assertRaisesRegex(ValueError, "Libvirt xml has missing",
                               self._create_plat_kvm)
    # test_missing_target_tag()

    def test_same_device_number(self):
        """
        Test the case two volumes have the same device number.
        """
        self.addCleanup(MANAGER.session.rollback)
        libvirt_dev1 = ("<disk type='block' device='disk'>"
                        "<driver name='qemu' type='raw'/>"
                        "<source dev='/dev/disk/by-id/dm-uuid-mpath-"
                        "11002076305aac1a0000000000002409'/>"
                        "<target dev='vda' bus='virtio'/>"
                        "<address type='ccw' cssid='0xfe'"
                        " ssid='0x0' devno='0x0001'/></disk>")
        libvirt_dev2 = ("<disk type='block' device='disk'>"
                        "<driver name='qemu' type='raw'/>"
                        "<source dev='/dev/disk/by-id/dm-uuid-mpath-"
                        "11002076305aac1a000000000000240a'/>"
                        "<target dev='vda' bus='virtio'/>"
                        "<address type='ccw' cssid='0xfe'"
                        " ssid='0x0' devno='0x0001'/></disk>")
        volumes = self._profile_entry.storage_volumes_rel
        volumes[1].system_attributes["libvirt"] = libvirt_dev1
        volumes[2].system_attributes["libvirt"] = libvirt_dev2

        self.assertRaisesRegex(ValueError, "devno", self._create_plat_kvm)
    # test_same_device_number()

    def test_same_target_device_name(self):
        """
        Test the case two volumes have the same target device name.
        """
        self.addCleanup(MANAGER.session.rollback)
        libvirt_dev1 = ("<disk type='block' device='disk'>"
                        "<driver name='qemu' type='raw'/>"
                        "<source dev='/dev/disk/by-id/dm-uuid-mpath-"
                        "11002076305aac1a0000000000002409'/>"
                        "<target dev='vda' bus='virtio'/>"
                        "<address type='ccw' cssid='0xfe'"
                        " ssid='0x0' devno='0x0001'/></disk>")
        libvirt_dev2 = ("<disk type='block' device='disk'>"
                        "<driver name='qemu' type='raw'/>"
                        "<source dev='/dev/disk/by-id/dm-uuid-mpath-"
                        "11002076305aac1a000000000000240a'/>"
                        "<target dev='vda' bus='virtio'/>"
                        "<address type='ccw' cssid='0xfe'"
                        " ssid='0x0' devno='0x0002'/></disk>")
        volumes = self._profile_entry.storage_volumes_rel
        volumes[1].system_attributes["libvirt"] = libvirt_dev1
        volumes[2].system_attributes["libvirt"] = libvirt_dev2

        self.assertRaisesRegex(ValueError, "dev vda", self._create_plat_kvm)
    # test_same_target_device_name()

    def test_unknown_volume_type(self):
        """
        Test the case a storage volume is of an unknown type.
        """
        # Save the type name for restore after the test.
        bk_type_name = self._profile_entry.storage_volumes_rel[0].type_rel.name
        def restore_type_name():
            """
            Inner function to restore the type name of the volume
            """
            self._profile_entry.storage_volumes_rel[0].type_rel.name = (
                bk_type_name)
            MANAGER.session.commit()
        # restore_type_name()
        self.addCleanup(restore_type_name)

        self._profile_entry.storage_volumes_rel[0].type_rel.name = "unknown"
        MANAGER.session.commit()
        self.assertRaisesRegex(RuntimeError, "Unknown ", self._create_plat_kvm)
    # test_unknown_volume_type()

    def test_unsupported_arch(self):
        """
        Test the case the architecture is not supported.
        """
        self.addCleanup(MANAGER.session.rollback)

        system_entry = self._profile_entry.system_rel
        system_entry.type_rel.arch_rel.name = "unknown"

        self.assertRaisesRegex(RuntimeError, "Unsupported system architecture",
                               self._create_plat_kvm)
    # test_unsupported_arch()

    def test_unsupported_bus(self):
        """
        Test the case the storage volume libvirt xml has an
        unsupported communication bus.
        """
        self.addCleanup(MANAGER.session.rollback)
        libvirt_dev = ("<disk type='block' device='disk'>"
                       "<driver name='qemu' type='raw'/>"
                       "<source dev='/dev/disk/by-id/dm-uuid-mpath-"
                       "11002076305aac1a0000000000002409'/>"
                       "<target dev='vda' bus='another_bus'/>"
                       "<address type='ccw' cssid='0xfe'"
                       " ssid='0x0' devno='0x0001'/></disk>")

        volumes = self._profile_entry.storage_volumes_rel
        volumes[1].system_attributes["libvirt"] = libvirt_dev

        self.assertRaisesRegex(RuntimeError, "Unsupported bus",
                               self._create_plat_kvm)
    # test_unsupported_bus()

# TestPlatKvm