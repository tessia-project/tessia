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
from tessia.server.db.models import OperatingSystem, Repository
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

        patcher = patch.object(sm_base, 'gethostbyname', autospec=True)
        self._mock_gethostbyname = patcher.start()
        self._mock_gethostbyname.side_effect = Exception()
        self.addCleanup(patcher.stop)

        patcher = patch.object(sm_base, 'SshClient', autospec=True)
        self._mock_ssh_client = patcher.start()
        # mock it for the common case
        mock_client = self._mock_ssh_client.return_value
        mock_client.open_shell.return_value.run.return_value = 0, ""
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

    def _create_repos(self, repo_list):
        """
        Create the repository entries in the db and return the corresponding
        dictionary in the format expected for validation.
        """
        repos_ret = {'objs': [], 'dicts': [], 'names': []}
        for repo_dict in repo_list:
            repo_obj = Repository(
                name=repo_dict['name'],
                desc=repo_dict['name'],
                initrd=repo_dict.get('initrd'),
                kernel=repo_dict.get('kernel'),
                install_image=repo_dict.get('install_image'),
                operating_system=repo_dict.get('os'),
                url=repo_dict['url'],
                owner='admin', project='Admins', modifier='admin'
            )
            MANAGER.session.add(repo_obj)
            MANAGER.session.commit()
            self.addCleanup(MANAGER.session.delete, repo_obj)

            repos_ret['objs'].append(repo_obj)
            repos_ret['dicts'].append({
                'url': repo_obj.url,
                'name': repo_obj.name,
                'desc': repo_obj.desc,
                'os': repo_obj.operating_system,
                'install_image': None,
            })
            repos_ret['names'].append(repo_obj.name)

        return repos_ret
    # _create_repos()

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
        with self.assertRaisesRegex(RuntimeError, "Unable to delete"):
            mach.start()
            mach.cleanup()
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
        profile_name = "CPC3LP55/default_CPC3LP55"
        profile_entry = utils.get_profile(profile_name)
        template_entry = utils.get_template("rhel7-default")
        system_entry = profile_entry.system_rel
        hyp_type = system_entry.type_rel.name.lower()
        repo_entry = os_entry.repository_rel[0]

        # store last modified time before system power changes
        system_last_modified = system_entry.modified

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
            mock_config_dict.get("auto_install")["url"], autofile_name)
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
            mock_config_dict.get("auto_install")["dir"], autofile_name)
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

        # validate that system modified time is updated
        updated_system_entry = utils.get_profile(profile_name).system_rel
        self.assertGreater(updated_system_entry.modified,
                           system_last_modified,
                           'System modified time is updated')

        self.assertEqual(profile_entry.operating_system_id, os_entry.id)
    # test_machine_execution()

    def test_machine_execution_custom_kargs(self):
        """
        Test usage of custom kernel cmdline arguments specified in the
        activation profile for the Linux installer.
        """
        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("rhel7-default")
        system_entry = profile_entry.system_rel
        hyp_type = system_entry.type_rel.name.lower()

        test_kargs = {
            'linux-kargs-installer': 'novnc zfcp.allow_lun_scan=0',
        }
        # expected cmdline content
        cmdline_template = self._mock_open(
        ).__enter__.return_value.read.return_value = (
            'ro ramdisk_size=50000 zfcp.allow_lun_scan=1')
        self._mock_jinja2.Template.return_value.render.return_value = (
            cmdline_template)
        cmdline_content = 'ro ramdisk_size=50000 zfcp.allow_lun_scan=0 novnc'

        # execute machine
        with self._mock_db_obj(profile_entry, 'parameters', test_kargs):
            mach = self._child_cls(os_entry, profile_entry, template_entry)
            mach.start()

        # validate behavior
        self._mock_jinja2.Template.assert_has_calls([
            call(template_entry.content),
            call().render(config=mock.ANY),
            call(cmdline_template),
            call().render(config=mock.ANY),
        ])
        mock_hyper_class = self._mocked_supported_platforms[hyp_type]
        mock_hyper_class.return_value.boot.assert_called_with(cmdline_content)

    def test_machine_execution_custom_repo_install(self):
        """
        Test usage of custom repositories specified by the user when an install
        repo is included.
        """
        repos = [{
            'name': "rhel7.2-custom",
            'initrd': '/images/initrd.img',
            'kernel': '/images/kernel.img',
            'os': "rhel7.2",
            'url': "http://_installserver.z",
            'install_image': None,
        }, {
            'name': "other-repo",
            'url': "http://_somepackages.z",
            'install_image': None,
        }]
        repos = self._create_repos(repos)

        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("rhel7-default")
        system_entry = profile_entry.system_rel
        hyp_type = system_entry.type_rel.name.lower()

        # execute machine
        mach = self._child_cls(
            os_entry, profile_entry, template_entry, repos['names'])
        mach.start()

        # validate behavior
        mock_hyper_class = self._mocked_supported_platforms[hyp_type]
        mock_hyper_class.assert_called_with(
            profile_entry.hypervisor_profile_rel,
            profile_entry,
            os_entry,
            repos['objs'][0],
            mock.ANY)

        # verify that the custom os repo is the first on the list and the
        # additional repo was also included
        try:
            info_dict = (self._mock_jinja2.Template.return_value.render.
                         call_args[1]['config'])
        except Exception as exc:
            raise AssertionError(
                'Template.render() was not executed correctly') from exc
        self.assertEqual(repos['dicts'], info_dict['repos'])
    # test_machine_execution_custom_repo_install()

    def test_machine_execution_custom_repo_no_install(self):
        """
        Test usage of custom repositories specified by the user when only
        additional repositories are included.
        """
        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("rhel7-default")
        def_repo_entry = os_entry.repository_rel[0]
        system_entry = profile_entry.system_rel
        hyp_type = system_entry.type_rel.name.lower()

        repos = [{
            'name': "other-repo",
            'url': "http://_somepackages.z",
        }, {
            'name': "other-repo2",
            'url': "http://_somepackages2.z",
        }]
        repos = self._create_repos(repos)
        # also add repos with urls, repos don't exist in db
        for scheme in ('http', 'https', 'ftp', 'file'):
            url = '{}://_urlrepo1.x'.format(scheme)
            repos['names'].append(url)
            repos['dicts'].append({
                'name': '{}____urlrepo1_x'.format(scheme),
                'desc': 'User defined repo {}____urlrepo1_x'.format(scheme),
                'url': url,
                'os': None,
                'install_image': None,
            })
        # include the default os repository in the expected result
        def_repo_dict = {
            'url': def_repo_entry.url,
            'name': def_repo_entry.name,
            'desc': def_repo_entry.desc,
            'os': def_repo_entry.operating_system,
            'install_image': None,
        }
        if not def_repo_dict['desc']:
            def_repo_dict['desc'] = def_repo_dict['name']
        repos['dicts'].insert(0, def_repo_dict)

        # execute machine
        mach = self._child_cls(
            os_entry, profile_entry, template_entry, repos['names'])
        mach.start()

        # validate behavior
        mock_hyper_class = self._mocked_supported_platforms[hyp_type]
        mock_hyper_class.assert_called_with(
            profile_entry.hypervisor_profile_rel,
            profile_entry,
            os_entry,
            def_repo_entry,
            mock.ANY)

        # verify that the custom os repo is the first on the list and the
        # additional repo was also included
        try:
            info_dict = (self._mock_jinja2.Template.return_value.render.
                         call_args[1]['config'])
        except Exception as exc:
            raise AssertionError(
                'Template.render() was not executed correctly') from exc
        self.assertEqual(repos['dicts'], info_dict['repos'])

        # negative test - try to specify a repo name which does not exist in db
        error_msg = (
            "Repository <some_wrong_repo> specified by user does not exist")
        with self.assertRaisesRegex(ValueError, error_msg):
            mach = self._child_cls(
                os_entry, profile_entry, template_entry, ['some_wrong_repo'])

        # negative test - try to specify a repo with invalid url
        error_msg = (
            r'Repository <http://_wrong\[aa.z> specified by user is not a '
            'valid URL')
        with self.assertRaisesRegex(ValueError, error_msg):
            self._child_cls(os_entry, profile_entry, template_entry,
                            ['http://_wrong[aa.z'])
    # test_machine_execution_custom_repo_no_install()

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
            mock_config_dict.get("auto_install")["dir"], autofile_name)
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

    def test_machine_execution_same_subnet(self):
        """
        Test the case where multiple repositories for the same os exists and
        the tool chooses the one in the same subnet as the system to be
        installed.
        """
        # create multiple install repo entries
        repos = []
        for index in range(0, 5):
            repos.append({
                'name': "rhel7.2-repo{}".format(index),
                'initrd': '/images/initrd.img',
                'kernel': '/images/kernel.img',
                'os': "rhel7.2",
                'url': "http://_repo{}.z".format(index),
                'install_image': None,
            })
        repos = self._create_repos(repos)

        # pretend third repo is in same subnet
        def mock_gethostbyname(hostname):
            """
            Mock the process of resolving hostnames to ip addreses
            """
            # pretend this repo is in the subnet inside the range of
            # 'external osa' iface, so that it gets chosen as the install
            # repository in the test
            if hostname == repos['objs'][2].url[7:]:
                return '192.168.160.10'
            # subnet outside the range of the system's ifaces
            return '192.168.0.50'
        # mock_gethostbyname
        self._mock_gethostbyname.side_effect = mock_gethostbyname

        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("rhel7-default")
        system_entry = profile_entry.system_rel
        hyp_type = system_entry.type_rel.name.lower()

        # execute machine
        mach = self._child_cls(os_entry, profile_entry, template_entry)
        mach.start()

        # validate behavior
        mock_hyper_class = self._mocked_supported_platforms[hyp_type]
        mock_hyper_class.assert_called_with(
            profile_entry.hypervisor_profile_rel,
            profile_entry,
            os_entry,
            repos['objs'][2],
            mock.ANY)

        # verify that the third install repo was used
        try:
            info_dict = (self._mock_jinja2.Template.return_value.render.
                         call_args[1]['config'])
        except Exception as exc:
            raise AssertionError(
                'Template.render() was not executed correctly') from exc
        self.assertEqual([repos['dicts'][2]], info_dict['repos'])
    # test_machine_execution_same_subnet()

    def test_machine_execution_same_subnet_custom_repo(self):
        """
        Test the case where multiple repositories for the same OS exists, the
        tool chooses the one in the same subnet as the system to be
        installed and the user specified an additional package repository.
        """
        # create multiple install repo entries
        repos = []
        for index in range(0, 5):
            repos.append({
                'name': "rhel7.2-repo{}".format(index),
                'initrd': '/images/initrd.img',
                'kernel': '/images/kernel.img',
                'os': "rhel7.2",
                'url': "http://_repo{}.z".format(index),
                'install_image': None,
            })
        repos.append({
            'name': "other-repo2",
            'url': "http://_somepackages2.z",
            'install_image': None,
        })
        repos = self._create_repos(repos)

        # pretend third repo is in same subnet
        def mock_gethostbyname(hostname):
            """
            Mock the process of resolving hostnames to ip addreses
            """
            # pretend this repo is in the subnet inside the range of
            # 'external osa' iface, so that it gets chosen as the install
            # repository in the test
            if hostname == repos['objs'][2].url[7:]:
                return '192.168.160.10'
            # subnet outside the range of the system's ifaces
            return '192.168.0.50'
        # mock_gethostbyname
        self._mock_gethostbyname.side_effect = mock_gethostbyname

        os_entry = utils.get_os("rhel7.2")
        profile_entry = utils.get_profile("CPC3LP55/default_CPC3LP55")
        template_entry = utils.get_template("rhel7-default")
        system_entry = profile_entry.system_rel
        hyp_type = system_entry.type_rel.name.lower()

        # execute machine
        mach = self._child_cls(os_entry, profile_entry, template_entry,
                               [repos['names'][-1]])
        mach.start()

        # validate behavior
        mock_hyper_class = self._mocked_supported_platforms[hyp_type]
        mock_hyper_class.assert_called_with(
            profile_entry.hypervisor_profile_rel,
            profile_entry,
            os_entry,
            repos['objs'][2],
            mock.ANY)

        # verify that the third install repo was used
        try:
            info_dict = (self._mock_jinja2.Template.return_value.render.
                         call_args[1]['config'])
        except Exception as exc:
            raise AssertionError(
                'Template.render() was not executed correctly') from exc
        self.assertEqual(
            # expected install repo in same subnet and package repo
            [repos['dicts'][2], repos['dicts'][-1]], info_dict['repos'])
    # test_machine_execution_same_subnet()

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

        with self.assertRaisesRegex(RuntimeError, "No install repository"):
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
        root_disk = None
        for disk in profile_obj.storage_volumes_rel:
            for part in disk.part_table['table']:
                if part['mp'] == '/':
                    root_disk = disk
                    break
        if not root_disk:
            raise ValueError('Could not find root disk for test')
        with self._mock_db_obj(root_disk, 'part_table', mock_table):
            mach = self._create_sm(
                self._child_cls, "rhel7.2", "CPC3LP55/default_CPC3LP55",
                "rhel7-default")
            with self.assertRaisesRegex(ValueError, "no root disk defined"):
                mach.start()
    # test_no_root()
# TestSmBase
