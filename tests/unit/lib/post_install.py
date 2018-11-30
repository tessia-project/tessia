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
Unit test for the post_install verification module.
"""

from contextlib import contextmanager
from copy import deepcopy
from tessia.server.db.models import System, SystemProfile, OperatingSystem
from tessia.server.lib import post_install
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest.mock import patch, Mock

import json
import os
import subprocess

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestPostInstallChecker(TestCase):
    """
    Unit testing for the PostInstallChecker class.
    """
    @classmethod
    def setUpClass(cls):
        """
        Called once to create the db content for this test.
        """
        DbUnit.create_db()
        sample_file = '{}/files/data.json'.format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(sample_file, 'r') as sample_fd:
            data = sample_fd.read()
        DbUnit.create_entry(json.loads(data))
        cls.db = DbUnit
    # setUpClass()

    def setUp(self):
        """
        Called before each test to set up the necessary mocks.
        """
        self._mismatch_msg = (
            "Configuration mismatch in {}: expected '{}', actual is '{}'")

        # mock for calling ansible commands
        patcher = patch.object(
            post_install.subprocess, 'check_output', autospec=True)
        self._mock_check_output = patcher.start()
        self.addCleanup(patcher.stop)

        # patch logger
        patcher = patch.object(post_install, 'logging')
        mock_logging = patcher.start()
        mock_logging.getLogger.return_value = Mock(
            spec=['warning', 'error', 'debug', 'info'])
        self._mock_logger = mock_logging.getLogger.return_value
    # setUp()

    @staticmethod
    def _get_profile(system, profile):
        """
        Helper function to query the db for a given profile
        """
        profile_entry = SystemProfile.query.join(
            'system_rel'
        ).filter(
            SystemProfile.name == profile
        ).filter(
            System.name == system
        ).one()
        return profile_entry
    # _get_profile()

    @contextmanager
    def _mock_db_obj(self, target_obj, target_field, temp_value):
        """
        Act as a context manager to temporarily change a value in a db row and
        restore it on exit.

        Args:
            target_obj (SAobject): sqlsa model object
            target_field (str): name of field in object
            temp_value (any): value to be temporarily assigned

        Yields:
            None: nothing is returned
        """
        orig_value = getattr(target_obj, target_field)
        setattr(target_obj, target_field, temp_value)
        self.db.session.add(target_obj)
        self.db.session.commit()
        yield
        setattr(target_obj, target_field, orig_value)
        self.db.session.add(target_obj)
        self.db.session.commit()
    # _mock_db_obj()

    def _set_mocks_lpar_fcp(self, prof_obj):
        """
        Prepare mocks to return content of a lpar with fcp disks installation.

        Args:
            prof_obj (SystemProfile): profile entry
        """
        facts_file = '{}/files/facts_fcp.output'.format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(facts_file, 'r') as facts_fd:
            facts = facts_fd.read()

        parted_1 = (
            """cpc3lp52.domain.com | SUCCESS => {
    "changed": false,
    "disk": {
        "dev": "/dev/dm-0",
        "logical_block": 512,
        "model": "Linux device-mapper (multipath)",
        "physical_block": 512,
        "size": 10737418240.0,
        "table": "msdos",
        "unit": "b"
    },
    "partitions": [
        {
            "begin": 1048576.0,
            "end": 9437183999.0,
            "flags": [],
            "fstype": "ext4",
            "num": 1,
            "size": 9436135424.0,
            "unit": "b"
        },
        {
            "begin": 9438231552.0,
            "end": 10737418239.0,
            "flags": [],
            "fstype": "",
            "num": 2,
            "size": 1299186688.0,
            "unit": "b"
        },
        {
            "begin": 9438232576.0,
            "end": 10737418239.0,
            "flags": [],
            "fstype": "linux-swap(v1)",
            "num": 5,
            "size": 1299185664.0,
            "unit": "b"
        }
    ],
    "script": "unit 'B' print"
}
"""
        )

        # pylint: disable=trailing-whitespace
        lsblk_1 = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
 
ext4 /
 
swap [SWAP]
"""
        )
        # pylint: enable=trailing-whitespace

        parted_2 = (
            """cpc3lp52.domain.com | SUCCESS => {
    "changed": false,
    "disk": {
        "dev": "/dev/dm-4",
        "logical_block": 512,
        "model": "Linux device-mapper (multipath)",
        "physical_block": 512,
        "size": 10737418240.0,
        "table": "msdos",
        "unit": "b"
    },
    "partitions": [
        {
            "begin": 1048576.0,
            "end": 5243928575.0,
            "flags": [],
            "fstype": "btrfs",
            "num": 1,
            "size": 5242880000.0,
            "unit": "b"
        }
    ],
    "script": "unit 'B' print"
}
"""
        )

        # pylint: disable=trailing-whitespace
        lsblk_2 = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
 
