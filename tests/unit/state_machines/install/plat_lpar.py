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
from unittest import TestCase
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
        self._mock_hypervisor = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(plat_lpar, 'SshClient', autospec=True)
        self._mock_ssh_client = patcher.start()
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

    def test_init(self):
        """
        Test the correct initialization and the operations of a
        PlatLpar object.
        """
        # The instance of the Hypervisor class.
        hyper = self._mock_hypervisor.return_value
        plat = self._create_plat_lpar()

        # Asserts that we are correctly creating the Hypervisor
        self._mock_hypervisor.assert_called_with(
            "hmc", self._hyper_profile_entry.system_rel.name,
            self._hyper_profile_entry.system_rel.hostname,
            self._hyper_profile_entry.credentials["username"],
            self._hyper_profile_entry.credentials["password"],
            None)
        hyper.login.assert_called_with() #pylint: disable=no-member

        # Performs the reboot operation.
        plat.reboot(self._profile_entry)
    # test_init()
# TestPlatLpar
