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
Test base autoinstall machine

A smallest implementation on SmBase is used to test common features
"""

# pylint: disable=invalid-name  # we have really long test names
# pylint: disable=redefined-outer-name  # use of fixtures
# pylint: disable=unused-argument  # use of fixtures for their side effects

#
# IMPORTS
#
from pathlib import Path
from tessia.baselib.hypervisors.hmc.volume_descriptor import FcpVolumeDescriptor
from tessia.server.config import Config
from tessia.server.state_machines.autoinstall import plat_lpar, plat_zvm, plat_kvm
from tessia.server.state_machines.autoinstall import plat_base, sm_base
from tessia.server.state_machines.autoinstall.model import AutoinstallMachineModel
from tessia.server.state_machines.autoinstall.sm_base import SmBase
from tests_pytest.decorators import tracked
from tests_pytest.state_machines.ssh_stub import SshClient
from tests_pytest.state_machines.null_hypervisor import NullHypervisor

import pytest
import yaml

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


class NullMachine(SmBase):
    """
    Concrete SmBase implementation

    This implementation helps trigger all common paths without having
    any distro specifics (i.e. termination conditions or log lines)
    """

    def __init__(self, model: AutoinstallMachineModel,
                 platform: plat_base.PlatBase, *args, **kwargs):
        """
        Initialize SmBase
        """
        super().__init__(model, platform, *args, **kwargs)

    @property
    @classmethod
    def DISTRO_TYPE(cls):  # pylint: disable=invalid-name
        """
        Return the type of linux distribution supported.
        """
        return "null"
    # DISTRO_TYPE

    def wait_install(self):
        """
        Consider operating system installed and return immediately
        """
    # wait_install()


class NullPostInstallChecker:
    """
    PostInstallChecked that checks that it has been called
    """

    @tracked
    def verify(self):
        """
        Public method to verify installed system
        """
        return []


class TestModelUpdate:
    """
    Test model updates during autoinstallation
    """

    class UpdatingHypervisor(NullHypervisor):
        """
        Hypervisor that returns some valid data about storage volumes
        """

        @tracked
        def query_dpm_storage_devices(self, guest_name):
            """Query storage devices on DPM"""
            return [
                FcpVolumeDescriptor(
                    **{'uri': '/api/storage-volumes/1', 'attachment': 'fcp',
                       'is_fulfilled': True, 'size': 19.07,
                       'uuid': '6005076309FFD435000000000000CD0F',
                       'paths': [{'device_nr': 'FC00',
                                  'wwpn': '5005076309049435',
                                  'lun': 'CD0F0000'}]
                       })]

    @pytest.fixture
    def scsi_volume_without_paths(self):
        """
        A single-partition SCSI volume
        """
        result = AutoinstallMachineModel.ZfcpVolume(
            'cd0f0000', 20_000_000, multipath=True,
            wwid='36005076309ffd435000000000000cd0f')
        result.set_partitions('msdos', [{
            'mount_point': '/data',
            'size': 18_000,
            'filesystem': 'ext4',
            'part_type': 'primary',
            'mount_opts': None,
        }])
        yield result

    @pytest.fixture(autouse=True)
    def mock_hypervisors(self, monkeypatch):
        """
        Use hypevisor stub instead of real sessions
        """
        monkeypatch.setattr(plat_lpar, 'HypervisorHmc',
                            TestModelUpdate.UpdatingHypervisor)

    def test_model_update_adds_fcp_paths(
            self, lpar_scsi_system, default_os_tuple, creds, tmpdir,
            scsi_volume_without_paths):
        """
        Attempt to install "nothing" on an LPAR on SCSI disk
        Verify that hypervisor is called with correct parameters
        and post-install checker is run
        """
        model = AutoinstallMachineModel(*default_os_tuple,
                                        lpar_scsi_system, creds)
        model.system_profile.add_volume(scsi_volume_without_paths)
        checker = NullPostInstallChecker()
        hyp = plat_lpar.PlatLpar.create_hypervisor(model)
        platform = plat_lpar.PlatLpar(model, hyp)
        # autoinstall machines use their own working directory
        # and have to be initialized in a temporary environment
        with tmpdir.as_cwd():
            smbase = NullMachine(model, platform, checker)

        smbase.start()

        assert len(model.system_profile.volumes) == 2
        assert model.system_profile.volumes[1].paths


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
    """
    Use hypevisor stub instead of real sessions
    """
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


def test_boot_and_postinstall_check_on_lpar_dasd(
        lpar_dasd_system, default_os_tuple, creds, tmpdir):
    """
    Attempt to install "nothing" on an LPAR on DASD disk
    Verify that hypervisor is called with correct parameters
    and post-install checker is run
    """
    model = AutoinstallMachineModel(*default_os_tuple,
                                    lpar_dasd_system, creds)
    checker = NullPostInstallChecker()
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)

    # autoinstall machines use their own working directory
    # and have to be initialized in a temporary environment
    with tmpdir.as_cwd():
        smbase = NullMachine(model, platform, checker)

    smbase.start()

    assert checker.verify.called_once
    sys, cpus, mem, attrs, *_ = hyp.start.calls[0]
    assert sys == lpar_dasd_system.hypervisor.boot_options['partition-name']
    assert cpus == lpar_dasd_system.cpus
    assert mem == lpar_dasd_system.memory
    # installation device does not show up in HmcHypervisor boot,
    # it is only used later during installation
    assert attrs['boot_params']['boot_method'] == 'dasd'
    assert attrs['boot_params']['devicenr'] == \
        lpar_dasd_system.hypervisor.boot_options['boot-device']


def test_boot_and_postinstall_check_on_lpar_scsi(
        lpar_scsi_system, default_os_tuple, creds, tmpdir):
    """
    Attempt to install "nothing" on an LPAR on SCSI disk
    Verify that hypervisor is called with correct parameters
    and post-install checker is run
    """
    model = AutoinstallMachineModel(*default_os_tuple,
                                    lpar_scsi_system, creds)
    checker = NullPostInstallChecker()
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)
    # autoinstall machines use their own working directory
    # and have to be initialized in a temporary environment
    with tmpdir.as_cwd():
        smbase = NullMachine(model, platform, checker)

    smbase.start()

    assert checker.verify.called_once
    sys, cpus, mem, attrs, *_ = hyp.start.calls[0]
    assert sys == lpar_scsi_system.hypervisor.boot_options['partition-name']
    assert cpus == lpar_scsi_system.cpus
    assert mem == lpar_scsi_system.memory
    # installation device does not show up in HmcHypervisor boot,
    # it is only used later during installation
    assert attrs['boot_params']['boot_method'] == 'dasd'
    assert attrs['boot_params']['devicenr'] == \
        lpar_scsi_system.hypervisor.boot_options['boot-device']

def test_boot_and_postinstall_check_on_lpar_nvme(
        lpar_nvme_system, default_os_tuple, creds, tmpdir):
    """
    Attempt to install "nothing" on an LPAR on NVME disk
    Verify that hypervisor is called with correct parameters
    and post-install checker is run
    """
    model = AutoinstallMachineModel(*default_os_tuple,
                                    lpar_nvme_system, creds)
    checker = NullPostInstallChecker()
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)

    # autoinstall machines use their own working directory
    # and have to be initialized in a temporary environment
    with tmpdir.as_cwd():
        smbase = NullMachine(model, platform, checker)

    smbase.start()

    assert checker.verify.called_once
    sys, cpus, mem, attrs, *_ = hyp.start.calls[0]
    assert sys == lpar_nvme_system.hypervisor.boot_options['partition-name']
    assert cpus == lpar_nvme_system.cpus
    assert mem == lpar_nvme_system.memory
    # installation device does not show up in HmcHypervisor boot,
    # it is only used later during installation
    assert attrs['boot_params']['boot_method'] == 'dasd'
    assert attrs['boot_params']['devicenr'] == \
        lpar_nvme_system.hypervisor.boot_options['boot-device']

def test_boot_and_postinstall_check_on_vm_dasd(
        vm_dasd_system, default_os_tuple, creds, tmpdir):
    """
    Attempt to install "nothing" on a VM on DASD disk
    Verify that hypervisor is called with correct parameters
    and post-install checker is run
    """
    model = AutoinstallMachineModel(*default_os_tuple,
                                    vm_dasd_system, creds)
    checker = NullPostInstallChecker()
    hyp = plat_zvm.PlatZvm.create_hypervisor(model)
    platform = plat_zvm.PlatZvm(model, hyp)
    # autoinstall machines use their own working directory
    # and have to be initialized in a temporary environment
    with tmpdir.as_cwd():
        smbase = NullMachine(model, platform, checker)

    smbase.start()

    assert checker.verify.called_once
    sys, cpus, mem, attrs, *_ = hyp.start.calls[0]
    assert sys == vm_dasd_system.system_name
    assert cpus == vm_dasd_system.cpus
    assert mem == vm_dasd_system.memory
    assert vm_dasd_system.volumes[0].device_id == \
        attrs['storage_volumes'][0]['devno']


def test_boot_and_postinstall_check_on_vm_scsi(
        vm_scsi_system, default_os_tuple, creds, tmpdir):
    """
    Attempt to install "nothing" on a VM on SCSI disk
    Verify that hypervisor is called with correct parameters
    and post-install checker is run
    """
    model = AutoinstallMachineModel(*default_os_tuple,
                                    vm_scsi_system, creds)
    checker = NullPostInstallChecker()
    hyp = plat_zvm.PlatZvm.create_hypervisor(model)
    platform = plat_zvm.PlatZvm(model, hyp)

    # autoinstall machines use their own working directory
    # and have to be initialized in a temporary environment
    with tmpdir.as_cwd():
        smbase = NullMachine(model, platform, checker)

    smbase.start()

    assert checker.verify.called_once
    sys, cpus, mem, attrs, *_ = hyp.start.calls[0]
    assert sys == vm_scsi_system.system_name
    assert cpus == vm_scsi_system.cpus
    assert mem == vm_scsi_system.memory
    assert vm_scsi_system.volumes[0].lun == \
        attrs['storage_volumes'][0]['lun']


def testboot_and_postinstall_check_on_kvm_scsi(
        kvm_scsi_system, default_os_tuple, creds, tmpdir):
    """
    Attempt to install "nothing" on a KVM on SCSI disk
    Verify correct device paths
    and that hypervisor is called with correct parameters
    and post-install checker is run
    """
    model = AutoinstallMachineModel(*default_os_tuple,
                                    kvm_scsi_system, creds)
    checker = NullPostInstallChecker()
    hyp = plat_kvm.PlatKvm.create_hypervisor(model)
    platform = plat_kvm.PlatKvm(model, hyp)

    # autoinstall machines use their own working directory
    # and have to be initialized in a temporary environment
    with tmpdir.as_cwd():
        smbase = NullMachine(model, platform, checker)

    smbase.start()

    assert checker.verify.called_once
    sys, cpus, mem, attrs, *_ = hyp.start.calls[0]
    assert sys == kvm_scsi_system.system_name
    assert cpus == kvm_scsi_system.cpus
    assert mem == kvm_scsi_system.memory
    assert kvm_scsi_system.volumes[0].lun == \
        attrs['storage_volumes'][0]['volume_id']
    for volume in model.system_profile.volumes:
        assert '/dev/disk/by-path/ccw' in volume.device_path


def test_network_boot_on_lpar_scsi(
        scsi_volume, osa_iface, default_os_tuple, creds, tmpdir):
    """
    Attempt to install "nothing" on an LPAR on SCSI disk
    using network boot
    Verify that hypervisor is called with correct parameters
    """
    ins_file = 'user@password:inst.local/some-os/boot.ins'
    hmc_hypervisor = AutoinstallMachineModel.HmcHypervisor(
        'hmc', 'hmc.local',
        {'user': '', 'password': ''},
        {
            'partition-name': 'LP10',
            'boot-method': 'network',
            'boot-uri': 'ftp://' + ins_file,
        })
    system = AutoinstallMachineModel.SystemProfile(
        'lp10', 'default',
        hypervisor=hmc_hypervisor,
        hostname='lp10.local',
        cpus=2, memory=8192,
        volumes=[scsi_volume],
        interfaces=[(osa_iface, True)]
    )
    model = AutoinstallMachineModel(*default_os_tuple, system, creds)
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)

    with tmpdir.as_cwd():
        smbase = NullMachine(model, platform)

    smbase.start()

    sys, cpus, mem, attrs, *_ = hyp.start.calls[0]
    assert sys == hmc_hypervisor.boot_options['partition-name']
    assert cpus == system.cpus
    assert mem == system.memory

    assert attrs['boot_params']['boot_method'] == 'ftp'
    assert attrs['boot_params']['insfile'] == ins_file


def test_template_lpar_dasd(lpar_dasd_system, default_os_tuple, creds, tmpdir):
    """
    Test major template parameters
    """
    *os_tuple, _, _ = default_os_tuple
    package_repo = AutoinstallMachineModel.PackageRepository(
        'aux', 'http://example.com/repo', 'package repo')

    model = AutoinstallMachineModel(
        *os_tuple, [], [package_repo], lpar_dasd_system, creds)
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)

    with tmpdir.as_cwd():
        smbase = NullMachine(model, platform)
        autofile_path = (Path.cwd() / 'lp10-default')

    smbase.start()
    autofile = yaml.safe_load(autofile_path.read_text())

    assert autofile['system']['type'] == 'LPAR'
    assert autofile['system']['hostname'] == 'lp10.local'
    assert autofile['gw_iface']['type'] == 'OSA'
    assert autofile['gw_iface']['osname'] == 'enccw0b01'
    assert autofile['gw_iface']['search_list'] == ['example.com', 'local']
    assert autofile['ifaces'][0]['osname'] == 'enccw0b01'
    assert autofile['volumes'][0]['type'] == 'DASD'
    assert autofile['volumes'][0]['partitions'] == [
        {'fs': 'ext4', 'mp': '/', 'size': '18000M'}
    ]
    assert autofile['repos'][0]['name'] == 'os-repo'
    assert autofile['repos'][1]['name'] == 'aux'


def test_template_kvm_scsi(kvm_scsi_system, default_os_tuple, creds, tmpdir):
    """
    Test major template parameters
    """
    model = AutoinstallMachineModel(*default_os_tuple,
                                    kvm_scsi_system, creds)
    hyp = plat_kvm.PlatKvm.create_hypervisor(model)
    platform = plat_kvm.PlatKvm(model, hyp)

    with tmpdir.as_cwd():
        smbase = NullMachine(model, platform)
        autofile_path = (Path.cwd() / 'kvm54-default')

    smbase.start()
    autofile = yaml.safe_load(autofile_path.read_text())

    assert autofile['system']['type'] == 'KVM'
    assert autofile['system']['hostname'] == 'kvm54.local'
    assert autofile['gw_iface']['type'] == 'MACVTAP'
    assert autofile['gw_iface']['osname'] == 'eth0'
    assert autofile['ifaces'][0]['is_gateway']