btrfs /home
"""
        )
        # pylint: enable=trailing-whitespace

        lszfcp = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
0.0.1800/0x100207630513c1ae/0x1022400000000000 0:0:21:1073758242
0.0.1800/0x100207630513c1ae/0x1022400200000000 0:0:21:1073889314
0.0.1800/0x100207630508c1ae/0x1022400000000000 0:0:22:1073758242
0.0.1800/0x100207630508c1ae/0x1022400200000000 0:0:22:1073889314
0.0.1800/0x100207630503c1ae/0x1022400000000000 0:0:23:1073758242
0.0.1800/0x100207630503c1ae/0x1022400200000000 0:0:23:1073889314
0.0.1800/0x100207630510c1ae/0x1022400000000000 0:0:7:1073758242
0.0.1800/0x100207630510c1ae/0x1022400200000000 0:0:7:1073889314
0.0.1840/0x100207630508c1ae/0x1022400000000000 1:0:10:1073758242
0.0.1840/0x100207630508c1ae/0x1022400200000000 1:0:10:1073889314
0.0.1840/0x100207630503c1ae/0x1022400000000000 1:0:11:1073758242
0.0.1840/0x100207630503c1ae/0x1022400200000000 1:0:11:1073889314
0.0.1840/0x100207630510c1ae/0x1022400000000000 1:0:12:1073758242
0.0.1840/0x100207630510c1ae/0x1022400200000000 1:0:12:1073889314
0.0.1840/0x100207630513c1ae/0x1022400000000000 1:0:9:1073758242
0.0.1840/0x100207630513c1ae/0x1022400200000000 1:0:9:1073889314
"""
        )

        os_release = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
NAME=xxxx
VERSION=xxxx
PRETTY_NAME="{}"
ID=xxxxx
""".format(prof_obj.operating_system_rel.pretty_name)
        )

        lscpu_output = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
Architecture:          s390x
CPU op-mode(s):        32-bit, 64-bit
Byte Order:            Big Endian
CPU(s):                24
On-line CPU(s) list:   0-19
Off-line CPU(s) list:  20-23
Thread(s) per core:    2
Core(s) per socket:    10
Socket(s) per book:    3
NUMA node0 CPU(s):     0-255
"""
        )

        # new format (lsmem's C port)
        lsmem_output = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
RANGE                                        SIZE  STATE REMOVABLE BLOCK
0x0000000000000000-0x000000006fffffff  2147483648 online       yes   0-7
0x0000000070000000-0x000000007fffffff   268435456 online        no     8
0x0000000080000000-0x00000000bfffffff  1073741824 online       yes  9-12
0x00000000c0000000-0x00000000ffffffff  1073741824 online       yes 13-16

Memory block size:        268435456
Total online memory:     4294967296
Total offline memory:            0
"""
        )

        # systemd dns config
        realp_output = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
/run/systemd/resolve/stub-resolv.conf
""")
        resolv_output = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
# This file is managed by man:systemd-resolved(8). Do not edit.
#

