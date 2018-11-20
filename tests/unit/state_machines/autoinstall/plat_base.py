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
Module for the TestPlatBase class.
"""

#
# IMPORTS
#

from tessia.server.db.connection import MANAGER
from tessia.server.state_machines.autoinstall import plat_base
from tessia.server.state_machines.autoinstall.sm_base import SmBase
from tests.unit.state_machines.autoinstall import utils
from unittest import TestCase
from unittest.mock import patch, Mock

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class TestPlatBase(TestCase):
    """
    Class for unit testing the PlatBase class.
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
        # patch logger
        patcher = patch.object(plat_base, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)
        mock_logging.getLogger.return_value = Mock(
            spec=['warning', 'error', 'debug', 'info'])

        patcher = patch.object(plat_base, 'SshClient', autospec=True)
        self._mock_ssh_client_cls = patcher.start()
        self.addCleanup(patcher.stop)
        mock_ssh_client = self._mock_ssh_client_cls.return_value
        mock_shell = mock_ssh_client.open_shell.return_value
        mock_shell.run.side_effect = TimeoutError

        # We cannot use autospec here because the Hypervisor class does not
        # really have all the methods since it is a factory class.
        patcher = patch.object(plat_base, 'Hypervisor')
        self._mock_hypervisor = patcher.start()
        self.addCleanup(patcher.stop)

        class PlatBaseChild(plat_base.PlatBase):
            """
            Child class that implements the PlatBase abstract class.
            """
            def boot(self, kargs):
                """
                Look at the base class for the docstring.
                """
                super().boot(kargs)
            # boot()

            def get_vol_devpath(self, vol_obj):
                """
                Look at the base class for the docstring.
                """
                super().get_vol_devpath(vol_obj)
            # get_vol_devpath()
        self._child_cls = PlatBaseChild

        self._os_entry = utils.get_os("rhel7.2")
        self._profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        self._hyper_profile_entry = self._profile_entry.hypervisor_profile_rel
        self._repo_entry = self._os_entry.repository_rel[0]

        self._gw_iface_entry = self._profile_entry.gateway_rel
        # gateway interface not defined: use first available
        if self._gw_iface_entry is None:
            self._gw_iface_entry = self._profile_entry.system_ifaces_rel[0]

        # TODO: this is very ugly, but it is the only way to create
        # the parameters necessary for the creation of the PlatBase.
        self._parsed_gw_iface = (
            SmBase._parse_iface(self._gw_iface_entry, True))
    # setUp()

    def _create_plat_base(self):
        """
        Auxiliary method that create a PlatBaseChild instance based on
        the testcase inforamtion.
        """
        return self._child_cls(self._hyper_profile_entry, self._profile_entry,
                               self._os_entry, self._repo_entry,
                               self._parsed_gw_iface)
    # _create_plat_base()

    def test_init(self):
        """
        Test the correct initialization and the operations of a
        PlatBase object.
        """
        # The instance of the Hypervisor class.
        hyper = self._mock_hypervisor.return_value
        plat = self._create_plat_base()

        # Asserts that we are correctly creating the Hypervisor
        self._mock_hypervisor.assert_called_with(
            "hmc", self._hyper_profile_entry.system_rel.name,
            self._hyper_profile_entry.system_rel.hostname,
            self._hyper_profile_entry.credentials["admin-user"],
            self._hyper_profile_entry.credentials["admin-password"],
            None)
        hyper.login.assert_called_with()

        # Performs the reboot operation.
        plat.reboot(self._profile_entry)

        hostname = self._profile_entry.system_rel.hostname
        user = self._profile_entry.credentials['admin-user']
        password = self._profile_entry.credentials['admin-password']

        # make sure the reboot procedure was properly executed
        mock_ssh_client = self._mock_ssh_client_cls.return_value
        mock_ssh_client.login.assert_called_with(hostname, user=user,
                                                 passwd=password,
                                                 timeout=10)
        mock_shell = mock_ssh_client.open_shell.return_value
        mock_shell.run.assert_called_with(
            'nohup reboot -f; nohup killall sshd', timeout=1)

    # test_init()

    def test_unknown_hypervisor(self):
        """
        Test the case that the hypervisor is unknown.
        """
        system_entry = self._profile_entry.system_rel
        backup_name = system_entry.type_rel.name

        def restore_system_type():
            """
            Inner function to restore the value of system type
            after the execution of the tests.
            """
            system_entry.type_rel.name = backup_name
            MANAGER.session.commit()
        # restore_system_type()
        self.addCleanup(restore_system_type)

        # Modify the hypervisor type.
        system_entry.type_rel.name = "unknown"
        MANAGER.session.commit()

        with self.assertRaisesRegex(RuntimeError, "Unknown hypervisor"):
            self._create_plat_base()
            # test_unknown_hypervisor()

    def test_abstract_methods(self):
        """
        Test that the abstract methods are not implemented.
        """
        plat = self._create_plat_base()
        method_names = ('boot', 'get_vol_devpath')

        for method_name in method_names:
            method = getattr(plat, method_name)
            self.assertRaises(NotImplementedError, method, "SOME PARAM")
    # test_abstract_methods()

# TestPlatBase
