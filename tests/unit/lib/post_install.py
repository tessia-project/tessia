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
from unittest.mock import patch

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

    def _set_mocks_lpar_fcp(self):
        """
        Prepare mocks to return content of a lpar with fcp disks installation.
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

        crash_size = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
205520896
"""
        )

        self._mock_check_output.side_effect = [
            facts, parted_1, lsblk_1, parted_2, lsblk_2, lszfcp, crash_size]
    # _set_mocks_lpar_fcp()

    def _set_mocks_lpar_dasd(self):
        """
        Prepare mocks to return content of a lpar with dasd disks installation.
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

        crash_size = (
            """cpc3lp52.domain.com | SUCCESS | rc=0 >>
168820736
"""
        )

        self._mock_check_output.side_effect = [
            facts, parted_1, lsblk_1, parted_2, lsblk_2, lszfcp, crash_size]
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
        self._set_mocks_lpar_dasd()
        orig_outputs = list(self._mock_check_output.side_effect)

        # simulate invalid facts content
        test_outputs = orig_outputs[:]
        test_outputs[0] = test_outputs[0].replace(
            'ansible_facts', 'ansible_wrong_facts')
        self._mock_check_output.side_effect = test_outputs
        with self.assertRaisesRegex(
            SystemError, 'Could not parse output from ansible facts: '):
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
        Test verification of a LPAR with DASD based installation.
        """
        self._set_mocks_lpar_dasd()

        profile_entry = self._get_profile('cpc3lp52', 'dasd1')
        checker = post_install.PostInstallChecker(profile_entry)
        checker.verify()
    # test_lpar_dasd()

    def test_lpar_fcp(self):
        """
        Test verification of a LPAR with FCP based installation.
        """
        self._set_mocks_lpar_fcp()

        profile_entry = self._get_profile('cpc3lp52', 'fcp1')
        checker = post_install.PostInstallChecker(profile_entry)
        checker.verify()
    # test_lpar_fcp()

    def test_misconfiguration(self):
        """
        Test scenarios where actual config does not match expected from
        profile. This test also exercises the areas= parameter of the verify()
        method.
        """
        fcp_prof_entry = self._get_profile('cpc3lp52', 'fcp1')

        # cpu mismatch
        self._set_mocks_lpar_fcp()
        with self._mock_db_obj(fcp_prof_entry, 'cpu', 99):
            error_msg = self._mismatch_msg.format('cpu quantity', 99, 2)
            checker = post_install.PostInstallChecker(fcp_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['cpu'])

        # min memory mismatch
        self._set_mocks_lpar_fcp()
        with self._mock_db_obj(fcp_prof_entry, 'memory', 5000):
            # actual is calculated by using ansible_total_mb + crash_size set
            # by mock
            error_msg = self._mismatch_msg.format(
                'minimum MiB memory', 4872, 4011)
            checker = post_install.PostInstallChecker(fcp_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['memory'])

        # max memory mismatch
        self._set_mocks_lpar_fcp()
        with self._mock_db_obj(fcp_prof_entry, 'memory', 3000):
            # actual is calculated by using ansible_total_mb + crash_size set
            # by mock
            error_msg = self._mismatch_msg.format(
                'maximum MiB memory', 3128, 4011)
            checker = post_install.PostInstallChecker(fcp_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['memory'])

        # os mismatch
        self._set_mocks_lpar_fcp()
        os_entry = fcp_prof_entry.operating_system_rel
        with self._mock_db_obj(os_entry, 'minor', 8):
            error_msg = self._mismatch_msg.format('OS version release', 8, 4)
            checker = post_install.PostInstallChecker(fcp_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['os'])
        # os mismatch - non numeric version
        self._set_mocks_lpar_fcp()
        check_outputs = list(self._mock_check_output.side_effect)
        check_outputs[0] = check_outputs[0].replace(
            '"ansible_distribution_version": "16.04"',
            '"ansible_distribution_version": "16.04a"')
        self._mock_check_output.side_effect = check_outputs
        error_msg = self._mismatch_msg.format('OS version release', '4', '04a')
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['os'])

        # network - gateway mismatch
        self._set_mocks_lpar_fcp()
        check_outputs = list(self._mock_check_output.side_effect)
        # simulate missing gateway
        check_outputs[0] = check_outputs[0].replace(
            'gateway', 'hide_gateway')
        self._mock_check_output.side_effect = check_outputs
        error_msg = self._mismatch_msg.format(
            'gateway', '192.168.160.1', '<not found>')
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['network'])
        # simulate invalid gateway
        check_outputs[0] = check_outputs[0].replace(
            '"hide_gateway": "192.168.160.1"',
            '"gateway": "192.152.160.1"')
        self._mock_check_output.side_effect = check_outputs
        error_msg = self._mismatch_msg.format(
            'gateway', '192.168.160.1', '192.152.160.1')
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['network'])

        # network - dns mismatch
        self._set_mocks_lpar_fcp()
        subnet_entry = (fcp_prof_entry.system_ifaces_rel[0]
                        .ip_address_rel.subnet_rel)
        with self._mock_db_obj(subnet_entry, 'dns_2', '8.8.8.8'):
            error_msg = self._mismatch_msg.format(
                'iface enccw0.0.f500 nameservers', '8.8.8.8', '<not found>')
            checker = post_install.PostInstallChecker(fcp_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['network'])

        # storage - no fcp paths
        # use facts from a dasd-only config to simulate no fcp devices found
        self._set_mocks_lpar_dasd()
        error_msg = self._mismatch_msg.format(
            'fcp paths', 'fcp path for LUN 1022400000000000', '<not found>')
        checker = post_install.PostInstallChecker(fcp_prof_entry)
        with self.assertRaisesRegex(
            post_install.Misconfiguration, error_msg):
            checker.verify(areas=['storage'])

        dasd_prof_entry = self._get_profile('cpc3lp52', 'dasd1')
        # storage - disk min size mismatch
        self._set_mocks_lpar_dasd()
        vol_entry = dasd_prof_entry.storage_volumes_rel[0]
        with self._mock_db_obj(vol_entry, 'size', 15000):
            dasd_devpath = '/dev/disk/by-path/ccw-0.0.3956'
            error_msg = self._mismatch_msg.format(
                'min MiB size disk {}'.format(dasd_devpath), '14800', '7043')
            checker = post_install.PostInstallChecker(dasd_prof_entry)
            with self.assertRaisesRegex(
                post_install.Misconfiguration, error_msg):
                checker.verify(areas=['storage'])

        # storage - part min size mismatch
        self._set_mocks_lpar_dasd()
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

        # kernel mismatch
        self._set_mocks_lpar_dasd()
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

    # test_misconfiguration()

    def test_missing_profile_params(self):
        """
        Force error when profile has missing information
        """
        self._set_mocks_lpar_fcp()

        # simulate credentials missing
        profile_entry = self._get_profile('cpc3lp52', 'fcp1')
        with self._mock_db_obj(profile_entry, 'credentials', None):
            with self.assertRaisesRegex(
                ValueError, 'Credentials in profile are missing'):
                post_install.PostInstallChecker(profile_entry)

        # simulate os not specified
        with self._mock_db_obj(profile_entry, 'operating_system_id', None):
            with self.assertRaisesRegex(
                ValueError, 'No operating system specified in profile'):
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

    def test_ipv6(self):
        """
        Test ipv6 address validation.
        """
        self._set_mocks_lpar_fcp()
        profile_entry = self._get_profile('cpc3lp52', 'fcp1')

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
        self._set_mocks_lpar_dasd()
        profile_entry = self._get_profile('cpc3lp52', 'dasd1')

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
        self._set_mocks_lpar_fcp()
        profile_entry = self._get_profile('cpc3lp52', 'fcp1')
        os_entry = OperatingSystem.query.filter_by(name='rhel7.2').one()
        checker = post_install.PostInstallChecker(profile_entry, os_entry)
        with self.assertRaisesRegex(
            post_install.Misconfiguration,
            self._mismatch_msg.format('OS name', 'rhel', 'ubuntu')):
            checker.verify()
    # test_custom_os()
# TestPostInstallChecker
