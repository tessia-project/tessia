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
This module contains all unit tests for the Autoyast state machine.
"""

#
# IMPORTS
#
from tessia_engine.state_machines.install import sm_autoyast, sm_base
from tests.unit.state_machines.install import utils
from unittest.mock import MagicMock, Mock, patch
from unittest import TestCase

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestSmAutoyast(TestCase):
    """
    Class for unit testing the SmAnaconda class.
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
        self._mock_plat_lpar = Mock(spec_set=sm_base.PlatLpar)
        self._mock_plat_kvm = Mock(spec_set=sm_base.PlatKvm)

        self._mocked_supported_platforms = {
            'lpar': self._mock_plat_lpar,
            'kvm': self._mock_plat_kvm
        }

        dict_patcher = patch.dict(sm_base.PLATFORMS,
                                  values=self._mocked_supported_platforms)
        dict_patcher.start()
        self.addCleanup(dict_patcher.stop)

        patcher = patch("builtins.open", autospec=True)
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_autoyast, 'logging', autospec=True)
        self._mock_logging_autoyast = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'logging', autospec=True)
        self._mock_logging_base = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'Config', autospec=True)
        self._mock_config = patcher.start()
        self.addCleanup(patcher.stop)

        self._mock_config.get_config.return_value = MagicMock()

        patcher = patch.object(sm_base, 'os', autospec=True)
        self._mock_os = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'urljoin', autospec=True)
        self._mock_urljoin = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_autoyast, 'sleep', autospec=True)
        self._mock_sleep_autoyast = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'sleep', autospec=True)
        self._mock_sleep_base = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'SshClient', autospec=True)
        self._mock_ssh_client = patcher.start()
        self.addCleanup(patcher.stop)

        # reset variables due to timeout tests
        sm_autoyast.INSTALLATION_TIMEOUT = 600
        sm_autoyast.CHECK_INSTALLATION_FREQ = 10

        # We do not patch the jsonschema in order to validate the expressions
        # that are used in the request.
    # setUp()

    def test_normal_installation(self):
        """
        Test the correct execution of the install machine.
        """
        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        mock_shell.run.return_value = 0, ""

        machine = self._instantiate_machine()
        machine.start()
    # test_init()

    def test_connect_installer_timeout(self):
        """
        Test when install machine fails to connect with guest being installed.
        """
        self._mock_ssh_client.return_value.login.side_effect = ConnectionError
        machine = self._instantiate_machine()
        with self.assertRaises(ConnectionError):
            machine.start()
    # test_wait_install_fails_ssh_timeout()

    def test_kill_shell_error(self):
        """
        On sles, we open a shell at the beginning and end of the
        installations. Test the case when killing the shell (so the installer
        can start) fails.
        """
        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        mock_shell.run.return_value = -1, ""

        machine = self._instantiate_machine()
        with self.assertRaises(RuntimeError):
            machine.start()
    # test_kill_shell_error()

    def test_read_installation_log_error(self):
        """
        Test when an error raises while reading installation logs due to some
        sort of file reading error.
        """
        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        mock_shell.run.side_effect = [[0, ""], [-1, ""]]

        machine = self._instantiate_machine()
        with self.assertRaises(StopIteration):
            machine.start()

    # test_read_installation_log_error()

    def test_installation_timeout(self):
        """
        Each installation has a timeout of 10 minutes. Test the case when the
        installation timeouts and a TimeoutError will be raised.
        """
        sm_autoyast.INSTALLATION_TIMEOUT = 0
        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        mock_shell.run.return_value = 0, ""

        machine = self._instantiate_machine()
        with self.assertRaises(TimeoutError):
            machine.start()
    # test_installation_timeout()

    def test_installation_checking_freq(self):
        """
        Test if the state machine waits the installation according to
        the CHECK_INSTALLATION_FREQ variable.
        """
        sm_autoyast.CHECK_INSTALLATION_FREQ = 0
        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        mock_shell.run.side_effect =[
            [0, ""], # killing the shell
            [0, "first\nsecond"], # tailing the log file
            [0, "some_dummy_pid"], # checking the installer
            [0, ""], # tailing log again
            [0, ""], # ending installer
            [0, ""] # check installation
        ]
        machine = self._instantiate_machine()
        machine.start()
        self._mock_sleep_autoyast.assert_called_with(0)
    # test_installation_timeout()

    def _instantiate_machine(self): # pylint: disable=no-self-use
        os_entry = utils.get_os("sles12.1")
        profile_entry = utils.get_profile("CPC3LP54/lpar_cpc3lp54_install")
        template_entry = utils.get_template("SLES12.1")

        return sm_autoyast.SmAutoyast(os_entry, profile_entry, template_entry)
    # _instantiate_machine()
# TestSmAutoyast