nameserver 192.168.200.241
search domain.com
""")
        self._mock_check_output.side_effect = [
            facts, parted_1, lsblk_1, parted_2, lsblk_2, lszfcp, os_release,
            lscpu_output, lsmem_output, realp_output, resolv_output]
    # _set_mocks_lpar_fcp()

    def _set_mocks_lpar_dasd(self, prof_obj):
        """
        Prepare mocks to return content of a lpar with dasd disks installation.

        Args:
            prof_obj (SystemProfile): profile entry
        """
        facts_file = '{}/files/facts_dasd.output'.format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(facts_file, 'r') as facts_fd:
            facts = facts_fd.read()

        parted_1 = (
            """cpc3lp52.domain.com | SUCCESS => {
    "changed": false,
    "disk": {
        "dev": "/dev/dasda",
        "logical_block": 512,
        "model": "IBM S390 DASD drive",
        "physical_block": 4096,
        "size": 7385333760.0,
        "table": "dasd",
        "unit": "b"
    },
    "partitions": [
        {
            "begin": 98304.0,
            "end": 7340163071.0,
            "flags": [],
            "fstype": "ext4",
            "num": 1,
            "size": 7340064768.0,
            "unit": "b"
        }
    ],
    "script": "unit 'B' print"
}
"""
        )

        # pylint: disable=trailing-whitespace
        lsblk_1 = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
 
ext4 /
"""
        ) # pylint: enable=trailing-whitespace

        parted_2 = (
            """cpc3lp52.domain.com | SUCCESS => {
    "changed": false,
    "disk": {
        "dev": "/dev/dasdb",
        "logical_block": 512,
        "model": "IBM S390 DASD drive",
        "physical_block": 4096,
        "size": 7385333760.0,
        "table": "dasd",
        "unit": "b"
    },
    "partitions": [
        {
            "begin": 98304.0,
            "end": 7340163071.0,
            "flags": [],
            "fstype": "linux-swap(v1)",
            "num": 1,
            "size": 7340064768.0,
            "unit": "b"
        }
    ],
    "script": "unit 'B' print"
}
"""
        )

        # pylint: disable=trailing-whitespace
        lsblk_2 = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
 
swap [SWAP]
"""
        ) # pylint: enable=trailing-whitespace

        lszfcp = subprocess.CalledProcessError(returncode=1, cmd='lszfcp -D')
        lszfcp_output = (
            """cpc3lp52.domain.com | FAILED | rc=1 >>
Error: No fcp devices found.
"""
        )
        lszfcp.output = lszfcp_output

        os_release = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
NAME=xxxx
VERSION=xxxx
PRETTY_NAME="{}"
ID=xxxxx
""".format(prof_obj.operating_system_rel.pretty_name)
        )

        lscpu_output = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
Architecture:          s390x
CPU op-mode(s):        32-bit, 64-bit
Byte Order:            Big Endian
CPU(s):                10
On-line CPU(s) list:   0-9
Thread(s) per core:    1
Core(s) per socket:    10
Socket(s) per book:    3
NUMA node0 CPU(s):     0-255
"""
        )

        # old format (lsmem's perl script)
        lsmem_output = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
Address Range                          Size (MB)  State    Removable  Device
===============================================================================
0x0000000000000000-0x00000000fffffffe       4096  online   no         0-4095

Memory device size  : 1 MB
Memory block size   : 256 MB
Total online memory : 4096 MB
Total offline memory: 0 MB
"""
        )

        # systemd dns config
        realp_output = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
/etc/resolv.conf
""")

        self._mock_check_output.side_effect = [
            facts, parted_1, lsblk_1, parted_2, lsblk_2, lszfcp, os_release,
            lscpu_output, RuntimeError(), lsmem_output, realp_output]
    # _set_mocks_lpar_dasd()

    def test_facts_fail(self):
        """
        Simulate possible errors when collecting facts
        """
        profile_entry = self._get_profile('cpc3lp52', 'dasd1')
        checker = post_install.PostInstallChecker(profile_entry)

        exc = subprocess.CalledProcessError(returncode=1, cmd='')
        self._mock_check_output.side_effect = exc

        # simulate output of connection failed (i.e. wrong password)
        exc.output = (
            """cpc3lp52.domain.com | UNREACHABLE! => {
    "changed": false,
    "msg": "Authentication failure.",
    "unreachable": true
}
"""
        )
        with self.assertRaisesRegex(
            ConnectionError, 'Connection failed, output: '):
            checker.verify()

        # simulate an unknown output (should not happen in reality)
        exc.output = (
            """cpc3lp52.domain.com, ERROR! => {
}
"""
        )
        with self.assertRaisesRegex(
            SystemError, 'Unknown error, output: '):
            checker.verify()

        # simulate a module error output
        exc.output = (
            """cpc3lp52.domain.com | FAILED | rc=2 >>
[Errno 2] No such file or directory
"""
        )
        with self.assertRaisesRegex(
            RuntimeError, 'Command failed, output: '):
            checker.verify()

        # simulate a success output in an unknown format (should not happen in
        # reality)
        self._mock_check_output.side_effect = [
            """cpc3lp52.domain.com | SUCCESS >>>
