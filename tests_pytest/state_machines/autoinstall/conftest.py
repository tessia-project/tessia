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
Test configuration

Contains fixtures for unit tests (i.e. static and generated data,
helpers etc)

Fixtures for resources are provided with reasonable settings
and should be used when test does not care for details
and only expects something suitable to run. These fixtures
are not suitable to test the resource they are representing.
"""

#
# IMPORTS
#
from pathlib import Path
from tessia.server.state_machines.autoinstall.model import AutoinstallMachineModel

import os
import pytest


#
# CONSTANTS AND DEFINITIONS
#
# Directory containing the os templates
TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "../../../tessia/server/db/templates/")
# directory containing the kernel cmdline templates
CMDLINE_TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "../../../tessia/server/state_machines/autoinstall/templates/")

#
# CODE
#


@pytest.fixture
def creds():
    """
    Common credentials
    """
    yield {'user': 'unit', 'password': 'test', 'installation-password': 'temp'}


@pytest.fixture
def default_os():
    """
    Default operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'os', 'linux', 15, 0, 'SupportedOS', None)


@pytest.fixture
def default_os_template():
    """
    Default OS template
    """
    yield AutoinstallMachineModel.Template(
        'os-template',
        (Path(__file__).parent.resolve() /
         "data" / "verification_template.jinja").read_text())


@pytest.fixture
def default_os_cmdline_template():
    """
    Installer kernel command line template
    """
    yield AutoinstallMachineModel.Template('cmdline.linux.jinja',
                                           'command-line template')


@pytest.fixture
def default_os_repos():
    """
    Repository for default OS installation
    """
    yield [AutoinstallMachineModel.OsRepository(
        'os-repo', 'http://example.com/os', '/kernel', '/initrd', None,
        'os', 'Default OS repo')]


@pytest.fixture
def default_os_tuple(default_os, default_os_repos, default_os_template,
                     default_os_cmdline_template):
    """
    OS resources as a convenient tuple
    """
    yield (default_os, default_os_repos, default_os_template,
           default_os_cmdline_template, [], [])


@pytest.fixture
def redhat_cmdline_template():
    """
    Installer command-line for Red Hat Anaconda-based installer
    """
    with open(os.path.join(CMDLINE_TEMPLATES_DIR,
                           'redhat.cmdline.jinja'), "r") as f:
        yield AutoinstallMachineModel.Template('redhat.cmdline',  f.read())


@pytest.fixture
def suse_cmdline_template():
    """
    Installer command-line for Suse installer
    """
    with open(os.path.join(CMDLINE_TEMPLATES_DIR,
                           'suse.cmdline.jinja'), "r") as f:
        yield AutoinstallMachineModel.Template('suse.cmdline',  f.read())


@pytest.fixture
def debian_cmdline_template():
    """
    Installer command-line for Debian installer
    """
    with open(os.path.join(CMDLINE_TEMPLATES_DIR,
                           'debian.cmdline.jinja'), "r") as f:
        yield AutoinstallMachineModel.Template('debian.cmdline', f.read())


@pytest.fixture
def subiquity_cmdline_template():
    """
    Installer command-line for Subiquity installer
    """
    with open(os.path.join(CMDLINE_TEMPLATES_DIR,
                           'subiquity.cmdline.jinja'), "r") as f:
        yield AutoinstallMachineModel.Template('subiquity.cmdline', f.read())


@pytest.fixture
def os_rhel7():
    """
    RHEL 7 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'rhel7', 'redhat', 7, 9, 'Red Hat Enterprise Linux 7.9 (Maipo)', None)


@pytest.fixture
def os_rhel8():
    """
    RHEL 8 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'rhel8', 'redhat', 8, 3, 'Red Hat Enterprise Linux 8.3 (Ootpa)', None)


@pytest.fixture
def os_sles12():
    """
    SLES 12 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'sles12', 'suse', 12, 4, 'SUSE Linux Enterprise Server 12 SP4', None)


@pytest.fixture
def os_sles15():
    """
    SLES 15 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'sles15', 'suse', 15, 2, 'SUSE Linux Enterprise Server 15 SP2', None)


@pytest.fixture
def os_ubuntu16():
    """
    Ubuntu 16 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu16', 'debian', 1604, 5, 'Ubuntu 16.04.5 LTS', None)


@pytest.fixture
def os_ubuntu18():
    """
    Ubuntu 18 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu18', 'debian', 1804, 5, 'Ubuntu 18.04.5 LTS', None)


