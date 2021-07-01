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
Test Anaconda autoinstall specifics

Anaconda autoinstaller is based on SmBase, but contains parts specific
to anaconda-based installers.
"""

# pylint: disable=invalid-name  # we have really long test names
# pylint: disable=redefined-outer-name  # use of fixtures
# pylint: disable=unused-argument  # use of fixtures for their side effects

#
# IMPORTS
#

from tessia.server.config import Config
from tessia.server.state_machines.autoinstall.sm_anaconda import SmAnaconda
from tessia.server.state_machines.autoinstall import sm_base, plat_base
from tessia.server.state_machines.autoinstall import plat_lpar, plat_zvm, plat_kvm
from tessia.server.state_machines.autoinstall.model import AutoinstallMachineModel
from tests_pytest.state_machines.null_hypervisor import NullHypervisor
from tests_pytest.state_machines.ssh_stub import SshClient, SshShell

import os
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
            '/tmp/anaconda.log':
                "03:25:38,829 DBG ui.gui.spokes.installation_progress:"
                " The installation has finished."
        }
        return SshShell(responses)


class FailLogSsh(SshClient):
    """
    Ssh that returns a session with failing responses
    """

    def open_shell(self, chroot_dir=None, shell_path=None):
        """
        Set return values for commands
        """
        responses = {
            '/tmp/anaconda.log':
                "03:25:38,825 ERR anaconda: storage configuration failed:"
                " validate test failure"
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
    """Set hypevisor stub"""
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


@pytest.fixture
def good_log(monkeypatch):
    """
    Set good log sequence
    """
    monkeypatch.setattr(sm_base, 'SshClient', GoodLogSsh)


@pytest.fixture
def fail_log(monkeypatch):
    """
    Set failing log sequence
    """
    monkeypatch.setattr(sm_base, 'SshClient', FailLogSsh)


def test_systemd_osa_name_rhel7(hmc_hypervisor,
                                scsi_volume, os_rhel7_tuple, creds,
                                tmpdir):
    """Test anaconda state machine"""
    osa_iface1 = AutoinstallMachineModel.OsaInterface(
        '0b01,0b02,0b03', False, os_device_name='enccw0b01',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.0.15', subnet='10.0.0.0/24', gateway='10.0.0.1')])
    osa_iface2 = AutoinstallMachineModel.OsaInterface(
        'abcd,abce,abcf', False, os_device_name='enccwabcd',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.8.0.15', subnet='10.8.0.0/24', gateway='10.8.0.1')])
    system = AutoinstallMachineModel.SystemProfile(
        'lp10', 'default',
        hypervisor=hmc_hypervisor,
        hostname='lp10.local',
        cpus=2, memory=8192,
        volumes=[scsi_volume],
        interfaces=[(osa_iface1, True), (osa_iface2, False)]
    )
    model = AutoinstallMachineModel(*os_rhel7_tuple, system, creds)
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)

    with tmpdir.as_cwd():
        autofile_dir = os.getcwd()
        instmachine = SmAnaconda(model, platform)
    instmachine.init_target()
    instmachine.fill_template_vars()
    instmachine.create_autofile()
    instmachine.boot_installer()

    with open(os.path.join(autofile_dir, 'lp10-default')) as f:
        autofile = f.read()

    # both cards mentioned in autofile
    assert 'network --bootproto=static --device=enccw0b01' in autofile
    assert 'network --bootproto=static --device=enccwabcd' in autofile

    attrs = hyp.start.last_call[3]
    # RHEL <= 7: IP configuration with "enccw" name
    assert 'enccw0b01:none' in attrs['boot_params']['netboot']['cmdline']
    # other card is not mentioned in cmdline
    assert 'enccwabcd' not in attrs['boot_params']['netboot']['cmdline']


def test_systemd_osa_name_rhel8(zvm_hypervisor,
                                dasd_volume, os_rhel8_tuple, creds,
                                tmpdir):
    """Test anaconda state machine"""
    osa_iface1 = AutoinstallMachineModel.OsaInterface(
        '0b01,0b02,0b03', False, os_device_name='enccw0b01',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.0.15', subnet='10.0.0.0/24', gateway='10.0.0.1')])
    osa_iface2 = AutoinstallMachineModel.OsaInterface(
        'abcd,abce,abcf', False, os_device_name='enccwabcd',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.8.0.15', subnet='10.8.0.0/24', gateway='10.8.0.1')])
    system = AutoinstallMachineModel.SystemProfile(
        'vm25', 'two-osa',
        hypervisor=zvm_hypervisor,
        hostname='vm25.local',
        cpus=2, memory=8192,
        volumes=[dasd_volume],
        interfaces=[(osa_iface1, True), (osa_iface2, False)]
    )
    model = AutoinstallMachineModel(*os_rhel8_tuple, system, creds)
    hyp = plat_zvm.PlatZvm.create_hypervisor(model)
    platform = plat_zvm.PlatZvm(model, hyp)

    with tmpdir.as_cwd():
        autofile_dir = os.getcwd()
        instmachine = SmAnaconda(model, platform)
    instmachine.init_target()
    instmachine.fill_template_vars()
    instmachine.create_autofile()
    instmachine.boot_installer()

    with open(os.path.join(autofile_dir, 'vm25-two-osa')) as f:
        autofile = f.read()

    # both cards mentioned in autofile
    assert 'network --bootproto=static --device=encb01' in autofile
    assert 'network --bootproto=static --device=encabcd' in autofile

    attrs = hyp.start.last_call[3]
    # RHEL >= 8: IP configuration with "enc" name
    assert 'encb01:none' in attrs['netboot']['cmdline']
    # other card is not mentioned in cmdline
    assert 'encabcd' not in attrs['netboot']['cmdline']


def test_fail_on_low_memory(hmc_hypervisor, osa_iface,
                            scsi_volume, os_rhel7_tuple, creds,
                            tmpdir):
    """Test anaconda failing when too little memory defined"""
    system = AutoinstallMachineModel.SystemProfile(
        'lp10', 'default',
        hypervisor=hmc_hypervisor,
        hostname='lp10.local',
        cpus=2, memory=1024,
        volumes=[scsi_volume],
        interfaces=[(osa_iface, True)]
    )
    model = AutoinstallMachineModel(*os_rhel7_tuple, system, creds)
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)

    with tmpdir.as_cwd():
        with pytest.raises(ValueError, match='require at least .* memory'):
            instmachine = SmAnaconda(model, platform)
            instmachine.start()


def test_success_installation_on_text_trigger(
        kvm_scsi_system, os_rhel7_tuple, creds,
        tmpdir, monkeypatch):
    """Test anaconda succeed when a special line is provided"""
    model = AutoinstallMachineModel(*os_rhel7_tuple, kvm_scsi_system, creds)
    hyp = plat_kvm.PlatKvm.create_hypervisor(model)
    platform = plat_kvm.PlatKvm(model, hyp)
    # set good log
    monkeypatch.setattr(sm_base, 'SshClient', GoodLogSsh)

    with tmpdir.as_cwd():
        instmachine = SmAnaconda(model, platform)

    instmachine.start()
    # assert does not throw


def test_fail_installation_on_text_trigger(
        vm_scsi_system, os_rhel8_tuple, creds,
        tmpdir, fail_log):
    """Test anaconda succeed when a special line is provided"""
    model = AutoinstallMachineModel(*os_rhel8_tuple, vm_scsi_system, creds)
    hyp = plat_zvm.PlatZvm.create_hypervisor(model)
    platform = plat_zvm.PlatZvm(model, hyp)

    with tmpdir.as_cwd():
        instmachine = SmAnaconda(model, platform)

    with pytest.raises(RuntimeError, match='storage configuration failed'):
        instmachine.start()


def test_kvm_device_path_rhel74(
        kvm_scsi_system, os_rhel7_tuple, creds,
        tmpdir, good_log):
    """
    Attempt to install "nothing" on an KVM on SCSI disk
    """
    _, *os_tuple_rest = os_rhel7_tuple
    rhel74_tuple = (AutoinstallMachineModel.OperatingSystem(
        'rhel7', 'redhat', 7, 4, 'Red Hat Enterprise Linux 7.4 (Maipo)', None),
        *os_tuple_rest)

    model = AutoinstallMachineModel(*rhel74_tuple,
                                    kvm_scsi_system, creds)
    hyp = plat_kvm.PlatKvm.create_hypervisor(model)
    platform = plat_kvm.PlatKvm(model, hyp)

    # autoinstall machines use their own working directory
    # and have to be initialized in a temporary environment
    with tmpdir.as_cwd():
        smbase = SmAnaconda(model, platform)

    smbase.start()

    for volume in model.system_profile.volumes:
        assert '/dev/disk/by-path/virtio-pci-' in volume.device_path
