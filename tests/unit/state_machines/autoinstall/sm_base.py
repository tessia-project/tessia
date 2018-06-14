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
from contextlib import contextmanager
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import OperatingSystem
from tessia.server.state_machines.autoinstall import sm_base
from tests.unit.state_machines.autoinstall import utils
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
        cls.db = utils.setup_dbunit()
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

        patcher = patch.object(sm_base, 'SshClient', autospec=True)
        self._mock_ssh_client = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'sleep', autospec=True)
        self._mock_sleep = patcher.start()
        self.addCleanup(patcher.stop)

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

        # We do not patch the jsonschema in order to validate the expressions
        # that are used in the request.

        # The following mock objects are used to track the correct execution
        # of the install machine, assuring that each method was called.
        mock_wait_install = Mock()
        self._mock_wait_install = mock_wait_install
        class Child(sm_base.SmBase):
            """
            Child class created to implement all the base class methods.
            With this class we want to execute the start method.
            """
            DISTRO_TYPE = 'redhat'

            def __init__(self, *args):
                super().__init__(*args)

            def wait_install(self):
                mock_wait_install()

        class NotImplementedChild(sm_base.SmBase):
            """
            Child class created to implement all the base class methods,
            but calling the original methods.
            """
            DISTRO_TYPE = 'redhat'

            def __init__(self, *args):
                super().__init__(*args)

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

    def test_init_fails_cleanup(self):
        """
        Test the case the cleanup function fails.
        """
        self._mock_os.remove.side_effect = OSError
        mach = self._create_sm(self._child_cls, "rhel7.2",
                               "kvm054/kvm_kvm054_install", "rhel7-default")
        mock_client = self._mock_ssh_client.return_value
        mock_client.open_shell.return_value.run.return_value = 0, ""
        with self.assertRaisesRegex(RuntimeError, "Unable to delete"):
            mach.start()
    # test_init()

    def test_invalid_config(self):
        """
        Test scenarios where the profile or system has an invalid configuration
        which prevents the installation to occur.
        """
        os_obj = utils.get_os("rhel7.2")
        profile_obj = utils.get_profile("CPC3LP55/default_CPC3LP55")
        system_obj = profile_obj.system_rel
        template_obj = utils.get_template("rhel7-default")

        # system has no hypervisor defined
        error_msg = ('System {} cannot be installed because it has no '
                     'hypervisor defined'.format(system_obj.name))
        with self._mock_db_obj(system_obj, 'hypervisor_id', None):
            with self.assertRaisesRegex(ValueError, error_msg):
                self._child_cls(os_obj, profile_obj, template_obj)

        # hypervisor has no default profile
        error_msg = (
            'Hypervisor {} of system {} has no default profile defined'
            .format(system_obj.hypervisor_rel.name, system_obj.name))
        hyp_prof_obj = profile_obj.hypervisor_profile_rel
        with self._mock_db_obj(profile_obj, 'hypervisor_profile_id', None):
            with self._mock_db_obj(hyp_prof_obj, 'default', False):
                with self.assertRaisesRegex(ValueError, error_msg):
                    self._child_cls(os_obj, profile_obj, template_obj)

    # test_invalid_config()

    def test_machine_execution(self):
        """
        Test the correct initialization of the sm_class and the correct
        execution of the state machine.
        """
        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("rhel7-default")
        system_entry = profile_entry.system_rel
        hyp_type = system_entry.type_rel.name.lower()
        repo_entry = os_entry.repository_rel[0]
        mock_client = self._mock_ssh_client.return_value
        mock_client.open_shell.return_value.run.return_value = 0, ""

        # cmdline file mock
        cmdline_content = self._mock_open(
            ).__enter__.return_value.read.return_value

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

        autofile_url = '{}/{}'.format(
            mock_config_dict["auto_install"]["url"], autofile_name)
        self.assertEqual(mach._autofile_url, autofile_url)

        # verify that the cmdline and auto templates were rendered
        self._mock_jinja2.Template.assert_has_calls([
            call(template_entry.content),
            call().render(config=mock.ANY),
            call(cmdline_content),
            call().render(config=mock.ANY),
        ])

        # Assert the autofile is being written twice.
        mock_template = self._mock_jinja2.Template.return_value
        autofile_content = mock_template.render.return_value
        self._mock_os.path.join.assert_called_with(
            mock_config_dict["auto_install"]["dir"], autofile_name)
        calls = [call(autofile_content), call(autofile_content)]
        self._mock_open().__enter__.return_value.write.assert_has_calls(
            calls)

        # Assert that the methods implemented in the child class were
        # called in the execution of the Install Machine.
        self._mock_wait_install.assert_called_with()
        self._mock_checker.assert_called_with(
            profile_entry, os_entry, permissive=True)

        mock_hyper_class.return_value.boot.assert_called_with(mock.ANY)
        mock_hyper_class.return_value.reboot.assert_called_with(profile_entry)

        self.assertEqual(profile_entry.operating_system_id, os_entry.id)
    # test_machine_execution()

    def test_machine_execution_no_hyp_profile(self):
        """
        Test the case where the system activation profile does not have a
        hypervisor profile defined. In this case the hypervisor's default
        profile should be used.
        """
        # collect necessary objects
        os_obj = utils.get_os("rhel7.2")
        profile_obj = utils.get_profile("CPC3LP55/default_CPC3LP55")
        hyp_prof_obj = utils.get_profile("CPC3/default CPC3")
        template_obj = utils.get_template("rhel7-default")
        system_obj = profile_obj.system_rel
        hyp_type = system_obj.type_rel.name.lower()
        repo_obj = os_obj.repository_rel[0]
        mock_client = self._mock_ssh_client.return_value
        mock_client.open_shell.return_value.run.return_value = 0, ""

        # cmdline file mock
        cmdline_content = self._mock_open(
            ).__enter__.return_value.read.return_value

        with self._mock_db_obj(profile_obj, 'hypervisor_profile_id', None):
            mach = self._child_cls(os_obj, profile_obj, template_obj)
            mach.start()

        # We do not assert the gateway dictionary since it will be tested in
        # the unittest of each implementation by testing the generated template
        mock_hyper_class = self._mocked_supported_platforms[hyp_type]
        mock_hyper_class.assert_called_with(
            # default hypervisor profile should be used
            hyp_prof_obj,
            profile_obj,
            os_obj,
            repo_obj,
            mock.ANY)

        # validate correct creation of template
        # verify that the cmdline and auto templates were rendered
        self._mock_jinja2.Template.assert_has_calls([
            call(template_obj.content),
            call().render(config=mock.ANY),
            call(cmdline_content),
            call().render(config=mock.ANY),
        ])

        # Assert the autofile is being written twice.
        mock_template = self._mock_jinja2.Template.return_value
        autofile_content = mock_template.render.return_value
        mock_config_dict = self._mock_config.get_config.return_value
        autofile_name = '{}-{}'.format(system_obj.name, profile_obj.name)
        self._mock_os.path.join.assert_called_with(
            mock_config_dict["auto_install"]["dir"], autofile_name)
        calls = [call(autofile_content), call(autofile_content)]
        self._mock_open().__enter__.return_value.write.assert_has_calls(
            calls)

        # Assert that the methods implemented in the child class were
        # called in the execution of the Install Machine.
        self._mock_wait_install.assert_called_with()
        self._mock_checker.assert_called_with(
            profile_obj, os_obj, permissive=True)

        mock_hyper_class.return_value.boot.assert_called_with(mock.ANY)
        mock_hyper_class.return_value.reboot.assert_called_with(profile_obj)

        self.assertEqual(profile_obj.operating_system_id, os_obj.id)
    # test_machine_execution_no_hyp_profile()

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
            MANAGER.session.commit()
        # restore_system_type()
        self.addCleanup(restore_system_type)

        profile.system_rel.type_rel.name = "unknown plat"

        MANAGER.session.commit()

        with self.assertRaisesRegex(RuntimeError, "Platform type"):
            self._create_sm(self._child_cls, "rhel7.2",
                            "kvm054/kvm_kvm054_install", "rhel7-default")
    # test_not_supported_platform()

    def test_not_implemented_methods(self):
        """
        Test the methods that are not implemented in te base class.
        """
        mach = self._create_sm(self._ni_child_cls, "rhel7.2",
                               "kvm054/kvm_kvm054_install", "rhel7-default")

        methods = ('wait_install',)

        for method_name in methods:
            method = getattr(mach, method_name)
            self.assertRaises(NotImplementedError, method)
    # test_not_implemented_methods()

    def test_check_install_error(self):
        """
        Check the case an error occur when testing the installed system
        after the installation has successfully finished.
        """
        mock_shell = self._mock_ssh_client.return_value.open_shell.return_value
        mock_shell.run.return_value = (-1, "Some text")
        mach = self._create_sm(self._child_cls, "rhel7.2",
                               "kvm054/kvm_kvm054_install", "rhel7-default")
        with self.assertRaisesRegex(RuntimeError, "Error while checking"):
            mach.start()
    # test_check_install_error()

    def test_check_install_timeout(self):
        """
        Exercise time out when the post install library tries to connect to the
        target system.
        """
        # mock shell command in check_installation
        mock_client = self._mock_ssh_client.return_value
        mock_client.open_shell.return_value.run.return_value = 0, ""

        # mock post install failure to connect
        post_install_obj = self._mock_checker.return_value
        post_install_obj.verify.side_effect = ConnectionError()
        mach = self._create_sm(self._child_cls, "rhel7.2",
                               "CPC3LP55/default_CPC3LP55", "rhel7-default")
        error_msg = 'Timeout occurred while trying to connect to target system'
        with self.assertRaisesRegex(ConnectionError, error_msg):
            mach.start()
    # test_check_install_timeout()

    def test_no_ssh_connection_after_installation(self):
        """
        Check the case that there is no ssh connection after the target system
        reboots.
        """
        self._mock_ssh_client.return_value.login.side_effect = ConnectionError
        mach = self._create_sm(self._child_cls, "rhel7.2",
                               "kvm054/kvm_kvm054_install", "rhel7-default")
        with self.assertRaisesRegex(ConnectionError, "Timeout occurred"):
            mach.start()
    # test_check_install_error()

    def test_no_repo_os(self):
        """
        Test the case that the operating system does not have a repo.
        """
        # Add an unsupported OS to the database
        unsupported_os = OperatingSystem(name="AnotherOS",
                                         type="another",
                                         major="1",
                                         minor="0",
                                         template=None,
                                         pretty_name="AnotherOS without repo")
        MANAGER.session.add(unsupported_os)
        MANAGER.session.commit()
        self.addCleanup(MANAGER.session.delete, unsupported_os)

        with self.assertRaisesRegex(RuntimeError, "No repository"):
            self._create_sm(self._child_cls, "AnotherOS",
                            "kvm054/kvm_kvm054_install", "rhel7-default")
    # test_no_repo_os()

    def test_multi_root(self):
        """
        Test the case where a system profile has multiple root disks defined.
        """
        profile_obj = utils.get_profile("CPC3LP55/default_CPC3LP55")
        mock_table = {
            "table": [
                {
                    "fs": "ext4",
                    "mo": None,
                    "mp": "/",
                    "size": 6000,
                    "type": "primary"
                }
            ],
            "type": "msdos"
        }
        first_disk = profile_obj.storage_volumes_rel[0]
        second_disk = profile_obj.storage_volumes_rel[1]
        with self._mock_db_obj(first_disk, 'part_table', mock_table):
            with self._mock_db_obj(second_disk, 'part_table', mock_table):
                mach = self._create_sm(
                    self._child_cls, "rhel7.2", "CPC3LP55/default_CPC3LP55",
                    "rhel7-default")
                with self.assertRaisesRegex(
                    ValueError, "multiple root disks defined"):
                    mach.start()
    # test_multi_root()

    def test_no_root(self):
        """
        Test the case where a system profile has no root disks defined.
        """
        profile_obj = utils.get_profile("CPC3LP55/default_CPC3LP55")
        mock_table = {
            "table": [
                {
                    "fs": "ext4",
                    "mo": None,
                    "mp": "/home",
                    "size": 6000,
                    "type": "primary"
                }
            ],
            "type": "msdos"
        }
        first_disk = profile_obj.storage_volumes_rel[0]
        with self._mock_db_obj(first_disk, 'part_table', mock_table):
            mach = self._create_sm(
                self._child_cls, "rhel7.2", "CPC3LP55/default_CPC3LP55",
                "rhel7-default")
            with self.assertRaisesRegex(ValueError, "no root disk defined"):
                mach.start()
    # test_no_root()
# TestSmBase
