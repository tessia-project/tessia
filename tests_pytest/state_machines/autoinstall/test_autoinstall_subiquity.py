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
Test Subiquity autoinstall machine
"""

# pylint: disable=invalid-name  # we have really long test names
# pylint: disable=redefined-outer-name  # use of fixtures
# pylint: disable=unused-argument  # use of fixtures for their side effects

#
# IMPORTS
#

from json import dumps, loads
from pathlib import Path
from tessia.server.state_machines.autoinstall import sm_subiquity
from tessia.server.config import Config
from tessia.server.state_machines.autoinstall import sm_base, plat_base
from tessia.server.state_machines.autoinstall import plat_lpar, plat_zvm, plat_kvm
from tessia.server.state_machines.autoinstall.model import AutoinstallMachineModel
from tessia.server.state_machines.autoinstall.sm_subiquity import SmSubiquityInstaller
from tests_pytest.state_machines.null_hypervisor import NullHypervisor
from tests_pytest.state_machines.ssh_stub import SshClient

import pytest

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


class MockLogStream:
    """
    Event stream with given responses
    """
    class JsonResponse:
        """
        JSON response object
        """

        def __init__(self, status_code=200, data=None) -> None:
            self._status_code = status_code
            self._data = data

        def json(self):
            """Return stored object"""
            return self._data

        @property
        def status_code(self):
            """Return status code"""
            return self._status_code

    def __init__(self, responses) -> None:
        self._responses = responses

    def post(self, url: str, json: dict = None):
        """
        Mock POST request to open a new session
        """
        return MockLogStream.JsonResponse(status_code=201)

    def delete(self, url: str):
        """
        Delete a session
        """

    def close(self):
        """
        Close connection
        """

    def get(self, url: str, params: dict = None):
        """
        Set return values for commands
        """
        if not self._responses:
            return MockLogStream.JsonResponse(data=[])

        return MockLogStream.JsonResponse(data=[self._responses.pop(0)])


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
            },
            'installer-webhook': {
                'control_port': 1234,
                'webhook_port': 2345
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


@pytest.fixture(autouse=True)
def mock_sleep_and_time(monkeypatch):
    """
    Subiquity uses sleep and monotonic timings,
    so we speed it up for tests
    """
    def _speed_clock():
        time = 0
        while True:
            time += 1.1
            yield time
    clock = _speed_clock()

    monkeypatch.setattr(sm_subiquity, 'sleep', lambda x: x)
    monkeypatch.setattr(sm_subiquity, 'monotonic', lambda: next(clock))


@pytest.fixture(params=["ubuntu20"])
def os_any_ubuntu(request, os_ubuntu20_subiquity_tuple):
    """
    Enable test for multiple OS
    """
    yield {
        'ubuntu20': os_ubuntu20_subiquity_tuple
    }[request.param]


@pytest.fixture
def os_ubuntu2004():
    """
    Ubuntu 20.04 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu20', 'debian', 2004, 0, 'Ubuntu 20.04 LTS', None)


@pytest.fixture
def os_ubuntu2004_1():
    """
    Ubuntu 20.04.1 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu20', 'debian', 2004, 1, 'Ubuntu 20.04.1 LTS', None)


@pytest.fixture
def os_ubuntu2004_2():
    """
    Ubuntu 20.04.2 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu20', 'debian', 2004, 2, 'Ubuntu 20.04.2 LTS', None)


@pytest.fixture
def os_ubuntu2010():
    """
    Ubuntu 20.10 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu20', 'debian', 2010, 0, 'Ubuntu 20.10 LTS', None)


@pytest.fixture
def os_ubuntu2104():
    """
    Ubuntu 21.04 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu21', 'debian', 2104, 0, 'Ubuntu 21.04 LTS', None)

    
@pytest.fixture
def os_ubuntu2204():
    """
    Ubuntu 22.04 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu22', 'debian', 2204, 0, 'Ubuntu 22.04 LTS', None)

@pytest.fixture
def os_ubuntu2210():
    """
    Ubuntu 22.10 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu22', 'debian', 2210, 0, 'Ubuntu 22.10', None)

