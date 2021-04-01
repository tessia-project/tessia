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
Test Autoyast autoinstall machine
"""

# pylint: disable=invalid-name  # we have really long test names
# pylint: disable=redefined-outer-name  # use of fixtures
# pylint: disable=unused-argument  # use of fixtures for their side effects

#
# IMPORTS
#

from tessia.server.config import Config
from tessia.server.state_machines.autoinstall import sm_autoyast
from tessia.server.state_machines.autoinstall import sm_base, plat_base
from tessia.server.state_machines.autoinstall import plat_lpar, plat_zvm, plat_kvm
from tessia.server.state_machines.autoinstall.model import AutoinstallMachineModel
from tessia.server.state_machines.autoinstall.sm_autoyast import SmAutoyast
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
            '/var/log/YaST2/y2log': '',  # indicate end of file
            "pgrep '^yast2'": (1, 'Installer process not found'),
            "true": (-1, 'Reached reboot')
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


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """
    Autoyast uses too much sleep in its code,
    so we speed it up for tests
    """
    monkeypatch.setattr(sm_autoyast, 'sleep', lambda x: x)


@pytest.fixture(params=["sles12", "sles15"])
def os_any_sles(request, os_sles12_tuple, os_sles15_tuple):
    """
    Enable test for multiple OS
    """
    yield {
        'sles12': os_sles12_tuple,
        'sles15': os_sles15_tuple
    }[request.param]


@pytest.fixture
def good_log(monkeypatch):
    """
    Set good log sequence
    """
    monkeypatch.setattr(sm_base, 'SshClient', GoodLogSsh)


def test_sles_success_installation_on_text_trigger(
        lpar_scsi_system, os_any_sles, creds,
        tmpdir, good_log):
    """Test autoyast succeed when a special line is provided"""
    model = AutoinstallMachineModel(*os_any_sles, lpar_scsi_system, creds)
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)

    with tmpdir.as_cwd():
        instmachine = SmAutoyast(model, platform)

    instmachine.start()
    # assert does not throw


def test_sles_fail_unsupported_roce(
        hmc_hypervisor, roce_iface,
        scsi_volume, os_any_sles, creds,
        tmpdir, good_log):
    """Autoyast should fail when a RoCE card is used as gateway interface"""
    system = AutoinstallMachineModel.SystemProfile(
        'lp10', 'default',
        hypervisor=hmc_hypervisor,
        hostname='lp10.local',
        cpus=2, memory=1024,
        volumes=[scsi_volume],
        interfaces=[(roce_iface, True)]
    )
    model = AutoinstallMachineModel(*os_any_sles, system, creds)
    hyp = plat_lpar.PlatLpar.create_hypervisor(model)
    platform = plat_lpar.PlatLpar(model, hyp)

    with tmpdir.as_cwd():
        with pytest.raises(ValueError,
                           match='using a ROCE card as the gateway'):
            instmachine = SmAutoyast(model, platform)
            instmachine.start()