some_output
"""
        ]
        with self.assertRaisesRegex(
            SystemError, 'Could not parse command output: '):
            checker.verify()

        # prepare valid output and turn them invalid
        self._set_mocks_lpar_dasd(profile_entry)
        orig_outputs = list(self._mock_check_output.side_effect)

        # simulate invalid facts content
        test_outputs = orig_outputs[:]
        test_outputs[0] = test_outputs[0].replace(
            'ansible_facts', 'ansible_wrong_facts')
        self._mock_check_output.side_effect = test_outputs
        with self.assertRaisesRegex(
            SystemError, 'Could not parse output from ansible facts: '):
            checker.verify()

        # simulate invalid lsmem output
        test_outputs = orig_outputs[:]
        test_outputs[9] = test_outputs[9].replace(
            'Total online memory : 4096 MB',
            'Total online memory:       unknown')
        self._mock_check_output.side_effect = test_outputs
        with self.assertRaisesRegex(
            RuntimeError, 'Failed to parse lsmem output'):
            checker.verify()

        # simulate invalid parted content
        test_outputs = orig_outputs[:]
        test_outputs[1] += '}'
        self._mock_check_output.side_effect = test_outputs
        with self.assertRaisesRegex(
            SystemError, 'Could not parse parted output of disk'):
            checker.verify()

    # test_facts_fail()

    def test_lpar_dasd(self):
        """
        Test verification of an LPAR with DASD based installation and no smt.
        """
        profile_entry = self._get_profile('cpc3lp52', 'dasd1')
        self._set_mocks_lpar_dasd(profile_entry)

        checker = post_install.PostInstallChecker(profile_entry)
        checker.verify()
    # test_lpar_dasd()

    def test_lpar_dasd_no_mac(self):
        """
        Test verification without mac address defined.
        """
        profile_entry = self._get_profile('cpc3lp52', 'dasd1')
        self._set_mocks_lpar_dasd(profile_entry)
        profile_entry.system_ifaces_rel[0].mac_address = None

        checker = post_install.PostInstallChecker(profile_entry)
        checker.verify()
    # test_lpar_dasd_no_mac()

    def test_lpar_dasd_no_lscpu(self):
        """
        Test verification of a LPAR with DASD based installation where 'lscpu'
        is not available on the system.
        """
        profile_entry = self._get_profile('cpc3lp52', 'dasd1')
        self._set_mocks_lpar_dasd(profile_entry)
        # set mock to simulate lscpu not found
        check_outputs = list(self._mock_check_output.side_effect)
        check_outputs[7] = subprocess.CalledProcessError(
            returncode=2, cmd='lscpu')
        check_outputs[7].output = (
            """cpc3lp52.domain.com | FAILED | rc=3 >>
