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
Test Debian autoinstall machine
"""

# pylint: disable=invalid-name  # we have really long test names
# pylint: disable=redefined-outer-name  # use of fixtures
# pylint: disable=unused-argument  # use of fixtures for their side effects

#
# IMPORTS
#

from tessia.server.config import Config
from tessia.server.state_machines.autoinstall import sm_base, plat_base
from tessia.server.state_machines.autoinstall import plat_lpar, plat_zvm, plat_kvm
from tessia.server.state_machines.autoinstall.model import AutoinstallMachineModel
from tessia.server.state_machines.autoinstall.sm_debian import SmDebianInstaller
from tests_pytest.state_machines.null_hypervisor import NullHypervisor
from tests_pytest.state_machines.ssh_stub import SshClient, SshShell

import pytest

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


class GoodLogSsh(SshClient):
    """
    Ssh that returns a session with good responses
    """

    def open_shell(self, chroot_dir=None, shell_path=None):
        """
        Set return values for commands
        """
        responses = {
            '/var/log/syslog':
                'Running /usr/lib/finish-install.d/20final-message',
        }
        return SshShell(responses)


@pytest.fixture(autouse=True)
def mock_config(monkeypatch, tmp_path):
    """
    Set default configuration
    """

    def get_config():
        """
        Configuration for use in tests
        """
        # use a temporary path for storing templates
        return {
            'auto_install': {
                'url': 'http://server_1:5000/',
                'dir': str(tmp_path),
                'live_img_passwd': 'liveimage'
            }
        }

    monkeypatch.setattr(Config, 'get_config', get_config)


@pytest.fixture(autouse=True)
def mock_hypervisors(monkeypatch):
    """Set null hypervisor"""
    monkeypatch.setattr(plat_lpar, 'HypervisorHmc', NullHypervisor)
    monkeypatch.setattr(plat_zvm, 'HypervisorZvm', NullHypervisor)
    monkeypatch.setattr(plat_kvm, 'HypervisorKvm', NullHypervisor)


@pytest.fixture(autouse=True)
def mock_ssh(monkeypatch):
    """
    Use ssh stub instead of real sessions
    """
    monkeypatch.setattr(plat_base, 'SshClient', SshClient)
    monkeypatch.setattr(plat_kvm, 'SshClient', SshClient)
    monkeypatch.setattr(sm_base, 'SshClient', SshClient)


@pytest.fixture(params=["ubuntu16", "ubuntu18", "ubuntu20"])
def os_any_ubuntu(request, os_ubuntu16_tuple, os_ubuntu18_tuple,
                  os_ubuntu20_legacy_tuple):
    """
    Enable test for multiple OS
    """
    yield {
        'ubuntu16': os_ubuntu16_tuple,
        'ubuntu18': os_ubuntu18_tuple,
        'ubuntu20': os_ubuntu20_legacy_tuple
    }[request.param]


@pytest.fixture
def good_log(monkeypatch):
    """
    Set good log sequence
    """
    monkeypatch.setattr(sm_base, 'SshClient', GoodLogSsh)


def test_successful_installation_on_text_trigger(
        kvm_scsi_system, os_any_ubuntu, creds,
        tmpdir, good_log):
    """Test Debian succeed when a special line is provided"""
    model = AutoinstallMachineModel(*os_any_ubuntu, kvm_scsi_system, creds)
    hyp = plat_kvm.PlatKvm.create_hypervisor(model)
    platform = plat_kvm.PlatKvm(model, hyp)

    with tmpdir.as_cwd():
        instmachine = SmDebianInstaller(model, platform)

    instmachine.start()
    # assert does nto throw


def test_successful_installation_on_kvm_complex(
        kvm_hypervisor,
        os_any_ubuntu, creds,
        tmpdir, good_log):
    """
    Test Ubuntu installation on KVM with a number of different devices
    """
    host_iface = AutoinstallMachineModel.MacvtapHostInterface(
        'encbf0', mac_address='04:05:ac:17:18:1d',
        os_device_name='hostvtap',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.0.15', subnet='10.0.0.0/24', gateway='10.0.0.1'),
            AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.2.1', subnet='10.0.2.0/24')])
    iface_libvirt_definition = r"""
       <interface type="direct">
         <mac address="04:05:ac:17:ff:02"/>
         <source dev="encbf0" mode="bridge"/>
         <model type="virtio"/>
         <address type="ccw" cssid="0xfe" ssid="0x0" devno="0xf4f2"/>
       </interface>"""
    internal_iface = AutoinstallMachineModel.MacvtapLibvirtInterface(
        iface_libvirt_definition, mac_address='04:05:ac:17:ff:02',
        os_device_name='enccwabcd',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.8.0.15', subnet='10.8.0.0/24', gateway='10.8.0.1')])

    dasd_root_volume = AutoinstallMachineModel.DasdVolume('abcd', 20_000)
    dasd_root_volume.set_partitions('dasd', [{
        'mount_point': '/',
        'size': 18_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': '/boot',
        'size': 500,
        'filesystem': 'ext2',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': 'swap',
        'size': 1_500,
        'filesystem': 'swap',
        'part_type': 'primary',
        'mount_opts': None,
    }, ])

    scsi_data_volume = AutoinstallMachineModel.ScsiVolume(
        '40a040b400c800dc', 20_000, multipath=True,
        wwid='36005076309ffd435000000000000c8dc')
    scsi_data_volume.create_paths(
        ['0.0.fc00', '0.0.fc40'],
        ['5005076309049435', '5005076309009435'])
    scsi_data_volume.set_partitions('msdos', [{
        'mount_point': '/data',
        'size': 18_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }])

    scsi_predefined_volume = AutoinstallMachineModel.ScsiVolume(
        '40a040b400c800dd', 25_000, multipath=True,
        wwid='36005076309ffd435000000000000c8dd'
    )
    volume_libvirt_definition = r"""
        <disk type="block" device="disk">
            <driver name="qemu" type="raw" cache="none"/>
            <source dev="{device_path}"/>
            <target dev="vda" bus="virtio"/>
            <address type="ccw" cssid="0xfe" ssid="0x0" devno="0xc8dd"/>
        </disk>""".format(device_path=scsi_predefined_volume.device_path)
    scsi_predefined_volume.libvirt_definition = volume_libvirt_definition
    scsi_predefined_volume.create_paths(
        ['0.0.fc00', '0.0.fc40'],
        ['5005076309049435', '5005076309009435'])
    scsi_predefined_volume.set_partitions('msdos', [{
        'mount_point': '/backup',
        'size': 18_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }])

    system = AutoinstallMachineModel.SystemProfile(
        'kvm54', 'complex',
        hypervisor=kvm_hypervisor,
        hostname='kvm54.local',
        cpus=2, memory=4096,
        volumes=[dasd_root_volume, scsi_data_volume,
                 scsi_predefined_volume],
        interfaces=[(host_iface, True), (internal_iface, False)]
    )

    model = AutoinstallMachineModel(*os_any_ubuntu, system, creds)
    hyp = plat_kvm.PlatKvm.create_hypervisor(model)
    platform = plat_kvm.PlatKvm(model, hyp)

    with tmpdir.as_cwd():
        instmachine = SmDebianInstaller(model, platform)

    instmachine.start()

    # make sure libvirt definition for volumes is generated
    for volume in model.system_profile.volumes:
        assert volume.libvirt_definition


def test_successful_installation_on_zvm_complex(
        zvm_hypervisor,
        os_any_ubuntu, creds,
        tmpdir, good_log):
    """
    Test Ubuntu installation on KVM with a number of different devices
    """
    osa_iface = AutoinstallMachineModel.OsaInterface(
        '0b01,0b02,0b03', False, mac_address='04:13:b7:97:0a:02',
        os_device_name='encb01',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.0.15', subnet='10.0.0.0/24', gateway='10.0.0.1'),
            AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.2.1', subnet='10.0.2.0/24')])
    osa_layer3_iface = AutoinstallMachineModel.OsaInterface(
        '0b41,0b42,0b43', True,
        os_device_name='encb41',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.3.0.15', subnet='10.3.0.0/24', gateway='10.3.0.1')])
    hsi_iface = AutoinstallMachineModel.HipersocketsInterface(
        '1a1c,1a1d,1a1e', False,
        os_device_name='enc1a1c',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.1.15', subnet='10.0.1.0/24')])
    hsi_layer3_iface = AutoinstallMachineModel.HipersocketsInterface(
        '4320,4321,4322', True,
        os_device_name='enc4320',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.3.2.15', subnet='10.3.2.0/24')])
    roce_iface = AutoinstallMachineModel.RoceInterface(
        '605',
        os_device_name='pci0n1',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.9.0.15', subnet='10.9.0.0/24', gateway='10.9.0.1')])
    roce_unbound_iface = AutoinstallMachineModel.RoceInterface(
        '606',
        os_device_name='pci0n2',
        subnets=[])

    dasd_root_volume = AutoinstallMachineModel.DasdVolume('abcd', 20_000)
    dasd_root_volume.set_partitions('dasd', [{
        'mount_point': '/',
        'size': 18_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': '/boot',
        'size': 500,
        'filesystem': 'ext2',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': 'swap',
        'size': 1_500,
        'filesystem': 'swap',
        'part_type': 'primary',
        'mount_opts': None,
    }, ])

    hpav_volume = AutoinstallMachineModel.HpavVolume('abfe')

    scsi_data_volume = AutoinstallMachineModel.ScsiVolume(
        '40a040b400c800dc', 20_000, multipath=True,
        wwid='36005076309ffd435000000000000c8dc')
    scsi_data_volume.create_paths(
        ['0.0.fc00', '0.0.fc40'],
        ['5005076309049435', '5005076309009435'])
    scsi_data_volume.set_partitions('msdos', [{
        'mount_point': '/data-1',
        'size': 3_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': '/data-2',
        'size': 3_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': '/data-3',
        'size': 3_000,
        'filesystem': 'xfs',
        'part_type': 'primary',
        'mount_opts': None,
    },
        {
        'mount_point': '/data-4',
        'size': 3_000,
        'filesystem': 'xfs',
        'part_type': 'primary',
        'mount_opts': None,
    },
        {
        'mount_point': '/data-5',
        'size': 3_000,
        'filesystem': 'ext3',
        'part_type': 'extended',
        'mount_opts': None,
    }])

    system = AutoinstallMachineModel.SystemProfile(
        'zvm25', 'complex',
        hypervisor=zvm_hypervisor,
        hostname='zvm25.local',
        cpus=2, memory=4096,
        volumes=[dasd_root_volume, hpav_volume, scsi_data_volume],
        interfaces=[(roce_iface, True), (roce_unbound_iface, False),
                    (osa_iface, False), (osa_layer3_iface, False),
                    (hsi_iface, False), (hsi_layer3_iface, False)]
    )

    model = AutoinstallMachineModel(*os_any_ubuntu, system, creds)
    hyp = plat_zvm.PlatZvm.create_hypervisor(model)
    platform = plat_zvm.PlatZvm(model, hyp)

    with tmpdir.as_cwd():
        instmachine = SmDebianInstaller(model, platform)

    instmachine.start()
    # assert does not throw


def test_successful_installation_on_lpar_complex(
        os_any_ubuntu, creds,
        tmpdir, good_log):
    """
    Test Ubuntu installation on KVM with a number of different devices
    """
    osa_iface = AutoinstallMachineModel.OsaInterface(
        '0b01,0b02,0b03', False, mac_address='04:13:b7:97:0a:02',
        os_device_name='encb01',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.0.15', subnet='10.0.0.0/24', gateway='10.0.0.1'),
            AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.2.1', subnet='10.0.2.0/24')])
    osa_layer3_iface = AutoinstallMachineModel.OsaInterface(
        '0b41,0b42,0b43', True,
        os_device_name='encb41',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.3.0.15', subnet='10.3.0.0/24', gateway='10.3.0.1')])
    hsi_iface = AutoinstallMachineModel.HipersocketsInterface(
        '1a1c,1a1d,1a1e', False,
        os_device_name='enc1a1c',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.1.15', subnet='10.0.1.0/24')])
    hsi_layer3_iface = AutoinstallMachineModel.HipersocketsInterface(
        '4320,4321,4322', True,
        os_device_name='enc4320',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.3.2.15', subnet='10.3.2.0/24')])
    roce_iface = AutoinstallMachineModel.RoceInterface(
        '605',
        os_device_name='pci0n1',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.9.0.15', subnet='10.9.0.0/24', gateway='10.9.0.1')])
    roce_unbound_iface = AutoinstallMachineModel.RoceInterface(
        '606',
        os_device_name='pci0n2',
        subnets=[])

    scsi_root_volume = AutoinstallMachineModel.ScsiVolume(
        '40a040b400c800dc', 20_000, multipath=True,
        wwid='36005076309ffd435000000000000c8dc')
    scsi_root_volume.create_paths(
        ['0.0.fc00', '0.0.fc40'],
        ['5005076309049435', '5005076309009435'])
    scsi_root_volume.set_partitions('msdos', [{
        'mount_point': '/',
        'size': 18_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': '/boot',
        'size': 500,
        'filesystem': 'ext2',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': 'swap',
        'size': 1_500,
        'filesystem': 'swap',
        'part_type': 'primary',
        'mount_opts': None,
    }, ])

    hpav_volume = AutoinstallMachineModel.HpavVolume('abfe')

    dasd_data_volume = AutoinstallMachineModel.DasdVolume('abcd', 20_000)

    dasd_data_volume.set_partitions('dasd', [{
        'mount_point': '/data-1',
        'size': 3_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': '/data-2',
        'size': 3_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': '/data-3',
        'size': 3_000,
        'filesystem': 'xfs',
        'part_type': 'primary',
        'mount_opts': None,
    },
        {
        'mount_point': '/data-4',
        'size': 3_000,
        'filesystem': 'xfs',
        'part_type': 'primary',
        'mount_opts': None,
    },
        {
        'mount_point': '/data-5',
        'size': 3_000,
        'filesystem': 'ext3',
        'part_type': 'extended',
        'mount_opts': None,
    }])

    hmc_hypervisor = AutoinstallMachineModel.HmcHypervisor(
        'hmc', 'hmc.local',
        {'user': 'hmcuser', 'password': 'hmcpassword'},
        {
            'partition-name': 'LP12',
            'boot-method': 'storage',
            'boot-device': 'fc06',
            'boot-device-lun': '408000c000de0018',
            'boot-device-wwpn': '5005076309049435',
            'boot-device-uuid': '6005076309ffd435000000000000de18',
        })

    system = AutoinstallMachineModel.SystemProfile(
        'lpar12', 'complex',
        hypervisor=hmc_hypervisor,
        hostname='lpar12.local',
        cpus=2, memory=4096,
        volumes=[hpav_volume, dasd_data_volume, scsi_root_volume],
        interfaces=[(roce_iface, True), (roce_unbound_iface, False),
                    (osa_iface, False), (osa_layer3_iface, False),
                    (hsi_iface, False), (hsi_layer3_iface, False)]
    )

    model = AutoinstallMachineModel(*os_any_ubuntu, system, creds)
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)

    with tmpdir.as_cwd():
        instmachine = SmDebianInstaller(model, platform)

    instmachine.start()
    # assert does not throw


def test_kvm_device_path_ubuntu1610(
        kvm_scsi_system, os_ubuntu16_tuple,
        tmpdir, creds, good_log):
    """ 
    Attempt to install "nothing" on an KVM on SCSI disk
    """
    _, *os_tuple_rest = os_ubuntu16_tuple
    ubuntu1610_tuple = (AutoinstallMachineModel.OperatingSystem(
        'ubuntu16', 'debian', 1610, 0, 'Ubuntu 16.10', None),
        *os_tuple_rest)

    model = AutoinstallMachineModel(*ubuntu1610_tuple,
                                    kvm_scsi_system, creds)
    hyp = plat_kvm.PlatKvm.create_hypervisor(model)
    platform = plat_kvm.PlatKvm(model, hyp)

    # autoinstall machines use their own working directory
    # and have to be initialized in a temporary environment
    with tmpdir.as_cwd():
        smbase = SmDebianInstaller(model, platform)

    smbase.start()

    for volume in model.system_profile.volumes:
        assert '/dev/disk/by-path/virtio-pci-' in volume.device_path