@pytest.fixture
def os_ubuntu20():
    """
    Ubuntu 20 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu20', 'debian', 2004, 2, 'Ubuntu 20.04.2 LTS', None)


@pytest.fixture
def os_ubuntu21():
    """
    Ubuntu 21 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu21', 'debian', 2104, 0, 'Ubuntu 21.04', None)


@pytest.fixture
def os_ubuntu22():
    """
    Ubuntu 22 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu22', 'debian', 2204, 0, 'Ubuntu 22.04', None)

@pytest.fixture
def os_ubuntu23():
    """
    Ubuntu 23 operating system
    """
    yield AutoinstallMachineModel.OperatingSystem(
        'ubuntu23', 'debian', 2304, 0, 'Ubuntu 23.04', None)

@pytest.fixture
def os_rhel7_tuple(os_rhel7, redhat_cmdline_template):
    """
    Default operating system
    """
    template_content = ''
    with open(TEMPLATES_DIR + 'rhel7-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_rhel7,
           [AutoinstallMachineModel.OsRepository(
               'rhel7-repo', 'http://example.com/os', '/kernel', '/initrd',
               None, 'rhel7', 'RHEL 7 repo')],
           AutoinstallMachineModel.Template('rhel7-default', template_content),
           redhat_cmdline_template, [], [])


@pytest.fixture
def os_rhel8_tuple(os_rhel8, redhat_cmdline_template):
    """
    Default operating system
    """
    template_content = ''
    with open(TEMPLATES_DIR + 'rhel8-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_rhel8,
           [AutoinstallMachineModel.OsRepository(
               'rhel8-repo', 'http://example.com/os', '/kernel', '/initrd',
               None, 'rhel8', 'RHEL 8 repo')],
           AutoinstallMachineModel.Template('rhel8-default', template_content),
           redhat_cmdline_template, [], [])


@pytest.fixture
def os_sles12_tuple(os_sles12, suse_cmdline_template):
    """
    Default operating system
    """
    template_content = ''
    with open(TEMPLATES_DIR + 'sles12-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_sles12,
           [AutoinstallMachineModel.OsRepository(
               'sles-repo', 'http://example.com/os', '/kernel', '/initrd',
               None, 'sles12', 'SLES 12 repo')],
           AutoinstallMachineModel.Template(
               'sles12-default', template_content),
           suse_cmdline_template, [], [])


@pytest.fixture
def os_sles15_tuple(os_sles15, suse_cmdline_template):
    """
    Default operating system
    """
    template_content = ''
    with open(TEMPLATES_DIR + 'sles15-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_sles15,
           [AutoinstallMachineModel.OsRepository(
               'sles-repo', 'http://example.com/os', '/kernel', '/initrd',
               None, 'sles15', 'SLES 15 repo')],
           AutoinstallMachineModel.Template(
               'sles15-default', template_content),
           suse_cmdline_template, [], [])


@pytest.fixture
def os_ubuntu16_tuple(os_ubuntu16, debian_cmdline_template):
    """
    Ubuntu 16 complete definition
    """
    template_content = ''
    with open(TEMPLATES_DIR + 'ubuntu16-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_ubuntu16,
           [AutoinstallMachineModel.OsRepository(
               'ubuntu-repo', 'http://example.com/os', '/kernel', '/initrd',
               None, 'ubuntu16', 'Ubuntu 16 repo')],
           AutoinstallMachineModel.Template(
               'ubuntu16-default', template_content),
           debian_cmdline_template, [], [])


@pytest.fixture
def os_ubuntu18_tuple(os_ubuntu18, debian_cmdline_template):
    """
    Ubuntu 18 complete definition
    """
    template_content = ''
    with open(TEMPLATES_DIR + 'ubuntu18-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_ubuntu18,
           [AutoinstallMachineModel.OsRepository(
               'ubuntu-repo', 'http://example.com/os', '/kernel', '/initrd',
               None, 'ubuntu18', 'Ubuntu 18 repo')],
           AutoinstallMachineModel.Template(
               'ubuntu18-default', template_content),
           debian_cmdline_template, [], [])


@pytest.fixture
def os_ubuntu20_legacy_tuple(os_ubuntu20, debian_cmdline_template):
    """
    Ubuntu 20 with legacy installer complete definition
    """
    template_content = ''
    # use template from ubuntu18 for legacy installer
    with open(TEMPLATES_DIR + 'ubuntu18-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_ubuntu20,
           [AutoinstallMachineModel.OsRepository(
               'ubuntu-repo', 'http://example.com/os', '/kernel', '/initrd',
               'http://example.com/os.iso', 'ubuntu20', 'Ubuntu 20 repo')],
           AutoinstallMachineModel.Template(
               'ubuntu18-default', template_content),
           debian_cmdline_template, [], [])


@pytest.fixture
def os_ubuntu20_subiquity_tuple(os_ubuntu20, subiquity_cmdline_template):
    """
    Ubuntu 20 with subiquity installer complete definition
    """
    template_content = ''
    # use template from ubuntu18 for legacy installer
    with open(TEMPLATES_DIR + 'ubuntu20-subiquity.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_ubuntu20,
           [AutoinstallMachineModel.OsRepository(
               'ubuntu-repo', 'http://example.com/os', '/kernel', '/initrd',
               'http://example.com/os.iso', 'ubuntu20', 'Ubuntu 20 repo')],
           AutoinstallMachineModel.Template(
               'ubuntu20-subiquity', template_content),
           debian_cmdline_template, [], [])


@pytest.fixture
def os_ubuntu21_subiquity_tuple(os_ubuntu21, subiquity_cmdline_template):
    """
    Ubuntu 21 with subiquity installer complete definition
    """
    template_content = ''
    # use template from ubuntu18 for legacy installer
    with open(TEMPLATES_DIR + 'ubuntu21-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_ubuntu21,
           [AutoinstallMachineModel.OsRepository(
               'ubuntu-repo', 'http://example.com/os', '/kernel', '/initrd',
               'http://example.com/os.iso', 'ubuntu21', 'Ubuntu 21 repo')],
           AutoinstallMachineModel.Template(
               'ubuntu21-default', template_content),
           debian_cmdline_template, [], [])



@pytest.fixture
def os_ubuntu22_subiquity_tuple(os_ubuntu22, subiquity_cmdline_template):
    """
    Ubuntu 22 with subiquity installer complete definition
    """
    template_content = ''
    # use template from ubuntu18 for legacy installer
    with open(TEMPLATES_DIR + 'ubuntu22-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_ubuntu22,
           [AutoinstallMachineModel.OsRepository(
               'ubuntu-repo', 'http://example.com/os', '/kernel', '/initrd',
               'http://example.com/os.iso', 'ubuntu22', 'Ubuntu 22 repo')],
           AutoinstallMachineModel.Template(
               'ubuntu22-default', template_content),
           debian_cmdline_template, [], [])


@pytest.fixture
def os_ubuntu23_subiquity_tuple(os_ubuntu23, subiquity_cmdline_template):
    """
    Ubuntu 23 with subiquity installer complete definition
    """
    template_content = ''
    # use template from ubuntu18 for legacy installer
    with open(TEMPLATES_DIR + 'ubuntu23-default.jinja', "r") as template_file:
        template_content = template_file.read()

    yield (os_ubuntu23,
           [AutoinstallMachineModel.OsRepository(
               'ubuntu-repo', 'http://example.com/os', '/kernel', '/initrd',
               'http://example.com/os.iso', 'ubuntu23', 'Ubuntu 23 repo')],
           AutoinstallMachineModel.Template(
               'ubuntu23-default', template_content),
           debian_cmdline_template, [], [])


@pytest.fixture
def dasd_volume():
    """
    A single-partition DASD volume
    """
    result = AutoinstallMachineModel.DasdVolume('abcd', 20_000_000)
    result.set_partitions('dasd', [{
        'mount_point': '/',
        'size': 18_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }])
    yield result


@pytest.fixture
def scsi_volume():
    """
    A single-partition SCSI volume
    """
    result = AutoinstallMachineModel.ZfcpVolume(
        'bcde0000', 20_000_000, multipath=True,
        wwid='36005076309ffd4350000000000007926')
    result.create_paths(
        ['0.0.fc00', '0.0.fc40'],
        ['5005076309049435', '5005076309009435'])
    result.set_partitions('msdos', [{
        'mount_point': '/',
        'size': 18_000,
        'filesystem': 'ext4',
        'part_type': 'primary',
        'mount_opts': None,
    }])
    yield result


@pytest.fixture
def osa_iface():
    """
    An OSA interface
    """
    result = AutoinstallMachineModel.OsaInterface(
        '0b01,0b02,0b03', False, os_device_name='enccw0b01',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.0.0.15', subnet='10.0.0.0/24', gateway='10.0.0.1',
            search_list='example.com local')])
    yield result


@pytest.fixture
def roce_iface():
    """
    A ROCE card interface
    """
    result = AutoinstallMachineModel.RoceInterface(
        '655', os_device_name='pci01',
        mac_address='10:ce:24:65:50:b0',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.2.0.23', subnet='10.2.0.0/24', gateway='10.2.0.1')])
    yield result


@pytest.fixture
def macvtap_iface():
    """
    A MACVTAP interface
    """
    result = AutoinstallMachineModel.MacvtapHostInterface(
        'enccw0b01', os_device_name='eth0',
        mac_address='0a:b0:c0:0d:45:58',
        subnets=[AutoinstallMachineModel.SubnetAffiliation(
            ip_address='10.1.0.75', subnet='10.1.0.0/24', gateway='10.1.0.1')])
    yield result


@pytest.fixture
def hmc_hypervisor():
    """
    An HMC hypervisor
    """
    hypervisor = AutoinstallMachineModel.HmcHypervisor(
        'hmc', 'hmc.local',
        {'user': '', 'password': ''},
        {
            'partition-name': 'LP10',
            'boot-method': 'storage',
            'boot-device': 'b007',
        })
    return hypervisor


@pytest.fixture
def zvm_hypervisor():
    """
    A ZVM hypervisor
    """
    hypervisor = AutoinstallMachineModel.ZvmHypervisor(
        'vmhost', 'vmhost.local',
        {'user': 'guest', 'password': 'guest'},
        {'logon-by': None, 'no-cms': True, })
    return hypervisor


@pytest.fixture
def kvm_hypervisor():
    """
    A KVM hypervisor
    """
    hypervisor = AutoinstallMachineModel.KvmHypervisor(
        'lp18kvm', 'lp18kvm.local',
        {'user': 'kvmuser', 'password': 'test'})
    return hypervisor


@pytest.fixture
def lpar_dasd_system(osa_iface, dasd_volume, hmc_hypervisor):
    """
    An LPAR system on DASD with OSA interface
    """
    result = AutoinstallMachineModel.SystemProfile(
        'lp10', 'default',
        hypervisor=hmc_hypervisor,
        hostname='lp10.local',
        cpus=2, memory=8192,
        volumes=[dasd_volume],
        interfaces=[(osa_iface, True)]
    )
    yield result


@pytest.fixture
def lpar_scsi_system(osa_iface, scsi_volume, hmc_hypervisor):
    """
    An LPAR system on SCSI with OSA interface
    """
    result = AutoinstallMachineModel.SystemProfile(
        'lp10', 'default',
        hypervisor=hmc_hypervisor,
        hostname='lp10.local',
        cpus=2, memory=8192,
        volumes=[scsi_volume],
        interfaces=[(osa_iface, True)]
    )
    yield result


@pytest.fixture
def vm_dasd_system(osa_iface, dasd_volume, zvm_hypervisor):
    """
    A VM system on DASD with OSA interface
    """
    result = AutoinstallMachineModel.SystemProfile(
        'vm25', 'default',
        hypervisor=zvm_hypervisor,
        hostname='vm25.local',
        cpus=4, memory=8192,
        volumes=[dasd_volume],
        interfaces=[(osa_iface, True)]
    )
    yield result


@pytest.fixture
def vm_scsi_system(osa_iface, scsi_volume, zvm_hypervisor):
    """
    A VM system on SCSI with OSA interface
    """
    result = AutoinstallMachineModel.SystemProfile(
        'vm25', 'default',
        hypervisor=zvm_hypervisor,
        hostname='vm25.local',
        cpus=4, memory=8192,
        volumes=[scsi_volume],
        interfaces=[(osa_iface, True)]
    )
    yield result


@pytest.fixture
def kvm_scsi_system(macvtap_iface, scsi_volume, kvm_hypervisor):
    """
    A VM system on SCSI with OSA interface
    """
    result = AutoinstallMachineModel.SystemProfile(
        'kvm54', 'default',
        hypervisor=kvm_hypervisor,
        hostname='kvm54.local',
        cpus=1, memory=4096,
        volumes=[scsi_volume],
        interfaces=[(macvtap_iface, True)]
    )
    yield result