[Errno 2] No such file or directory
"""
        )
        self._mock_check_output.side_effect = check_outputs

        checker = post_install.PostInstallChecker(profile_entry)
        checker.verify()
    # test_lpar_dasd()

    def test_lpar_fcp(self):
        """
        Test verification of a LPAR with FCP based installation with smt
        enabled.
        """
        profile_entry = self._get_profile('cpc3lp52', 'fcp1')
        self._set_mocks_lpar_fcp(profile_entry)

        checker = post_install.PostInstallChecker(profile_entry)
        checker.verify()
    # test_lpar_fcp()

    def test_misconfiguration_cpu(self):
        """
        Exercise misconfiguration of cpu values.
        """
        fcp_prof_entry = self._get_profile('cpc3lp52', 'fcp1')

        # cpu mismatch
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        with self._mock_db_obj(fcp_prof_entry, 'cpu', 99):
            error_msg = self._mismatch_msg.format('cpu quantity', 198, 20)
            checker = post_install.PostInstallChecker(fcp_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['cpu'])

        # permissive - only logging occurs
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        self._mock_logger.reset_mock()
        with self._mock_db_obj(fcp_prof_entry, 'cpu', 99):
            checker = post_install.PostInstallChecker(
                fcp_prof_entry, permissive=True)
            checker.verify(areas=['cpu'])
            self._mock_logger.warning.assert_called_with(error_msg)
    # test_misconfiguration_cpu()

    def test_misconfiguration_memory(self):
        """
        Exercise misconfiguration of memory values.
        """
        fcp_prof_entry = self._get_profile('cpc3lp52', 'fcp1')
        # min memory mismatch
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        with self._mock_db_obj(fcp_prof_entry, 'memory', 6000):
            error_msg = self._mismatch_msg.format(
                'minimum MiB memory', 5872, 4096)
            checker = post_install.PostInstallChecker(fcp_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['memory'])

            # permissive - only logging occurs
            self._set_mocks_lpar_fcp(fcp_prof_entry)
            self._mock_logger.reset_mock()
            checker = post_install.PostInstallChecker(
                fcp_prof_entry, permissive=True)
            checker.verify(areas=['memory'])
            self._mock_logger.warning.assert_called_with(error_msg)

        # max memory mismatch
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        with self._mock_db_obj(fcp_prof_entry, 'memory', 3000):
            # actual is calculated by using ansible_total_mb + crash_size set
            # by mock
            error_msg = self._mismatch_msg.format(
                'maximum MiB memory', 3128, 4096)
            checker = post_install.PostInstallChecker(fcp_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['memory'])

            # permissive - only logging occurs
            self._set_mocks_lpar_fcp(fcp_prof_entry)
            self._mock_logger.reset_mock()
            checker = post_install.PostInstallChecker(
                fcp_prof_entry, permissive=True)
            checker.verify(areas=['memory'])
            self._mock_logger.warning.assert_called_with(error_msg)

        # simulate lsmem not available
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        # mock the failure to call lsmem
        exc = subprocess.CalledProcessError(returncode=1, cmd='')
        exc.output = (
            """cpc3lp52.domain.com | FAILED | rc=2 >>
