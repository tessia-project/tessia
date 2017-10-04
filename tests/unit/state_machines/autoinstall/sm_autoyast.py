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
from tessia_engine.state_machines.autoinstall import sm_autoyast, sm_base
from tests.unit.state_machines.autoinstall import utils
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
    @staticmethod
    def _instantiate_machine():
        os_entry = utils.get_os("sles12.1")
        profile_entry = utils.get_profile("CPC3LP54/lpar_cpc3lp54_install")
        template_entry = utils.get_template("SLES12.1")

        return sm_autoyast.SmAutoyast(os_entry, profile_entry, template_entry)
    # _instantiate_machine()

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

        patcher = patch.object(sm_autoyast, 'sleep', autospec=True)
        self._mock_sleep_autoyast = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'sleep', autospec=True)
        self._mock_sleep_base = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_autoyast, 'time', autospec=True)
        self._mock_time = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_time.return_value = 0

        patcher = patch.object(sm_base, 'SshClient', autospec=True)
        self._mock_ssh_client = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'PostInstallChecker', autospec=True)
        self._mock_checker = patcher.start()
        self.addCleanup(patcher.stop)

        # fake call to time so that we don't have to actually wait for the
        # timeout to occur
        def time_generator():
            """Simulate time.time()"""
            start = 1.0
            yield start
            while True:
                # step is half of timeout time to cause two loop iterations
                start += sm_base.CONNECTION_TIMEOUT/2
                yield start
        patcher = patch.object(sm_base, 'time', autospec=True)
        mock_time = patcher.start()
        self.addCleanup(patcher.stop)
        get_time = time_generator()
        mock_time.side_effect = lambda: next(get_time)

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
        ssh_cmds = [
            (0, ""), # first time to kill the start_shell
            (1, ""), # check if log file exists
            (0, ""), # log file now exists
            (0, "some_content\nsome_content"), # read log file, some content
            # read log file has now empty content, triggers verification for
            # yast2 process
            (0, ""),
            (0, ""), # yast2 still running
            (1, ""), # failed to read log file, back to yast2 verification
            (1, ""), # yast2 finished
            (0, ""), # last reading of log file
            TimeoutError(), # kill second start_shell to allow kexec
            (0, ""), # systemctl status in check_installation
            ConnectionError(), # connection died due to last reboot
            (0, "1") # echo 1 from sm_base.check_installation
        ]
        mock_shell.run.side_effect = ssh_cmds

        machine = self._instantiate_machine()
        machine.start()

        # validate behavior
        self.assertTrue(len(mock_shell.run.call_args_list) == len(ssh_cmds))
    # test_normal_installation()

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
        Test the case when the installation times out and a TimeoutError is
        raised.
        """
        def time_generator():
            """Generator for increasing time counter"""
            start = 1.1
            while True:
                start += 50.111
                yield start
        get_time = time_generator()
        self._mock_time.side_effect = lambda: next(get_time)

        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        ssh_cmds = [
            (0, ""), # first time to kill the start_shell
            (1, ""), # check if log file exists
            (0, ""), # log file now exists
            (0, "some_content\nsome_content"), # read log file, some content
            # read log file has now empty content, triggers verification for
            # yast2 process
            (0, ""),
        ]
        ssh_cmds += [(0, "")] * 50 # yast2 still running
        mock_shell.run.side_effect = ssh_cmds

        machine = self._instantiate_machine()
        with self.assertRaisesRegex(TimeoutError, "Installation Timeout"):
            machine.start()
    # test_installation_timeout()

    def test_installation_timeout_log_file(self):
        """
        Test the case when a timeout occurs while waiting for creation of
        installer log file
        """
        def time_generator():
            """Generator for increasing time counter"""
            start = 1.1
            while True:
                start += 50.111
                yield start
        get_time = time_generator()
        self._mock_time.side_effect = lambda: next(get_time)

        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        # generate a lot failures as response when checking if log file was
        # created
        mock_shell.run.side_effect = [(0, '')] + [(1, '')] * 50

        machine = self._instantiate_machine()
        with self.assertRaisesRegex(
            TimeoutError, "Timed out while waiting for installation logfile"):
            machine.start()
    # test_wait_install_timeout_log_file()
# TestSmAutoyast
