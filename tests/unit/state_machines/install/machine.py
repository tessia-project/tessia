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
from tests.unit.state_machines.install import utils
from unittest.mock import patch
from unittest import TestCase
from unittest.mock import Mock

import json

#
# CONSTANTS AND DEFINITIONS
#
REQUEST_PARAMETERS = json.dumps({
    "system": "kvm054",
    "profile": "kvm_kvm054_install",
    "template": "RHEL7.2"
})

#
# CODE
#
class TestAutoInstallMachine(TestCase):
    """
    Class for unit tests of the AutoInstallMachine class
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
        self._mock_sm_anaconda = Mock(spec_set=machine.SmAnaconda)
        self._mock_sm_autoyast = Mock(spec_set=machine.SmAutoyast)

        mocked_supported_distros = {
            'rhel': self._mock_sm_anaconda,
            'sles': self._mock_sm_autoyast
        }

        patcher_dict = patch.dict(machine.SUPPORTED_DISTROS,
                                  values=mocked_supported_distros)
        self._mocked_supported_distros = patcher_dict.start()
        self.addCleanup(patcher_dict.stop)

        patcher = patch.object(machine, 'logging', autospec=True)
        self._mock_logging = patcher.start()
        self.addCleanup(patcher.stop)

        # We do not patch the jsonschema in order to validate the expressions
        # that are used in the request.
    # setUp()

    def _perform_test_init(self, parameters):
        """
        Auxiliary method to test the initialization of the AutoInstallMachine
        with different parameters.

        Args:
            parameters (str): A string containing a json in the format:
            {
                "template": "<name of the template>",
                "os": "<name of the operating system>",
                "system": "<system_name>",
                "profile": "<name of the profile>"
            }
            "profile" is optional.
        """
        mach = machine.AutoInstallMachine(parameters)
        mach.start()
        mach.cleanup()
        # Assert that the methods of the correct install machine were called.
        self._mock_sm_anaconda.return_value.start.assert_called_once_with()
        self._mock_sm_anaconda.return_value.cleanup.assert_called_once_with()
    # _perform_test_init()

    def test_init(self):
        """
        Test the correct initialization of the AutoInstallMachine.
        """
        self._perform_test_init(REQUEST_PARAMETERS)
    # test_init()

    def test_init_default_profile(self):
        """
        Test the correct initialization of the AutoInstallMachine using the
        default profile.
        """
        request = json.dumps({
            "system": "kvm054",
            "template": "RHEL7.2"
        })

        self._perform_test_init(request)
    # test_init_default_profile()

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
        self.assertRaises(SyntaxError,
                          machine.AutoInstallMachine.parse,
                          invalid_request_parameters1)
        self.assertRaises(SyntaxError,
                          machine.AutoInstallMachine.parse,
                          invalid_request_parameters2)
    # test_invalid_request_parameters()

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
            machine.AutoInstallMachine.parse(malformed_request_parameters)
    # test_malformed_request_parameters()

    def test_nonexistent_os(self):
        """
        Test the case that an operating system does not exist in the database.
        """
        request = json.dumps({
            "system": "kvm054",
            "profile": "kvm_kvm054_install",
            "template": "RHEL7.2",
            "os": "Nonono"
        })

        with self.assertRaisesRegex(ValueError, "OS Nonono"):
            machine.AutoInstallMachine(request)
    # test_nonexistent_os()

    def test_nonexistent_template(self):
        """
        Test the case that the template does not exist in the database.
        """
        request = json.dumps({
            "system": "kvm054",
            "profile": "kvm_kvm054_install",
            "template": "Nonono"
        })
        with self.assertRaisesRegex(ValueError, "Template Nonono"):
            machine.AutoInstallMachine(request)
    # test_nonexistent_template()

    def test_parse_request_parameters(self):
        """
        Test the correct extraction of the resources from the request
        parameters.
        """
        parsed_request = machine.AutoInstallMachine.parse(REQUEST_PARAMETERS)
        resources = parsed_request["resources"]

        # Now we check that the resources were correctly allocated
        # according to the database specified in data.json
        self.assertIn("kvm054", resources["exclusive"])
        self.assertIn("CPC3LP55", resources["shared"])
        self.assertIn("CPC3", resources["shared"])
        self.assertNotIn("kvm054", resources["shared"])
    # test_parse_request_parameters()

    def test_unsupported_os(self):
        """
        Test the case when a unsupported OS is used
        """
        # Add an unsupported OS to the database
        unsupported_os = models.OperatingSystem(name="UnsupportedOS",
                                                type="another",
                                                major="1",
                                                minor="0",
                                                cmdline="foo",
                                                desc="Unsupported OS for Test")

        MANAGER.session.add(unsupported_os)
        MANAGER.session.commit()
        request = json.dumps({
            "system": "kvm054",
            "profile": "kvm_kvm054_install",
            "template": "RHEL7.2",
            "os": "UnsupportedOS"
        })
        with self.assertRaisesRegex(RuntimeError, "OS Unsupported"):
            machine.AutoInstallMachine(request)
        MANAGER.session.delete(unsupported_os)
    # test_unsupported_os()
# TestAutoInstallMachine