[Errno 2] No such file or directory
"""
        )
        # add the failure to the list of outputs
        test_outputs = self._mock_check_output.side_effect[:]
        test_outputs[8] = RuntimeError()
        test_outputs.insert(9, exc)
        self._mock_check_output.side_effect = test_outputs
        # expected error message
        error_msg = self._mismatch_msg.format(
            'minimum MiB memory', 3968, -1)
        # test and validate
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify()
        # now test permissive - only logging occurs
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        self._mock_check_output.side_effect = test_outputs
        self._mock_logger.reset_mock()
        checker = post_install.PostInstallChecker(
            fcp_prof_entry, permissive=True)
        checker.verify(areas=['memory'])
        self._mock_logger.warning.assert_called_with(error_msg)

    # test_misconfiguration_memory()

    def test_misconfiguration_os(self):
        """
        Exercise misconfiguration of the operating system.
        """
        fcp_prof_entry = self._get_profile('cpc3lp52', 'fcp1')

        # os mismatch (different pretty name)
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        check_outputs = list(self._mock_check_output.side_effect)
        wrong_os = 'SUSE Linux 12.2'
        check_outputs[6] = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
NAME=xxxx
VERSION=xxxx
PRETTY_NAME="{}"
ID=xxxxx
""".format(wrong_os)
        )

        self._mock_check_output.side_effect = check_outputs
        error_msg = self._mismatch_msg.format(
            'OS name', fcp_prof_entry.operating_system_rel.pretty_name,
            wrong_os)
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['os'])

        # permissive - only logging occurs
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        self._mock_check_output.side_effect = check_outputs
        self._mock_logger.reset_mock()
        checker = post_install.PostInstallChecker(
            fcp_prof_entry, permissive=True)
        checker.verify(areas=['os'])
        self._mock_logger.warning.assert_called_with(error_msg)
    # test_misconfiguration_os()

    def test_misconfiguration_gw_missing(self):
        """
        Exercise a misconfiguration of the network subsystem where the expected
        gateway is missing
        """
        fcp_prof_entry = self._get_profile('cpc3lp52', 'fcp1')

        # network - gateway mismatch
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        check_outputs = list(self._mock_check_output.side_effect)
        # simulate missing gateway
        check_outputs[0] = check_outputs[0].replace(
            'gateway', 'hide_gateway')
        self._mock_check_output.side_effect = check_outputs
        error_msg = self._mismatch_msg.format(
            'gateway', '192.168.160.1', '<not found>')
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['network'])

        # permissive - only logging occurs
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        self._mock_check_output.side_effect = check_outputs
        self._mock_logger.reset_mock()
        checker = post_install.PostInstallChecker(
            fcp_prof_entry, permissive=True)
        checker.verify(areas=['network'])
        self._mock_logger.warning.assert_called_with(error_msg)
    # test_misconfiguration_gw_missing()

    def test_misconfiguration_gw_invalid(self):
        """
        Exercise a misconfiguration of the network subsystem where the expected
        gateway does not match the actual entry
        """
        fcp_prof_entry = self._get_profile('cpc3lp52', 'fcp1')

        # simulate invalid gateway
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        check_outputs = list(self._mock_check_output.side_effect)
        check_outputs[0] = check_outputs[0].replace(
            '"gateway": "192.168.160.1"',
            '"gateway": "192.152.160.1"')
        self._mock_check_output.side_effect = check_outputs
        error_msg = self._mismatch_msg.format(
            'gateway', '192.168.160.1', '192.152.160.1')
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['network'])

        # permissive - only logging occurs
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        self._mock_check_output.side_effect = check_outputs
        self._mock_logger.reset_mock()
        checker = post_install.PostInstallChecker(
            fcp_prof_entry, permissive=True)
        checker.verify(areas=['network'])
        self._mock_logger.warning.assert_called_with(error_msg)
    # test_misconfiguration_gw_invalid()

    def test_misconfiguration_dns(self):
        """
        Exercise a misconfiguration of the network subsystem where the expected
        dns server is not found
        """
        fcp_prof_entry = self._get_profile('cpc3lp52', 'fcp1')

        # network - dns mismatch
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        subnet_entry = (fcp_prof_entry.system_ifaces_rel[0]
                        .ip_address_rel.subnet_rel)
        with self._mock_db_obj(subnet_entry, 'dns_2', '8.8.8.8'):
            error_msg = self._mismatch_msg.format(
                'iface enccw0.0.f500 nameservers', '8.8.8.8', '<not found>')
            checker = post_install.PostInstallChecker(fcp_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['network'])

            # permissive - only logging occurs
            self._set_mocks_lpar_fcp(fcp_prof_entry)
            checker = post_install.PostInstallChecker(
                fcp_prof_entry, permissive=True)
            checker.verify(areas=['network'])
            self._mock_logger.warning.assert_called_with(error_msg)

        # no resolv.conf available
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        test_outputs = list(self._mock_check_output.side_effect)
        test_outputs[9] = RuntimeError(
            'Command failed, output: cpc3lp52.domain.com | FAILED!')
        self._mock_check_output.side_effect = test_outputs
        error_msg = self._mismatch_msg.format(
            'iface enccw0.0.f500 nameservers', '192.168.200.241',
            '<not found>')
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['network'])

        # permissive - only logging occurs
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        test_outputs = list(self._mock_check_output.side_effect)
        test_outputs[9] = RuntimeError(
            'Command failed, output: cpc3lp52.domain.com | FAILED!')
        self._mock_check_output.side_effect = test_outputs
        checker = post_install.PostInstallChecker(
            fcp_prof_entry, permissive=True)
        checker.verify(areas=['network'])
        self._mock_logger.warning.assert_called_with(error_msg)

        # failed to read resolv.conf froms systemd
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        test_outputs = list(self._mock_check_output.side_effect)
        test_outputs[10] = RuntimeError(
            'Command failed, output: cpc3lp52.domain.com | FAILED!')
        self._mock_check_output.side_effect = test_outputs
        error_msg = self._mismatch_msg.format(
            'iface enccw0.0.f500 nameservers', '192.168.200.241',
            '<not found>')
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['network'])

        # permissive - only logging occurs
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        test_outputs = list(self._mock_check_output.side_effect)
        test_outputs[10] = RuntimeError(
            'Command failed, output: cpc3lp52.domain.com | FAILED!')
        self._mock_check_output.side_effect = test_outputs
        checker = post_install.PostInstallChecker(
            fcp_prof_entry, permissive=True)
        checker.verify(areas=['network'])
        self._mock_logger.warning.assert_called_with(error_msg)

    # test_misconfiguration_dns()

    def test_misconfiguration_storage(self):
        """
        Exercise misconfiguration of the storage subsystem.
        """
        dasd_prof_entry = self._get_profile('cpc3lp52', 'dasd1')
        fcp_prof_entry = self._get_profile('cpc3lp52', 'fcp1')

        # storage - no fcp paths
        # use facts from a dasd-only config to simulate no fcp devices found
        self._set_mocks_lpar_dasd(dasd_prof_entry)
        error_msg = self._mismatch_msg.format(
            'fcp paths', 'fcp paths for LUN 1022400000000000', '<not found>')
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['storage'])

        # permissive - only logging occurs
        self._set_mocks_lpar_dasd(dasd_prof_entry)
        self._mock_logger.reset_mock()
        checker = post_install.PostInstallChecker(
            fcp_prof_entry, permissive=True)
        checker.verify(areas=['storage'])
        error_msg = self._mismatch_msg.format(
            'fcp paths', 'fcp paths for LUN 1022400200000000', '<not found>')
        self._mock_logger.warning.assert_called_with(error_msg)

        # simulate disk not available
        self._set_mocks_lpar_fcp(fcp_prof_entry)
        test_outputs = list(self._mock_check_output.side_effect)
        test_outputs[1] = RuntimeError(
            'Command failed, output: cpc3lp52.domain.com | FAILED!')
        # lsblk won't get called for this disk so remove the mock entry
        test_outputs.pop(2)
        self._mock_check_output.side_effect = test_outputs
        error_msg = self._mismatch_msg.format(
            'volume 1022400000000000',
            'disk /dev/disk/by-id/dm-uuid-mpath-'
            '11002076305aac1a0000000000002200 present',
            '<not found>')
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        with self.assertRaisesRegex(post_install.Misconfiguration, error_msg):
            checker.verify(areas=['storage'])

        # permissive - only logging occurs
        self._set_mocks_lpar_dasd(dasd_prof_entry)
        self._mock_check_output.side_effect = test_outputs
        self._mock_logger.reset_mock()
        checker = post_install.PostInstallChecker(
            fcp_prof_entry, permissive=True)
        checker.verify(areas=['storage'])
        self._mock_logger.warning.assert_any_call(error_msg)

        # storage - disk min size mismatch
        self._set_mocks_lpar_dasd(dasd_prof_entry)
        vol_entry = dasd_prof_entry.storage_volumes_rel[0]
        with self._mock_db_obj(vol_entry, 'size', 15000):
            dasd_devpath = '/dev/disk/by-path/ccw-0.0.3956'
            error_msg = self._mismatch_msg.format(
                'min MiB size disk {}'.format(dasd_devpath), '14800', '7043')
            checker = post_install.PostInstallChecker(dasd_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['storage'])

            # permissive - only logging occurs
            self._set_mocks_lpar_dasd(dasd_prof_entry)
            self._mock_logger.reset_mock()
            checker = post_install.PostInstallChecker(
                dasd_prof_entry, permissive=True)
            checker.verify(areas=['storage'])
            self._mock_logger.warning.assert_called_with(error_msg)

        # storage - part min size mismatch
        self._set_mocks_lpar_dasd(dasd_prof_entry)
        vol_entry = dasd_prof_entry.storage_volumes_rel[0]
        new_ptable = deepcopy(vol_entry.part_table)
        new_ptable['table'][0]['size'] = 50000
        with self._mock_db_obj(vol_entry, 'part_table', new_ptable):
            dasd_devpath = '/dev/disk/by-path/ccw-0.0.3956'
            error_msg = self._mismatch_msg.format(
                'min MiB size partnum 1 disk {}'.format(dasd_devpath),
                '49900', '7000')
            checker = post_install.PostInstallChecker(dasd_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['storage'])

            # permissive - only logging occurs
            self._set_mocks_lpar_dasd(dasd_prof_entry)
            self._mock_logger.reset_mock()
            checker = post_install.PostInstallChecker(
                dasd_prof_entry, permissive=True)
            checker.verify(areas=['storage'])
            self._mock_logger.warning.assert_called_with(error_msg)
    # test_misconfiguration_storage()

    def test_misconfiguration_kernel(self):
        """
        Exercise misconfiguration of the kernel running.
        """
        dasd_prof_entry = self._get_profile('cpc3lp52', 'dasd1')
        # kernel mismatch
        self._set_mocks_lpar_dasd(dasd_prof_entry)
        params_content = {
            'kernel_version': '3.11.0-327.el7.s390x'
        }
        with self._mock_db_obj(dasd_prof_entry, 'parameters', params_content):
            error_msg = self._mismatch_msg.format(
                'kernel version', '3.11.0-327.el7.s390x',
                '3.10.0-327.el7.s390x')
            checker = post_install.PostInstallChecker(dasd_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['kernel'])

            # permissive - only logging occurs
            self._set_mocks_lpar_dasd(dasd_prof_entry)
            self._mock_logger.reset_mock()
            checker = post_install.PostInstallChecker(
                dasd_prof_entry, permissive=True)
            checker.verify(areas=['kernel'])
            self._mock_logger.warning.assert_called_with(error_msg)
    # test_misconfiguration_kernel()

    def test_missing_profile_params(self):
        """
        Force error when profile has missing information
        """
        profile_entry = self._get_profile('cpc3lp52', 'fcp1')
        self._set_mocks_lpar_fcp(profile_entry)

        # simulate credentials missing
        with self._mock_db_obj(profile_entry, 'credentials', None):
            with self.assertRaisesRegex(
                ValueError, 'Credentials in profile are missing'):
                post_install.PostInstallChecker(profile_entry)

        # simulate specs missing for FCP volume
        svol = profile_entry.storage_volumes_rel[0]
        with self._mock_db_obj(svol, 'specs', None):
            with self.assertRaisesRegex(
                ValueError,
                'FCP parameters of volume {} not set: '.format(
                    svol.volume_id)):
                post_install.PostInstallChecker(profile_entry)
    # test_missing_profile_params()

    def test_missing_os(self):
        """
        Exercise the case where no OS is specified in profile
        """
        profile_entry = self._get_profile('cpc3lp52', 'fcp1')
        self._set_mocks_lpar_fcp(profile_entry)

        # simulate os not specified - in this case a warning is logged
        with self._mock_db_obj(profile_entry, 'operating_system_id', None):
            post_install.PostInstallChecker(profile_entry)
            self._mock_logger.warning.assert_called_with(
                'System profile has no OS defined, skipping OS check')
    # test_missing_os()

    def test_ipv6(self):
        """
        Test ipv6 address validation.
        """
        profile_entry = self._get_profile('cpc3lp52', 'fcp1')
        self._set_mocks_lpar_fcp(profile_entry)

        address_entry = profile_entry.system_ifaces_rel[0].ip_address_rel
        subnet_entry = (profile_entry.system_ifaces_rel[0]
                        .ip_address_rel.subnet_rel)
        with self._mock_db_obj(subnet_entry, 'address',
                               'fe80::/64'):
            with self._mock_db_obj(address_entry, 'address',
                                   'fe80::57:52ff:fe00:7600'):
                checker = post_install.PostInstallChecker(profile_entry)
                checker.verify(areas=['network'])
    # test_ipv6()

    def test_kernel(self):
        """
        Exercise verification of kernel version. This verification is likely to
        change when a json schema is defined for the parameters field in the
        system profile table for this reason we test it in a separate method.
        """
        profile_entry = self._get_profile('cpc3lp52', 'dasd1')
        self._set_mocks_lpar_dasd(profile_entry)

        params_content = {
            'kernel_version': '3.10.0-327.el7.s390x'
        }
        with self._mock_db_obj(profile_entry, 'parameters', params_content):
            checker = post_install.PostInstallChecker(profile_entry)
            checker.verify()
    # test_kernel()

    def test_custom_os(self):
        """
        Exercise passing a specific Operating System object for verification
        """
        profile_entry = self._get_profile('cpc3lp52', 'fcp1')
        self._set_mocks_lpar_fcp(profile_entry)
        os_entry = OperatingSystem.query.filter_by(name='rhel7.2').one()
        checker = post_install.PostInstallChecker(profile_entry, os_entry)
        error_msg = self._mismatch_msg.format(
            'OS name', os_entry.pretty_name,
            profile_entry.operating_system_rel.pretty_name)
        with self.assertRaises(post_install.Misconfiguration, msg=error_msg):
            checker.verify()

        # permissive - only logging occurs
        self._set_mocks_lpar_fcp(profile_entry)
        self._mock_logger.reset_mock()
        checker = post_install.PostInstallChecker(
            profile_entry, os_entry, permissive=True)
        checker.verify()
        # disk warnings might occur thus we look for the os warning message in
        # any order
        self._mock_logger.warning.assert_any_call(error_msg)
    # test_custom_os()
# TestPostInstallChecker
