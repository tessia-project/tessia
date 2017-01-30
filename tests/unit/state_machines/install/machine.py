# Copyright 2016, 2017 IBM Corp.
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
Unit tests for Install state machine.
"""

#
# IMPORTS
#
from tessia_engine.db import models
from tessia_engine.db.connection import MANAGER
from tessia_engine.state_machines.install import machine
from tests.unit.db.models import DbUnit
from unittest.mock import patch
from unittest import TestCase

import json
import os

#
# CONSTANTS AND DEFINITIONS
#
REQUEST_PARAMETERS = """{"profile": "kvm054/kvm_kvm054_install",
"template": "RHEL7.2"}
"""

#
# CODE
#
class TestInstallMachine(TestCase):
    """
    Class for unit tests of the InstallMachine class
    """
    @classmethod
    def setUpClass(cls):
        """
        Called once for the setup of DbUnit.
        """
        # Load the database content specifically prepared for this
        # test.
        data_file = "{}/data.json".format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(data_file, "r") as data_fd:
            data = data_fd.read()

        # The template is loaded separately since json files does not
        # accept multiline strings.
        template_file = "{}/template.ks".format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(template_file, "r") as template_fd:
            template = template_fd.read()

        data_dict = json.loads(data)
        data_dict["Template"][0]["content"] = template

        # Create a database using custom content,
        DbUnit.create_db(empty=True)
        DbUnit.create_entry(data_dict)
    # setUpClass()

    def setUp(self):
        """
        Setup all the mocks used for the execution of the tests.
        """
        patcher = patch.object(machine, "sleep", autospec=True)
        self._mock_sleep = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, "print")
        self._mock_print = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, "open")
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, "os", autospec=True)
        self._mock_os = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, "SshClient", autospec=True)
        self._mock_ssh_client = patcher.start()
        self.addCleanup(patcher.stop)

        # We cannot use autospec here due to the fact that the Hypervisor
        # class is a factory class that uses the magic method __getattr__
        # to access the methods of the instance it produces.
        patcher = patch.object(machine, "Hypervisor")
        self._mock_hypervisor = patcher.start()
        self.addCleanup(patcher.stop)

        # Open the connection with the database.
        self.session = MANAGER.session()
    # setUp()

    def _restore_template_record(self):
        """
        Restore the content of a record modified during a test.
        """
        template = models.Template.query.filter_by(name="RHEL7.2").one()
        template.template_type = "RHEL"
        self.session.add(template)
        self.session.commit()
    # _restore_template_record()

    def test_parse_request_parameters(self):
        """
        Test the correct extraction of the resources from the request
        parameters.
        """
        parsed_request = machine.InstallMachine.parse(REQUEST_PARAMETERS)
        resources = parsed_request["resources"]

        # Now we check that the resources were correctly allocated
        # according to the database specified in data.json
        self.assertIn("kvm054", resources["exclusive"])
        self.assertIn("cpc3lp55", resources["shared"])
        self.assertIn("cpc0", resources["shared"])
        self.assertNotIn("kvm054", resources["shared"])
    # test_parse_request_parameters()

    def test_malformed_request_parameters(self):
        """
        Test the case the state machine receives a malformed request
        (string containing a malformed json).
        """
        # Malformed json
        malformed_request_parameters = """{"profile": "kvm_kvm054_install",
        "template":
        """
        with self.assertRaises(SyntaxError):
            machine.InstallMachine.parse(malformed_request_parameters)
    # test_malformed_request_parameters()

    def test_invalid_request_parameters(self):
        """
        Test the case that the state machine receives an invalid
        request parameters.
        """
        # Invalid request parameter with one missing property
        invalid_request_parameters1 = '{"profile": "kvm_kvm054_install"}'
        # Invalid request with additional parameter
        invalid_request_parameters2 = """{"profile": "kvm_kvm054_install",
        "template": "RHEL7.2", "other_parameters": "value"}
        """
        with self.assertRaises(SyntaxError):
            machine.InstallMachine.parse(invalid_request_parameters1)
            machine.InstallMachine.parse(invalid_request_parameters2)
    # test_invalid_request_parameters()

    def test_start(self):
        """
        Test the start method for the case the InstallMachine performs a
        complete and correct system installation.
        """
        mock_ssh = self._mock_ssh_client.return_value
        mock_shell = mock_ssh.open_shell.return_value
        mock_shell.run.side_effect = [
            (0, "blah"),
            (0, "Thread Done: AnaConfigurationThread")
        ]

        mock_hyp = self._mock_hypervisor.return_value
        mach = machine.InstallMachine(REQUEST_PARAMETERS)

        ret = mach.start()

        self.assertEqual(ret, 0)
        self._mock_hypervisor.assert_called_with(
            "kvm", "cpc3lp55",
            "cpc3lp55.domain.com",
            "root", "somepasswd", None)
        #pylint: disable=protected-access
        mock_hyp.start.assert_called_with("kvm054", 2, 1024,
                                          mach._config["parameters"])
        ret = mach.cleanup()
        self.assertEqual(ret, 0)
    # test_start()

    def test_cleanup_fail(self):
        """
        Test the case the cleanup fails (by not removing the autofile).
        """
        mock_ssh = self._mock_ssh_client.return_value
        mock_shell = mock_ssh.open_shell.return_value
        mock_shell.run.side_effect = [
            (0, "blah"),
            (0, "Thread Done: AnaConfigurationThread")
        ]

        # Raise OSError while deleting the autofile
        self._mock_os.remove.side_effect = OSError
        mach = machine.InstallMachine(REQUEST_PARAMETERS)
        ret = mach.start()

        ret = mach.cleanup()

        self.assertEqual(ret, 1)
    # test_start()

    def test_start_default_profile(self):
        """
        Test the start method for the case the InstallMachine performs a
        complete and correct system installation.
        """
        request_params_default_prof = """
        {"profile": "kvm054",
        "template": "RHEL7.2"}
        """
        mock_ssh = self._mock_ssh_client.return_value
        mock_shell = mock_ssh.open_shell.return_value
        mock_shell.run.side_effect = [
            (0, "blah"),
            (0, "Thread Done: AnaConfigurationThread")
        ]

        mock_hyp = self._mock_hypervisor.return_value
        mach = machine.InstallMachine(request_params_default_prof)

        ret = mach.start()

        self.assertEqual(ret, 0)
        self._mock_hypervisor.assert_called_with(
            "kvm", "cpc3lp55",
            "cpc3lp55.domain.com",
            "root", "somepasswd", None)
        #pylint: disable=protected-access
        mock_hyp.start.assert_called_with("kvm054", 2, 1024,
                                          mach._config["parameters"])
        mach.cleanup()
    # test_start()

    def test_no_ssh_connection(self):
        """
        Test the case that it is not possible to connect through ssh after
        starting the guest.
        """
        mock_ssh = self._mock_ssh_client.return_value
        mock_ssh.login.side_effect = ConnectionError
        mach = machine.InstallMachine(REQUEST_PARAMETERS)
        ret = mach.start()
        # After 4 trials, the install machine will declare a error.
        self.assertEqual(mock_ssh.login.call_count, 4)
        self.assertEqual(ret, 1)
    # test_no_ssh_connection()

    def test_error_executing_command_rhel(self):
        """
        Test the case the ssh shell returns an error while trying to get
        the anaconda installation log. This could happen for example, if the
        anaconda log file does not exist.
        """
        mock_ssh = self._mock_ssh_client.return_value
        mock_shell = mock_ssh.open_shell.return_value
        mock_shell.run.return_value = 1, ""
        mach = machine.InstallMachine(REQUEST_PARAMETERS)

        ret = mach.start()

        self.assertEqual(ret, 1)
    # test_error_executing_command_rhel()

    def test_waiting_installation_timout_rhel(self):
        """
        Test the case the installation procedure of rhel takes more than
        10 minutes so a timeout happens.
        """
        mock_ssh = self._mock_ssh_client.return_value
        mock_shell = mock_ssh.open_shell.return_value
        mock_shell.run.return_value = 0, "SOME LOG"
        mach = machine.InstallMachine(REQUEST_PARAMETERS)
        ret = mach.start()
        self.assertEqual(ret, 1)
    # test_waiting_installation_timout_rhel()

    def test_invalid_handler_wait_installation(self):
        """
        Test the case there isn't any handler to monitor the installation
        process.
        """
        # Modify the template type so that there isn't any handler
        # to monitor this type of installation.
        template = models.Template.query.filter_by(name="RHEL7.2").one()
        template.template_type = "SOME_OTHER_TYPE"
        self.session.add(template)
        self.session.commit()

        # Restore the modified template record in the database after test
        self.addCleanup(self._restore_template_record)

        mach = machine.InstallMachine(REQUEST_PARAMETERS)
        ret = mach.start()
        self.assertEqual(ret, 1)
    # test_invalid_handler_wait_installation()
# TestInstallMachine
