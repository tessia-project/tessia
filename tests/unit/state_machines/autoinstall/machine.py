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
from contextlib import contextmanager
from copy import deepcopy
from tessia.server.db import models
from tessia.server.db.connection import MANAGER
from tessia.server.state_machines import base
from tessia.server.state_machines.autoinstall import machine
from tests.unit.config import EnvConfig
from tests.unit.state_machines.autoinstall import utils
from unittest.mock import patch
from unittest import TestCase
from unittest.mock import Mock

import json

#
# CONSTANTS AND DEFINITIONS
#
DEFAULT_CONFIG = {
    'log': {
        'version': 1,
        'handlers': {}
    }
}
REQUEST_PARAMETERS = json.dumps({
    "system": "kvm054",
    "profile": "kvm_kvm054_install",
    "os": "rhel7.2"
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
        cls.db = utils.setup_dbunit()
        cls._env_config = EnvConfig()
        cls._env_config.start(DEFAULT_CONFIG)
    # setUpClass()

    @classmethod
    def tearDownClass(cls):
        # restore original config
        cls._env_config.stop()
    # tearDownClass()

    def setUp(self):
        """
        Setup all the mocks used for the execution of the tests.
        """
        patcher = patch.object(base, 'CONF', autospec=True)
        self._mock_conf = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(base, 'sys', autospec=True)
        self._mock_sys = patcher.start()
        self._mock_sys_tblimit = 10
        self._mock_sys.tracebacklimit = self._mock_sys_tblimit
        self.addCleanup(patcher.stop)

        self._mock_sm_anaconda = Mock(spec_set=machine.SmAnaconda)
        self._mock_sm_autoyast = Mock(spec_set=machine.SmAutoyast)

        mocked_supported_distros = {
            'redhat': self._mock_sm_anaconda,
            'suse': self._mock_sm_autoyast
        }

        patcher_dict = patch.dict(machine.SUPPORTED_TYPES,
                                  values=mocked_supported_distros)
        patcher_dict.start()
        self.addCleanup(patcher_dict.stop)

        patcher = patch.object(machine, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)
        mock_logging.getLogger.return_value = Mock(
            spec=['warning', 'error', 'debug', 'info'])

        # We do not patch the jsonschema in order to validate the expressions
        # that are used in the request.
    # setUp()

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
            "profile" and "template" are optional.
        """
        mach = machine.AutoInstallMachine(parameters)
        # start also calls cleanup
        mach.start()
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
            "os": "rhel7.2"
        })

        self._perform_test_init(request)
    # test_init_default_profile()

    def test_init_with_verbosity(self):
        """
        Test the correct initialization of the AutoInstallMachine when output
        verbosity is specified.
        """
        request = {
            "system": "kvm054",
            "os": "rhel7.2",
            "verbosity": "DEBUG",
        }

        self._perform_test_init(json.dumps(request))

        self._mock_conf.log_config.assert_called_with(
            conf=machine.AutoInstallMachine._LOG_CONFIG,
            log_level=request['verbosity'])
        self.assertEqual(self._mock_sys.tracebacklimit, self._mock_sys_tblimit,
                         'sys.tracebacklimit was altered')
    # test_init_default_profile()

    def test_invalid_fcp_parameters(self):
        """
        Test the case when a required FCP parameter is missing
        """
        # fetch correct FCP parameters from db
        profile = models.SystemProfile.query.filter_by(
            name='kvm_kvm054_install', system='kvm054').one()
        volumes = profile.storage_volumes_rel

        # distort correct FCP parameters and check result
        test_vol = volumes[0]
        orig_specs = test_vol.specs
        # for some reason sqlalchemy does not detect the object as dirty if we
        # change the dictionary directly, so we force a copy here
        test_vol.specs = deepcopy(test_vol.specs)
        test_vol.specs['adapters'][0].pop('devno')
        MANAGER.session.add(test_vol)
        MANAGER.session.commit()
        error_re = (
            'failed to validate FCP parameters .* of volume {}: '.format(
                test_vol.volume_id))
        self.assertRaisesRegex(
            ValueError,
            error_re,
            machine.AutoInstallMachine.parse,
            REQUEST_PARAMETERS)

        test_vol.specs = orig_specs
        MANAGER.session.add(test_vol)
        MANAGER.session.commit()
    # test_invalid_fcp_parameters()

    def test_invalid_request_parameters(self):
        """
        Test the case that the state machine receives an invalid
        request parameters.
        """
        # Invalid request parameter with one missing property
        invalid_request_parameters1 = '{"profile": "kvm_kvm054_install"}'
        # Invalid request with additional parameter
        invalid_request_parameters2 = """{"profile": "kvm_kvm054_install",
        "os": "rhel7.2", "other_parameters": "value"}
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
        "os":
        """
        with self.assertRaises(SyntaxError):
            machine.AutoInstallMachine.parse(malformed_request_parameters)
    # test_malformed_request_parameters()

    def test_missing_part_table(self):
        """
        Test the case when a volume has no partition table defined
        """
        # fetch correct FCP parameters from db
        profile = models.SystemProfile.query.filter_by(
            name='kvm_kvm054_install', system='kvm054').one()
        volumes = profile.storage_volumes_rel

        # remove partition table and check result
        test_vol = volumes[0]
        orig_table = test_vol.part_table
        # for some reason sqlalchemy does not detect the object as dirty if we
        # change the dictionary directly, so we force a copy here
        test_vol.part_table = deepcopy(test_vol.part_table)
        test_vol.part_table.pop('table')
        MANAGER.session.add(test_vol)
        MANAGER.session.commit()
        self._perform_test_init(REQUEST_PARAMETERS)

        test_vol.part_table = orig_table
        MANAGER.session.add(test_vol)
        MANAGER.session.commit()
    # test_missing_part_table()

    def test_nonexistent_os(self):
        """
        Test the case that an operating system does not exist in the database.
        """
        request = json.dumps({
            "system": "kvm054",
            "profile": "kvm_kvm054_install",
            "template": "rhel7-default",
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
            "template": "Nonono",
            "os": "rhel7.2"
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

    def test_parse_no_hyp_profile(self):
        """
        Test the case where the system activation profile does not have a
        hypervisor profile defined. In this case the hypervisor's default
        profile should be used and the parse should succeed.
        """
        prof_obj = utils.get_profile("kvm054/kvm_kvm054_install")

        with self._mock_db_obj(prof_obj, 'hypervisor_profile_id', None):
            machine.AutoInstallMachine.parse(REQUEST_PARAMETERS)
    # test_parse_no_hyp_profile()

    def test_system_no_iface(self):
        """
        Confirm that exception is raised when a system without any interface
        attached is provided for installation.
        """
        request = json.dumps({
            'system': 'CPC3LP55',
            'profile': 'default_CPC3LP55_no_iface',
            'os': 'ubuntu16.04.1',
        })

        error_msg = 'No network interface attached to perform installation'
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.AutoInstallMachine.parse(request)
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.AutoInstallMachine(request)
    # test_system_no_iface()

    def test_system_no_hypervisor(self):
        """
        Confirm that parse fails when a system without hypervisor defined is
        provided for installation.
        """
        prof_obj = utils.get_profile("kvm054/kvm_kvm054_install")

        error_msg = ('System {} cannot be installed because it has no '
                     'hypervisor defined'.format(prof_obj.system_rel.name))
        with self._mock_db_obj(prof_obj.system_rel, 'hypervisor_id', None):
            with self.assertRaisesRegex(ValueError, error_msg):
                machine.AutoInstallMachine.parse(REQUEST_PARAMETERS)
    # test_system_no_hypervisor()

    def test_system_invalid_gw_iface(self):
        """
        Confirm that an exception is raised for the cases where a system has
        an invalid gateway interface defined
        """
        system_name = 'CPC3LP55'
        prof_name = 'default_CPC3LP55_SCSI'
        prof_obj = utils.get_profile("{}/{}".format(system_name, prof_name))
        iface_obj = prof_obj.system_ifaces_rel[0]
        request = json.dumps({
            'system': system_name,
            'profile': prof_name,
            'os': 'ubuntu16.04.1',
        })

        # subnet has no gateway route
        error_msg = (
            "Subnet <{}> of the gateway network interface <{}> has no gateway "
            "route defined".format(iface_obj.ip_address_rel.subnet_rel.name,
                                   iface_obj.name))
        with self._mock_db_obj(
                iface_obj.ip_address_rel.subnet_rel, 'gateway', None):
            with self.assertRaisesRegex(ValueError, error_msg):
                machine.AutoInstallMachine.parse(request)
            with self.assertRaisesRegex(ValueError, error_msg):
                machine.AutoInstallMachine(request)

        # gateway iface has no IP address
        error_msg = (
            "Gateway network interface <{}> has no IP address assigned"
            .format(iface_obj.name))
        with self._mock_db_obj(iface_obj, 'ip_address_id', None):
            with self.assertRaisesRegex(ValueError, error_msg):
                machine.AutoInstallMachine.parse(request)
            with self.assertRaisesRegex(ValueError, error_msg):
                machine.AutoInstallMachine(request)
    # test_system_gw_iface_no_gateway()

    def test_unsupported_os(self):
        """
        Test the case when a unsupported OS is used
        """
        # Add an unsupported OS to the database
        unsupported_os = models.OperatingSystem(
            name="UnsupportedOS", type="another", major="1", minor="0",
            pretty_name="Unsupported OS for Test")

        MANAGER.session.add(unsupported_os)
        MANAGER.session.commit()
        request = json.dumps({
            "system": "kvm054",
            "profile": "kvm_kvm054_install",
            "template": "rhel7-default",
            "os": "UnsupportedOS"
        })
        error_msg = "OS type 'another' is not supported for installation"
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.AutoInstallMachine.parse(request)
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.AutoInstallMachine(request)
        MANAGER.session.delete(unsupported_os)
    # test_unsupported_os()
# TestAutoInstallMachine
