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
Unit test for the Postinstalation verification module.
"""

from tests.unit.state_machines.autoinstall import utils
from unittest import TestCase
from unittest.mock import patch

import tessia_engine.state_machines.autoinstall.post_install_verif as verif

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestPostInstallVerif(TestCase):
    """
    Class for unit testing the post_install_verif module.
    """
    @classmethod
    def setUpClass(cls):
        """
        Called once for the setup of DbUnit.
        """
        utils.setup_dbunit()
    # setUpClass()

    @classmethod
    def test_verificatio(cls):
        """
        Test the case that the installation is correct.
        """
        profile = utils.get_profile("kvm054/kvm_kvm054_install")
        os_entry = utils.get_os("rhel7.2")

        with patch.object(verif, 'get_actual_params') as perm_mock:
            perm_mock.return_value = {
                "ansible_cmdline": {
                    "BOOT_IMAGE": "0",
                    "LANG": "en_US.UTF-8",
                    "cio_ignore": "all,!condev",
                    "crashkernel": "0M-2G:128M,2G-6G:256M,6G-8G:512M,8G-:768M",
                    "printk.time": "1",
                    "rd_DASD": "0.0.e272",
                    "root": "/dev/disk/by-path/ccw-0.0.e272-part1",
                    "scsi_mod.scsi_logging_level": "4605"},
                "ansible_default_ipv4": {
                    "address": "192.168.160.54",
                    "alias": "enccw0.0.f5f0",
                    "broadcast": "192.168.163.255",
                    "gateway": "192.168.160.1",
                    "interface": "enccw0.0.f5f0",
                    "macaddress": "02:a2:2c:00:00:30",
                    "mtu": 1500,
                    "netmask": "255.255.252.0",
                    "network": "192.168.160.0", "type": "MACVTAP"},
                "ansible_default_ipv6": {},
                "ansible_distribution": "RedHat",
                "ansible_distribution_major_version": "7",
                "ansible_distribution_release": "Maipo",
                "ansible_distribution_version": "7.2",
                "ansible_dns": {
                    "nameservers": ["192.168.200.241"],
                    "search": ["domain.com"]},
                "ansible_domain": "domain.com",
                "ansible_eth0": {
                    "active": "true",
                    "device": "enccw0.0.f5f0",
                    "ipv4": {
                        "address": "192.168.160.54",
                        "broadcast": "192.168.163.255",
                        "netmask": "255.255.252.0",
                        "network": "192.168.160.0"},
                    "ipv6": [{
                        "address": "fe80::a2:2cff:fe00:30",
                        "prefix": "64",
                        "scope": "link"}],
                    "macaddress": "02:a2:2c:00:00:30",
                    "module": "qeth",
                    "mtu": 1500,
                    "type": "MACVTAP"},
                "ansible_interfaces": ["lo", "eth0"],
                "ansible_kernel": "3.10.0-514.el7.s390x",
                "ansible_lo": {
                    "active": "true",
                    "device": "lo",
                    "ipv4": {
                        "address": "127.0.0.1",
                        "broadcast": "host",
                        "netmask": "255.0.0.0",
                        "network": "127.0.0.0"},
                    "ipv6": [{
                        "address": "::1",
                        "prefix": "128",
                        "scope": "host"}],
                    "mtu": 65536,
                    "promisc": "false",
                    "type": "loopback"},
                "ansible_machine": "s390x",
                "ansible_memfree_mb": 329,
                "ansible_memory_mb": {
                    "nocache": {
                        "free": 675,
                        "used": 188},
                    "real": {
                        "free": 329,
                        "total": 863,
                        "used": 534},
                    "swap": {
                        "cached": 0,
                        "free": 21129,
                        "total": 21129,
                        "used": 0}},
                "ansible_memtotal_mb": 863,
                "ansible_mounts": [
                    {
                        "fstype": "ext4",
                        "mount": "/",
                        "options": None,
                        "size_total": 4096000
                    },
                    {
                        "fstype": "swap",
                        "mount": None,
                        "options": None,
                        "size_total": 97280
                    },
                    {
                        "fstype": "ext4",
                        "mount": "/mnt/data1",
                        "options": None,
                        "size_total": 4193280
                    },
                    {
                        "fstype": "ext4",
                        "mount": "/mnt/data2",
                        "options": None,
                        "size_total": 4193280
                    },
                    {
                        "fstype": "ext4",
                        "mount": "/mnt/data3",
                        "options": None,
                        "size_total": 4193280
                    },
                    {
                        "fstype": "ext4",
                        "mount": "/mnt/data4",
                        "options": None,
                        "size_total": 4193280
                    },
                ],
                "ansible_os_family": "RedHat",
                "ansible_pkg_mgr": "yum",
                "ansible_processor": ["IBM/S390"],
                "ansible_processor_cores": 2
            }

            with patch.object(verif, 'get_actual_fcp') as fcp_mock:
                fcp_mock.return_value = [[
                    '0.0.1800',
                    '0x100207630503c1ae',
                    '0x4085400200000000']]

                verif.config_verificate(os_entry, profile)
    # test_verification()
# TestPostInstallVerif
