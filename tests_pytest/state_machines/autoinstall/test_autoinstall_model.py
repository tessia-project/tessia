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
Test Autoinstall model
"""

# pylint: disable=invalid-name  # we have really long test names

#
# IMPORTS
#
from tessia.server.state_machines.autoinstall.model import AutoinstallMachineModel

import pytest

#
# CONSTANTS AND DEFINITIONS
#

# installation credentials
CREDS = {'user': 'unit', 'password': 'test'}

# some default operating system
DEFAULT_OS = AutoinstallMachineModel.OperatingSystem(
    'os', 'linux', 15, 0, 'SupportedOS', None)

# autoinstall template stub
OS_TEMPLATE = AutoinstallMachineModel.Template('os-template', 'and then some')

# installation template stub
INST_TEMPLATE = AutoinstallMachineModel.Template('cmdline.linux.jinja',
                                                 'install-cmdline')

# an unpartitioned DASD volume
DASD_VOLUME = AutoinstallMachineModel.DasdVolume('abcd', 20_000_000)

# an OSA interface
OSA_IFACE = AutoinstallMachineModel.OsaInterface(
    '0b01,0b02,0b03', False, os_device_name='enccw0b01',
    subnets=[AutoinstallMachineModel.SubnetAffiliation(
        ip_address='10.0.0.15', subnet='10.0.0.0/24', gateway='10.0.0.1')])

# a complete LPAR systesm
SYSTEM_LP_DASD = AutoinstallMachineModel.SystemProfile(
    'lp10', 'default',
    hypervisor=AutoinstallMachineModel.HmcHypervisor(
        'hmc', 'hmc.local', {'user': 'user', 'password': 'password'},
        {
            'partition-name': 'LP10',
            'boot-method': 'storage',
            'boot-device': 'da8d',
        }),
    hostname='lp10.local',
    cpus=2, memory=2048,
    volumes=[DASD_VOLUME],
    interfaces=[(OSA_IFACE, True)]
)


#
# CODE
#


def test_model_with_single_repo_is_valid():
    """
    Model may have only one OS repository and be valid
    """
    repos = [AutoinstallMachineModel.OsRepository(
        'os-repo', 'http://example.com/os', '/kernel', '/initrd', None,
        'os', 'Default OS repo')]

    model = AutoinstallMachineModel(DEFAULT_OS, repos, OS_TEMPLATE,
                                    INST_TEMPLATE, [], [],
                                    SYSTEM_LP_DASD, CREDS)

    # does not throw
    model.validate()

    # non-empty
    assert model.operating_system
    assert model.os_repos
    assert model.template

    # no extra packages
    assert not model.package_repos


def test_model_with_multiple_repos_is_valid():
    """
    Multiple repositories for same OS can be specified in the model
    (although only first repo is chosen for installation, model information
     is complete)
    """
    repos = [AutoinstallMachineModel.OsRepository(
        'os-repo', 'http://example.com/os', '/kernel', '/initrd',
        None, 'os', 'Default OS repo'),
        AutoinstallMachineModel.OsRepository(
        'another-os-repo', 'http://example.com/os', '/kernel', '/initrd',
        None, 'os', 'Other OS repo'),
    ]

    model = AutoinstallMachineModel(DEFAULT_OS, repos, OS_TEMPLATE,
                                    INST_TEMPLATE, [], [],
                                    SYSTEM_LP_DASD, CREDS)

    # does not throw
    model.validate()

    # non-empty
    assert model.operating_system
    assert len(model.os_repos) == 2
    assert model.template

    # no extra packages
    assert not model.package_repos


def test_use_repo_for_different_os_as_package_repo():
    """
    Custom OS repository that has different OS is not chosen for installation,
    but is added to package source
    """
    custom_os_repos = [AutoinstallMachineModel.OsRepository(
        'next-os-repo', 'http://example.com/os-next', '/kernel', '/initrd',
        None, 'os-next', 'Next OS repo'),
        AutoinstallMachineModel.OsRepository(
        'os-repo', 'http://example.com/os', '/kernel', '/initrd',
        None, 'os', 'OS repo'),
    ]

    model = AutoinstallMachineModel(DEFAULT_OS, [], OS_TEMPLATE,
                                    INST_TEMPLATE,
                                    custom_os_repos, [],
                                    SYSTEM_LP_DASD, CREDS)

    # does not throw
    model.validate()

    # non-empty
    assert model.operating_system
    assert len(model.os_repos) == 1
    assert model.os_repos[0].name == 'os-repo'
    assert model.template

    # other os repo goes to packages
    assert len(model.package_repos) == 1
    assert model.package_repos[0].name == 'next-os-repo'


def test_model_prefers_custom_os_repos():
    """
    Custom OS repository that has same OS is prioritized over default
    """
    default_os_repos = [AutoinstallMachineModel.OsRepository(
        'os-default-repo', 'http://example.com/os', '/kernel', '/initrd',
        None, 'os', 'Default OS repo')]
    custom_os_repos = [AutoinstallMachineModel.OsRepository(
        'custom-os-repo', 'http://example.com/os-next', '/kernel', '/initrd',
        None, 'os', 'Custom OS repo')]

    model = AutoinstallMachineModel(DEFAULT_OS, default_os_repos,
                                    OS_TEMPLATE, INST_TEMPLATE,
                                    custom_os_repos, [],
                                    SYSTEM_LP_DASD, CREDS)

    # does not throw
    model.validate()

    # non-empty
    assert model.operating_system
    assert len(model.os_repos) == 2
    assert model.os_repos[0].name == 'custom-os-repo'
    assert model.template

    # other os repo goes to packages
    assert not model.package_repos


def test_model_rejects_invalid_partitioning(
        default_os_tuple, osa_iface, zvm_hypervisor, creds):
    """
    When volume partitions exceed volume size, model is rejected
    """

    volume = AutoinstallMachineModel.ZfcpVolume(
            'cd0f0000', 20_000, multipath=True,
            wwid='36005076309ffd435000000000000cd0f')
    volume.set_partitions('msdos', [{
        'mount_point': '/',
        'size': 19_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }, {
        'mount_point': '',
        'size': 2_000,
        'filesystem': 'swap',
        'part_type': 'primary',
        'mount_opts': None,
    }])
    system_profile = AutoinstallMachineModel.SystemProfile(
        'vm25', 'default',
        hypervisor=zvm_hypervisor,
        hostname='vm25.local',
        cpus=4, memory=8192,
        volumes=[volume],
        interfaces=[(osa_iface, True)]
    )
    model = AutoinstallMachineModel(*default_os_tuple,
                                    system_profile, creds)

    with pytest.raises(ValueError, match="exceeds volume size"):
        model.validate()
