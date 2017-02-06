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
Module for the TestPlatLpar class.
"""

#
# IMPORTS
#
from tessia_engine.db.models import SystemIface
from tessia_engine.db.connection import MANAGER
from tessia_engine.state_machines.install import plat_base, plat_lpar
from tessia_engine.state_machines.install.sm_base import SmBase
from tests.unit.state_machines.install import utils
from unittest import mock, TestCase
from unittest.mock import patch

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestPlatLpar(TestCase):
    """
    Class for unit testing the PlatLpar class.
    """
    @classmethod
    def setUpClass(cls):
        """
        Called once for the setup of DbUnit.
        """
        utils.setup_dbunit()
    # setUpClass()

    def setUp(self):
        """
        Setup all the mocks used for the execution of the tests.
        """
        # We cannot use autospec here because the Hypervisor class does not
        # really have all the methods since it is a factory class.
        patcher = patch.object(plat_base, 'Hypervisor')
        self._mock_hypervisor_cls = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(plat_lpar, 'SshClient', autospec=True)
        self._mock_ssh_client_cls = patcher.start()
        self.addCleanup(patcher.stop)

        self._os_entry = utils.get_os("rhel7.2")
        self._profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        self._hyper_profile_entry = self._profile_entry.hypervisor_profile_rel
        self._repo_entry = self._os_entry.repository_rel[0]
        default_gw_name = self._profile_entry.parameters.get("gateway_iface")
        system_id = self._profile_entry.system_rel.id
        self._gw_iface_entry = SystemIface.query.filter_by(
            system_id=system_id,
            name=default_gw_name).one()

        # TODO: this is very ugly, but it is the only way to create
        # the parameters necessary for the creation of the PlatLpar.
        self._parsed_gw_iface = (
            SmBase._parse_iface( # pylint: disable=protected-access
                self._gw_iface_entry, True))

        # Create a session so we can change the objects in the tests.
        self._session = MANAGER.session()
    # setUp()

    def _create_plat_lpar(self):
        """
        Auxiliary method that create a PlatLparChild instance based on
        the testcase inforamtion.
        """
        return plat_lpar.PlatLpar(self._hyper_profile_entry,
                                  self._profile_entry,
                                  self._os_entry, self._repo_entry,
                                  self._parsed_gw_iface)
    # _create_plat_base()

    def test_boot(self):
        """
        Test the boot operation.
        """
        mock_hyp = self._mock_hypervisor_cls.return_value
        plat = self._create_plat_lpar()
        plat.boot("some kargs")

        guest_name = self._profile_entry.system_rel.name
        cpu = self._profile_entry.cpu
        memory = self._profile_entry.memory

        # We don't test the params argument since it is a complex
        # dictionary generated inside the init function.
        mock_hyp.start.assert_called_with(guest_name, cpu, memory,
                                          mock.ANY)
    # test_boot()

    def test_get_vol_devpath(self):
        """
        Test the correct creation of the device paths for the volumes.
        """
        plat = self._create_plat_lpar()
        volumes = self._profile_entry.storage_volumes_rel

        # Here we used specifc test cases, since we know the content
        # ot the database.
        devpaths = [
            "/dev/disk/by-path/ccw-0.0.3961",
            "/dev/disk/by-id/scsi-"
            "11002076305aac1a0000000000002407",
            "/dev/disk/by-id/dm-uuid-mpath-"
            "11002076305aac1a0000000000002408"
        ]

        for vol, devpath in zip(volumes, devpaths):
            self.assertEqual(plat.get_vol_devpath(vol), devpath)
    # test_get_vol_devpath()

    def test_reboot(self):
        """
        Test the correct initialization and the operations of a
        PlatLpar object.
        """
        plat = self._create_plat_lpar()

        # Performs the reboot operation.
        plat.reboot(self._profile_entry)

        mock_ssh_client = self._mock_ssh_client_cls.return_value
        hostname = self._profile_entry.system_rel.hostname
        user = self._profile_entry.credentials['username']
        password = self._profile_entry.credentials['password']

        # Makes sure the reboot procedure was properly executed.
        mock_ssh_client.login.assert_called_with(hostname, user=user,
                                                 passwd=password,
                                                 timeout=10)
        mock_shell = mock_ssh_client.open_shell.return_value
        mock_shell.run.assert_called_with('nohup reboot -f &>/dev/null',
                                          ignore_ret=True)

    # test_reboot()

    def test_unknown_volume_type(self):
        """
        Test the case a volume is of an unknown type.
        """
        # Save the type name for restore after the test.
        bk_type_name = self._profile_entry.storage_volumes_rel[0].type_rel.name
        def restore_type_name():
            """
            Inner function to restore the type name of the volume
            """
            self._profile_entry.storage_volumes_rel[0].type_rel.name = (
                bk_type_name)
            self._session.commit()
        # restore_type_name()
        self.addCleanup(restore_type_name)

        self._profile_entry.storage_volumes_rel[0].type_rel.name = "unknown"
        self._session.commit()
        plat = self._create_plat_lpar()

        volumes = self._profile_entry.storage_volumes_rel

        self.assertRaisesRegex(RuntimeError, "Unknown", plat.get_vol_devpath,
                               volumes[0])
    # test_unknown_volume_type()
# TestPlatLpar
