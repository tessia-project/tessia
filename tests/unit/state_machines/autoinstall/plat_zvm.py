# Copyright 2018 IBM Corp.
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
Unit test for the platform zvm module
"""

#
# IMPORTS
#
from tessia.baselib.hypervisors.zvm import HypervisorZvm
from tessia.server.state_machines.autoinstall.sm_base import SmBase
from tessia.server.state_machines.autoinstall import plat_zvm
from tests.unit.state_machines.autoinstall import utils
from unittest import TestCase
from unittest.mock import patch, Mock

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestPlatZvm(TestCase):
    """
    Class for unit testing the PlatZvm class.
    """
    @classmethod
    def setUpClass(cls):
        """
        Called once for the setup of DbUnit.
        """
        cls.db = utils.setup_dbunit()
    # setUpClass()

    def setUp(self):
        """
        Set the common mocks used in the tests
        """
        # patch logger
        patcher = patch.object(plat_zvm, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)
        mock_logging.getLogger.return_value = Mock(
            spec=['warning', 'error', 'debug', 'info'])

        # specify the class for autospec as the Hypervisor class is actually a
        # factory class
        patcher = patch.object(plat_zvm, 'Hypervisor', autospec=HypervisorZvm)
        self._mock_hyp_cls = patcher.start()
        self.addCleanup(patcher.stop)

        self._os_entry = utils.get_os("rhel7.2")
        self._prof_entry = utils.get_profile("vmguest01/default")
        self._hyper_prof_entry = self._prof_entry.hypervisor_profile_rel
        self._repo_entry = self._os_entry.repository_rel[0]
        self._gw_iface_entry = self._prof_entry.gateway_rel
        # gateway interface not defined: use first available
        if self._gw_iface_entry is None:
            self._gw_iface_entry = self._prof_entry.system_ifaces_rel[0]

        # get the parsed iface so that we can create the platform object
        self._parsed_gw_iface = (
            SmBase._parse_iface(self._gw_iface_entry, True))

        self._plat = plat_zvm.PlatZvm(
            self._hyper_prof_entry, self._prof_entry,
            self._os_entry, self._repo_entry, self._parsed_gw_iface)
    # setUp()

    def test_boot(self):
        """
        Test the boot operation
        """
        kargs = "param1=value1 param2=value2"
        self._plat.boot(kargs)

        guest_name = self._prof_entry.system_rel.name
        cpu = self._prof_entry.cpu
        memory = self._prof_entry.memory

        # validate behavior (call to baselib)
        args = self._mock_hyp_cls.return_value.start.mock_calls[0][1]
        self.assertEqual(args[0], guest_name)
        self.assertEqual(args[1], cpu)
        self.assertEqual(args[2], memory)
        self.assertIn('ifaces', args[3])
        self.assertIn('storage_volumes', args[3])
        self.assertIn('netboot', args[3])
        self.assertIn('kernel_uri', args[3]['netboot'])
        self.assertIn('initrd_uri', args[3]['netboot'])
        self.assertEqual(kargs, args[3]['netboot']['cmdline'])
    # test_boot()

    def test_get_vol_devpath(self):
        """
        Test the correct creation of the device paths for the volumes.
        """
        volumes = self._prof_entry.storage_volumes_rel

        # validate according to the database content
        devpaths = [
            "/dev/disk/by-path/ccw-0.0.3963",
            "/dev/disk/by-id/dm-uuid-mpath-11002076305aac1a0000000000002002",
            "/dev/disk/by-id/scsi-11002076305aac1a0000000000002003",
        ]

        for vol, devpath in zip(volumes, devpaths):
            self.assertEqual(self._plat.get_vol_devpath(vol), devpath)
    # test_get_vol_devpath()

    def test_init_error(self):
        """
        Verify that the platform object cannot be created if zvm credentials
        are missing in profile
        """
        orig_cred = self._prof_entry.credentials
        new_cred = orig_cred.copy()
        new_cred.pop('host_zvm')
        self._prof_entry.credentials = new_cred
        self.db.session.add(self._prof_entry)
        self.db.session.commit()

        with self.assertRaisesRegex(
            ValueError, 'zVM password not available in profile'):
            plat_zvm.PlatZvm(
                self._hyper_prof_entry, self._prof_entry, self._os_entry,
                self._repo_entry, self._parsed_gw_iface)

        # restore value
        self._prof_entry.credentials = orig_cred
        self.db.session.add(self._prof_entry)
        self.db.session.commit()
    # test_init_error()

# TestPlatZvm