@pytest.fixture
def os_ubuntu2304():
    """
    Ubuntu 23.04 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu23', 'debian', 2304, 0, 'Ubuntu 23.04', None)

@pytest.fixture
def good_log(monkeypatch):
    """
    Set good log sequence
    """
    def good_session():
        return MockLogStream([
            dumps({'name': 'subiquity/Reboot/reboot',
                   'result': 'SUCCESS', 'event_type': 'finish'})
        ])
    monkeypatch.setattr(sm_subiquity.requests, 'Session', good_session)


@pytest.fixture
def fail_log(monkeypatch):
    """
    Set failing log sequence
    """
    def failed_session():
        return MockLogStream([
            dumps({'name': 'traceback', 'event_type': 'log_dump',
                   'origin': 'watchdog', 'result': 'SUCCESS'}),
            'binary:traceback:20480',
            dumps({'name': 'subiquity/ErrorReporter',
                   'result': 'SUCCESS', 'event_type': 'finish',
                   'description': 'written to /var/crash/request_fail'}),
        ])
    monkeypatch.setattr(sm_subiquity.requests, 'Session', failed_session)


class TestSubiquityRebootTriggers:
    """
    Subiquity state machine should find a "reboot" event to continue
    on to the next stage. This class contains tests for different
    Ubuntu versions with data from actual installations
    """
    @pytest.fixture(autouse=True)
    def load_data_streams(self):
        """
        Provide data streams
        """
        self._streams = loads(
            (Path(__file__).parent.resolve() /
             "data" / "ubuntu_streams.json").read_text())

    @pytest.fixture(autouse=True)
    def log_stream(self, monkeypatch):
        """
        Event sequence
        """
        def set_log_stream(ubuntu_version):
            event_list = self._streams[ubuntu_version]
            stream = MockLogStream([dumps(entry) for entry in event_list])
            monkeypatch.setattr(sm_subiquity.requests, 'Session',
                                lambda: stream)
        self._set_log_stream = set_log_stream

    @pytest.fixture(autouse=True)
    def default_machine(self, kvm_scsi_system, creds, tmpdir):
        """
        Create autoinstall machine from tuple

        For these tests machine type is irrelevant
        """
        def make_machine(os_tuple):
            model = AutoinstallMachineModel(*os_tuple, kvm_scsi_system, creds)
            hyp = plat_kvm.PlatKvm.create_hypervisor(model)
            platform = plat_kvm.PlatKvm(model, hyp)

            with tmpdir.as_cwd():
                instmachine = SmSubiquityInstaller(model, platform)

            return instmachine
        self._make_machine = make_machine

    @pytest.mark.parametrize("tag,os", [
        ("ubuntu20.04", pytest.lazy_fixture('os_ubuntu2004')),
        ("ubuntu20.04.1", pytest.lazy_fixture('os_ubuntu2004_1')),
        ("ubuntu20.04.2", pytest.lazy_fixture('os_ubuntu2004_2')),
        ("ubuntu20.10", pytest.lazy_fixture('os_ubuntu2010')),
    ])
    def test_ubuntu20(self, tag, os, os_ubuntu20_subiquity_tuple):
        """
        Test triggers for Ubuntu 20 using recorded event streams
        """
        _, *os_tuple_rest = os_ubuntu20_subiquity_tuple
        os_tuple = (os, *os_tuple_rest)
        self._set_log_stream(tag)
        instmachine = self._make_machine(os_tuple)

        instmachine.start()
        # assert does not throw

    @pytest.mark.parametrize("tag,os", [
        ("ubuntu21.04", pytest.lazy_fixture('os_ubuntu2104')),
    ])
    def test_ubuntu21(self, tag, os, os_ubuntu21_subiquity_tuple):
        """
        Test triggers for Ubuntu 21 using recorded event streams
        """
        _, *os_tuple_rest = os_ubuntu21_subiquity_tuple
        os_tuple = (os, *os_tuple_rest)
        self._set_log_stream(tag)
        instmachine = self._make_machine(os_tuple)

        instmachine.start()
        # assert does not throw

    @pytest.mark.parametrize("tag,os", [
        ("ubuntu22.04", pytest.lazy_fixture('os_ubuntu2204')),
        ("ubuntu22.10", pytest.lazy_fixture('os_ubuntu2210')),
    ])
    def test_ubuntu22(self, tag, os, os_ubuntu22_subiquity_tuple):
        """
        Test triggers for Ubuntu 22 using recorded event streams
        """
        _, *os_tuple_rest = os_ubuntu22_subiquity_tuple
        os_tuple = (os, *os_tuple_rest)
        self._set_log_stream(tag)
        instmachine = self._make_machine(os_tuple)

        instmachine.start()
        # assert does not throw

    @pytest.mark.parametrize("tag,os", [
        ("ubuntu23.04", pytest.lazy_fixture('os_ubuntu2304')),
    ])
    def test_ubuntu23(self, tag, os, os_ubuntu23_subiquity_tuple):
        """
        Test triggers for Ubuntu 23 using recorded event streams
        """
        _, *os_tuple_rest = os_ubuntu23_subiquity_tuple
        os_tuple = (os, *os_tuple_rest)
        self._set_log_stream(tag)
        instmachine = self._make_machine(os_tuple)

        instmachine.start()
        # assert does not throw

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

    scsi_data_volume = AutoinstallMachineModel.ZfcpVolume(
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

    scsi_predefined_volume = AutoinstallMachineModel.ZfcpVolume(
        '40a040b400c800dd', 15_000, multipath=True,
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
        instmachine = SmSubiquityInstaller(model, platform)

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

    scsi_data_volume = AutoinstallMachineModel.ZfcpVolume(
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
    }, {
        'mount_point': '/data-4',
        'size': 3_000,
        'filesystem': 'xfs',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
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
        instmachine = SmSubiquityInstaller(model, platform)

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

    scsi_root_volume = AutoinstallMachineModel.ZfcpVolume(
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
    }, {
        'mount_point': '/data-4',
        'size': 3_000,
        'filesystem': 'xfs',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
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
        instmachine = SmSubiquityInstaller(model, platform)

    instmachine.start()
    # assert does not throw


def test_failed_installation_on_text_trigger(
        kvm_scsi_system, os_any_ubuntu, creds,
        tmpdir, fail_log):
    """Test Subiquity fail when a special line is found"""
    model = AutoinstallMachineModel(*os_any_ubuntu, kvm_scsi_system, creds)
    hyp = plat_kvm.PlatKvm.create_hypervisor(model)
    platform = plat_kvm.PlatKvm(model, hyp)

    with tmpdir.as_cwd():
        instmachine = SmSubiquityInstaller(model, platform)

    with pytest.raises(RuntimeError,
                       match='Installation could not be completed'):
        instmachine.start()
