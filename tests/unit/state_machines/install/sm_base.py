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
from tessia_engine.db.models import OperatingSystem
from tessia_engine.state_machines.install import sm_base
from tests.unit.state_machines.install import utils
from unittest import mock, TestCase
from unittest.mock import call, Mock, MagicMock, patch

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestSmBase(TestCase):
    """
    Class for unit testing the SmBase class.
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

        patcher = patch.object(sm_base, 'logging', autospec=True)
        self._mock_logging = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'jinja2', autospec=True)
        self._mock_jinja2 = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch("builtins.open", autospec=True)
        self._mock_open = patcher.start()
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

        # We do not patch the jsonschema in order to validate the expressions
        # that are used in the request.

        # Open the connection with the database so that it can be used in the
        # tests. Even for tests that does not directly use the session, we must
        # Create a session in order to fullfill the models with the query
        # object.
        self.session = MANAGER.session()

        # The following mock objectes are used to track the correct execution
        # of the install machine, assuring that each method was called.
        mock_get_kargs = Mock()
        mock_check_installation = Mock()
        mock_wait_install = Mock()
        self._mock_get_kargs = mock_get_kargs
        self._mock_check_installation = mock_check_installation
        self._mock_wait_install = mock_wait_install
        class Child(sm_base.SmBase):
            """
            Child class created to implement all the base class methods.
            With this class we want to execute the start method.
            """
            def __init__(self, *args):
                super().__init__(*args)

            def _get_kargs(self):
                mock_get_kargs()

            def check_installation(self):
                mock_check_installation()

            def wait_install(self):
                mock_wait_install()

        class NotImplementedChild(sm_base.SmBase):
            """
            Child class created to implement all the base class methods,
            but calling the original methods.
            """
            def __init__(self, *args):
                super().__init__(*args)

            def _get_kargs(self):
                super()._get_kargs()
            def check_installation(self):
                super().check_installation()
            def wait_install(self):
                super().wait_install()

        self._child_cls = Child
        self._ni_child_cls = NotImplementedChild
    # setUp()

    @staticmethod
    def _create_sm(sm_cls, os_name, profile_name, template_name):
        """
        Auxiliary method to create a Child state machine.
        """
        os_entry = utils.get_os(os_name)
        profile_entry = utils.get_profile(profile_name)
        template_entry = utils.get_template(template_name)

        return sm_cls(os_entry, profile_entry, template_entry)
    # _create_sm()

    def test_init_fails_cleanup(self):
        """
        Test the case the cleanup function fails.
        """
        self._mock_os.remove.side_effect = OSError
        mach = self._create_sm(self._child_cls, "rhel7.2",
                               "kvm054/kvm_kvm054_install", "RHEL7.2")
        with self.assertRaisesRegex(RuntimeError, "Unable to delete"):
            mach.start()
    # test_init()

    def test_machine_execution(self):
        """
        Test the correct initialization of the sm_class and the correct
        execution of the state machine.
        """
        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("RHEL7.2")
        system_entry = profile_entry.system_rel
        hyp_type = system_entry.type_rel.name.lower()
        repo_entry = os_entry.repository_rel[0]

        mach = self._child_cls(os_entry, profile_entry, template_entry)
        mach.start()

        mock_hyper_class = self._mocked_supported_platforms[hyp_type]
        # We do not assert the gateway dictionary since it will be tested in
        # the unittest of each implementation by testing the generated template
        mock_hyper_class.assert_called_with(
            profile_entry.hypervisor_profile_rel,
            profile_entry,
            os_entry,
            repo_entry,
            mock.ANY)

        mock_config_dict = self._mock_config.get_config.return_value
        autofile_name = '{}-{}'.format(system_entry.name, profile_entry.name)

        self._mock_urljoin.assert_called_with(
            mock_config_dict["install_machine"]["url"], autofile_name)

        self._mock_os.path.join.assert_called_with(
            mock_config_dict["install_machine"]["www_dir"], autofile_name)

        self._mock_jinja2.Template.assert_called_with(template_entry.content)
        mock_template = self._mock_jinja2.Template.return_value
        mock_template.render.assert_called_with(config=mock.ANY)
        autofile_content = mock_template.render.return_value

        # Assert the autofile is being written twice.
        calls = [call(autofile_content), call(autofile_content)]
        self._mock_open().__enter__.return_value.write.assert_has_calls(
            calls)

        # Assert that the methods implemented in the child class where
        # called in the execution of the Install Machine.
        self._mock_get_kargs.assert_called_with()
        self._mock_check_installation.assert_called_with()
        self._mock_wait_install.assert_called_with()

        mock_hyper_class.return_value.boot.assert_called_with(mock.ANY)
        mock_hyper_class.return_value.reboot.assert_called_with(profile_entry)

        self.assertEqual(profile_entry.operating_system_id, os_entry.id)
    # test_init()

    def test_not_supported_platform(self):
        """
        Test the case that the platform is not supported
        """
        profile = utils.get_profile("kvm054/kvm_kvm054_install")
        system_type = profile.system_rel.type_rel.name

        def restore_system_type():
            """
            Inner function to restore the name of the system type
            """
            profile.system_rel.type_rel.name = system_type
            self.session.commit()
        # restore_system_type()
        self.addCleanup(restore_system_type)

        profile.system_rel.type_rel.name = "unknown plat"

        self.session.commit()

        with self.assertRaisesRegex(RuntimeError, "Platform type"):
            self._create_sm(self._child_cls, "rhel7.2",
                            "kvm054/kvm_kvm054_install", "RHEL7.2")
    # test_not_supported_platform()

    def test_not_implemented_methods(self):
        """
        Test the methods that are not implemented in te base class.
        """
        mach = self._create_sm(self._ni_child_cls, "rhel7.2",
                               "kvm054/kvm_kvm054_install", "RHEL7.2")

        methods = ('_get_kargs', 'check_installation', 'wait_install')

        for method_name in methods:
            method = getattr(mach, method_name)
            self.assertRaises(NotImplementedError, method)
    # test_not_implemented_methods()

    def _sched_restore_profile_params(self, profile):
        """
        Restore the profile parameters after the test has finished.

        Args:
            profile (SystemProfile): an instance of a SystemProfile
        """
        profile_parameters = profile.parameters

        def restore_parameters():
            """
            Inner function to restore the profile parameters.
            """
            profile.parameters = profile_parameters
            self.session.commit()
        # restore_paremeters()

        self.addCleanup(restore_parameters)
    # _sched_restore_profile_params()

    def test_no_default_gateway(self):
        """
        Test the case that the profile does not have a default gateway
        defined.
        """

        profile = utils.get_profile("kvm054/kvm_kvm054_install")
        self._sched_restore_profile_params(profile)
        profile.parameters = {}
        self.session.commit()

        with self.assertRaisesRegex(RuntimeError, "No gateway"):
            self._create_sm(self._child_cls, "rhel7.2",
                            "kvm054/kvm_kvm054_install", "RHEL7.2")
    # test_no_default_gateway()

    def test_default_gateway_not_found(self):
        """
        Test the case that the default_gateway is not found.
        """
        profile = utils.get_profile("kvm054/kvm_kvm054_install")
        self._sched_restore_profile_params(profile)
        profile.parameters = {"gateway_iface": "non existent iface"}
        self.session.commit()

        with self.assertRaisesRegex(RuntimeError, "Gateway interface"):
            self._create_sm(self._child_cls, "rhel7.2",
                            "kvm054/kvm_kvm054_install", "RHEL7.2")
    # test_no_default_gateway()

    def test_no_repo_os(self):
        """
        Test the case that the operating system does not have a repo.
        """
        # Add an unsupported OS to the database
        unsupported_os = OperatingSystem(name="AnotherOS",
                                         type="another",
                                         major="1",
                                         minor="0",
                                         cmdline="foo",
                                         desc="AnotherOS without repo")
        self.session.add(unsupported_os)
        self.session.commit()
        self.addCleanup(self.session.delete, unsupported_os)

        with self.assertRaisesRegex(RuntimeError, "No repository"):
            self._create_sm(self._child_cls, "AnotherOS",
                            "kvm054/kvm_kvm054_install", "RHEL7.2")
    # test_no_repo_os()

# TestSmBase
