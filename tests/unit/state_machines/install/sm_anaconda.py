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
This module does this and that.

ome more detailed info about the module here.
"""

#
# IMPORTS
#
from tessia_engine.db.connection import MANAGER
from tessia_engine.state_machines.install import sm_anaconda, sm_base
from tests.unit.state_machines.install import utils
from unittest.mock import MagicMock, Mock, patch
from unittest import TestCase

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestSmAnaconda(TestCase):
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

        patcher = patch.object(sm_anaconda, 'logging', autospec=True)
        self._mock_logging = patcher.start()
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

        patcher = patch.object(sm_base, 'SshClient', autospec=True)
        self._mock_ssh_client = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'urljoin', autospec=True)
        self._mock_urljoin = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'sleep', autospec=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_anaconda, 'sleep', autospec=True)
        self._mock_sleep_base = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_anaconda, 'time', autospec=True)
        self._mock_time = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_time.return_value = 0

        # We do not patch the jsonschema in order to validate the expressions
        # that are used in the request.

        # Open the connection with the database so that it can be used in the
        # tests. Even for tests that does not directly use the session, we must
        # create a session in order to fullfill the models with the query
        # object.
        self.session = MANAGER.session()
    # setUp()

    def test_init(self):
        """
        Test the correct execution of the install machine.
        """
        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("RHEL7.2")
        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        mock_shell.run.return_value = 0, "Thread Done: AnaConfigurationThread"

        mach = sm_anaconda.SmAnaconda(os_entry, profile_entry, template_entry)
        mach.start()
    # test_init()

    def test_wait_install_fails_ssh_timeout(self):
        """
        Test the case that the install machine fails to connect the guest
        being installed.
        """
        self._mock_ssh_client.return_value.login.side_effect = ConnectionError
        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("RHEL7.2")

        mach = sm_anaconda.SmAnaconda(os_entry, profile_entry, template_entry)
        with self.assertRaisesRegex(ConnectionError, "Error while"):
            mach.start()
    # test_wait_install_fails_ssh_timeout(self)

    def test_wait_install_timeout(self):
        """
        Test the case when a timeout occurs while waiting for log file output
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
            (1, ""), # first time to check if anaconda.log exists
            (0, ""), # anaconda.log now exists
            (0, ""), # read log file, empty content
        ]
        # generate a lot of responses to reading the log file
        ssh_cmds.extend([(0, 'some_line')] * 50)
        mock_shell.run.side_effect = ssh_cmds

        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("RHEL7.2")

        mach = sm_anaconda.SmAnaconda(os_entry, profile_entry, template_entry)
        with self.assertRaisesRegex(TimeoutError, "Installation Timeout"):
            mach.start()
    # test_wait_install_timeout()

    def test_wait_install_timeout_log_file(self):
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
        # generate a lot failures to check if log file was created
        mock_shell.run.side_effect = [(1, '')] * 50

        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("RHEL7.2")

        mach = sm_anaconda.SmAnaconda(os_entry, profile_entry, template_entry)
        with self.assertRaisesRegex(
            TimeoutError, "Timed out while waiting for installation logfile"):
            mach.start()
    # test_wait_install_timeout_log_file()

    def test_installation_error_from_log(self):
        """
        Test the case that an error is detected in the log during the
        installation process.
        """
        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("RHEL7.2")
        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        mach = sm_anaconda.SmAnaconda(os_entry, profile_entry, template_entry)
        mock_shell.run.side_effect = [
            (0, "Some Text"),
            (0, ""),
            (0, "<time> ERR anaconda: storage configuration"
             " failed: some message"),
            (-1, "ERROR")]
        with self.assertRaisesRegex(RuntimeError, "Anaconda storage"
                                    " configuration"):
            mach.start()
    # test_installation_error_from_log()
# TestSmAnaconda
