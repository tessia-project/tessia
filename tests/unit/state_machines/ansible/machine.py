# Copyright 2018 IBM Corp.
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
Unit test for the ansible machine.
"""

from tessia.server.state_machines.ansible import machine
from tessia.server.db.models import System, SystemProfile
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest import mock

import json
import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestAnsibleMachine(TestCase):
    """
    Unit testing for the AnsibleMachine class.
    """
    @classmethod
    def setUpClass(cls):
        """
        Called once to create the db content for this test.
        """
        DbUnit.create_db()
        sample_file = '{}/data.json'.format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(sample_file, 'r') as sample_fd:
            data = sample_fd.read()
        DbUnit.create_entry(json.loads(data))
        cls.db = DbUnit
    # setUpClass()

    def setUp(self):
        """
        Called before each test to set up the necessary mocks.
        """
        # mocks for subprocess
        patcher = mock.patch.object(machine, 'subprocess', autospec=True)
        self._mock_subproc = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_subproc.CalledProcessError.side_effect = Exception()
        self._mock_proc = mock.Mock(spec=['stdout', 'poll', 'returncode'])
        self._mock_subproc.Popen.return_value = self._mock_proc
        # prepare the playbook exec for the usual case (read two lines then
        # process ends)
        self._mock_proc.stdout.readline.side_effect = [
            'fake_output1\n', None, 'fake_output2\n', None]
        self._mock_proc.poll.side_effect = [None, 500]
        self._mock_proc.returncode = 0

        # mock for autoinstall machine
        patcher = mock.patch.object(
            machine, 'AutoInstallMachine', autospec=True)
        self._mock_autoinst_cls = patcher.start()
        self._mock_autoinst_obj = self._mock_autoinst_cls.return_value
        self.addCleanup(patcher.stop)

        # mock for request library
        patcher = mock.patch.object(machine, 'requests', autospec=True)
        self._mock_reqs_mod = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_reqs_mod_get_resp = self._mock_reqs_mod.get.return_value
        # prepare the response for the usual case
        self._mock_reqs_mod_get_resp.headers = {
            'content-length': (machine.MAX_REPO_MB_SIZE * 1024 * 1024) - 1
        }
        self._mock_reqs_mod_get_resp.iter_content.return_value = [
            bytes('line{}'.format(index), 'ascii') for index in range(0, 5)]

        # patch logger
        patcher = mock.patch.object(machine, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)
        mock_logging.getLogger.return_value = mock.Mock(
            spec=['warning', 'error', 'debug', 'info'])
        self._mock_logger = mock_logging.getLogger.return_value

        # mock some os functions
        patcher = mock.patch.object(machine.os, 'set_blocking')
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(machine.os.path, 'exists')
        self._mock_os_exists = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_os_exists.return_value = True
        patcher = mock.patch.object(machine.os, 'remove')
        patcher.start()
        self.addCleanup(patcher.stop)

        # mock sleep
        patcher = mock.patch.object(machine.time, 'sleep', autospec=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        # patch the print function
        patcher = mock.patch.object(machine, 'print')
        patcher.start()
        self.addCleanup(patcher.stop)

        # patch the open function
        patcher = mock.patch.object(machine, 'open')
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_open_fd = mock.MagicMock()
        self._mock_open.return_value = self._mock_open_fd
        self._mock_open_fd.__enter__.return_value = self._mock_open_fd

    # setUp()

    @staticmethod
    def _get_profile(system, profile=None):
        """
        Helper function to query the db for a given profile
        """
        query = SystemProfile.query.join(
            'system_rel').filter(System.name == system)
        # profile specified: add name filter to query
        if profile:
            query = query.filter(SystemProfile.name == profile)
        # profile not specified: use filter for default
        else:
            query = query.filter(SystemProfile.default == bool(True))

        # retrieve the system profile object
        return query.one()
    # _get_profile()

    def test_exec_git(self):
        """
        Execute a playbook from a git repository
        """
        # collect necessary db objects
        kvm_system = 'kvm054'
        kvm_obj = System.query.filter_by(name=kvm_system).one()
        kvm_prof_obj = self._get_profile(kvm_obj.name)

        lpar_system = 'cpc3lp52'
        lpar_obj = System.query.filter_by(name=lpar_system).one()
        lpar_prof_obj = self._get_profile(lpar_obj.name)

        # prepare request
        request = {
            'source': 'https://user:pwd@example._com/dir/ansible-example.git',
            'playbook': 'something/playbook.yml',
            'systems': [
                {
                    'name': kvm_system,
                    'groups': ['ioclient'],
                },
                {
                    'name': lpar_system,
                    'groups': ['ioserver'],
                }
            ]
        }
        exp_url_obs = 'https://****@example._com/dir/ansible-example.git'

        # check that parse works
        parsed_resp = machine.AnsibleMachine.parse(str(request))
        self.assertEqual(parsed_resp['repo_info']['url_obs'], exp_url_obs)
        self.assertSetEqual(
            set(parsed_resp['resources']['shared']),
            set([lpar_system, lpar_obj.hypervisor])
        )
        self.assertSetEqual(
            set(parsed_resp['resources']['exclusive']),
            set([kvm_system, lpar_system])
        )

        # run machine
        machine_obj = machine.AnsibleMachine(str(request))
        machine_obj.start()

        # validate call to logger
        down_msg = ('cloning git repo from %s', exp_url_obs)
        self.assertIn(mock.call(*down_msg), self._mock_logger.info.mock_calls)

        # validate stage download
        clone_call_args = self._mock_subproc.run.call_args_list[2][0]
        cmd = 'git clone -n --depth 1 --single-branch -b master {}'.format(
            request['source'])
        for index, param in enumerate(cmd.split()):
            self.assertEqual(clone_call_args[0][index], param)

        # validate inventory file creation
        for system in request['systems']:
            if system['name'] == kvm_system:
                system_obj = kvm_obj
                prof_obj = kvm_prof_obj
            else:
                system_obj = lpar_obj
                prof_obj = lpar_prof_obj
            for group in system['groups']:
                inv_calls = [
                    mock.call('[{}]\n'.format(group)),
                    mock.call(
                        '{name} ansible_host={hostname} ansible_user={user} '
                        'ansible_ssh_pass={pwd}\n'.format(
                            name=system_obj.name,
                            hostname=system_obj.hostname,
                            user=prof_obj.credentials['user'],
                            pwd=prof_obj.credentials['passwd']),
                    )
                ]
                self._mock_open_fd.write.assert_has_calls(
                    inv_calls, any_order=True)

        # TODO: validate stage_activate_systems

        # validate exec playbook
        pb_call = self._mock_subproc.Popen.call_args[0]
        self.assertEqual(pb_call[0][0], 'ansible-playbook')
        self.assertEqual(pb_call[0][1], '-i')
        self.assertEqual(pb_call[0][2], 'tessia-hosts')
        self.assertEqual(pb_call[0][3], request['playbook'])

    # test_exec_git()

    def test_exec_web(self):
        """
        Execute a playbook from a tarball
        """
        # collect necessary db objects
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name)

        # run machine
        request = {
            'source': 'https://example._com/ansible/ansible-example.tgz',
            'playbook': 'workload1/site.yaml',
            'systems': [
                {
                    'name': test_system,
                    'groups': ['webservers', 'dbservers'],
                }
            ]
        }
        machine_obj = machine.AnsibleMachine(str(request))
        machine_obj.start()

        # validate call to logger
        down_msg = (
            'downloading compressed file from %s', request['source'])
        self.assertIn(mock.call(*down_msg), self._mock_logger.info.mock_calls)

        # validate stage download
        get_call_args = self._mock_reqs_mod.get.call_args_list[-1][0]
        self.assertEqual(get_call_args[0], request['source'])
        self._mock_reqs_mod_get_resp.raise_for_status.assert_called_with()
        self.assertTrue(self._mock_reqs_mod_get_resp.iter_content.called)
        run_call = self._mock_subproc.run.call_args[0]
        # don't need to validate the complete command, only that the correct
        # tar flags were used
        cmd = 'tar zxf'
        for index, param in enumerate(cmd.split()):
            self.assertEqual(run_call[0][index], param)

        # validate inventory file creation
        for system in request['systems']:
            for group in system['groups']:
                inv_calls = [
                    mock.call('[{}]\n'.format(group)),
                    mock.call(
                        '{name} ansible_host={hostname} ansible_user={user} '
                        'ansible_ssh_pass={pwd}\n'.format(
                            name=system_obj.name,
                            hostname=system_obj.hostname,
                            user=prof_obj.credentials['user'],
                            pwd=prof_obj.credentials['passwd']),
                    )
                ]
                self._mock_open_fd.write.assert_has_calls(
                    inv_calls, any_order=True)

        # TODO: validate stage_activate_systems

        # validate exec playbook
        pb_call = self._mock_subproc.Popen.call_args[0]
        self.assertEqual(pb_call[0][0], 'ansible-playbook')
        self.assertEqual(pb_call[0][1], '-i')
        self.assertEqual(pb_call[0][2], 'tessia-hosts')
        self.assertEqual(pb_call[0][3], request['playbook'])

    # test_exec_web()

    def test_valid_urls(self):
        """
        Exercise different combinations of valid URLs.
        """
        request = {
            'playbook': 'something/playbook.yml',
            'systems': [
                {
                    'name': 'kvm054',
                    'groups': ['target'],
                },
            ]
        }

        combos = (
            {
                'source': (
                    'https://user:pwd@example._com/dir/ansible-example.git'),
                'url': 'https://user:pwd@example._com/dir/ansible-example.git',
                'url_obs': 'https://****@example._com/dir/ansible-example.git',
                'type': 'git',
                'git_branch': 'master',
                'git_commit': 'HEAD',
            },
            {
                'source': (
                    'http://user:pwd@example._com/dir/ansible-example.git@'
                    'mybranch'),
                'url': 'http://user:pwd@example._com/dir/ansible-example.git',
                'url_obs': ('http://****@example._com/dir/ansible-example.git@'
                            'mybranch'),
                'type': 'git',
                'git_branch': 'mybranch',
                'git_commit': 'HEAD',
            },
            {
                'source': (
                    'git://example._com/dir/ansible-example.git@'
                    'mybranch:mycommit'),
                'url': 'git://example._com/dir/ansible-example.git',
                'url_obs': ('git://example._com/dir/ansible-example.git@'
                            'mybranch:mycommit'),
                'type': 'git',
                'git_branch': 'mybranch',
                'git_commit': 'mycommit',
            },
            {
                'source': (
                    'http://user:pwd@example._com/dir/ansible-example.tgz'),
                'url': 'http://user:pwd@example._com/dir/ansible-example.tgz',
                'url_obs': 'http://****@example._com/dir/ansible-example.tgz',
                'type': 'web',
            }
        )

        for combo in combos:
            request['source'] = combo.pop('source')
            parsed_resp = machine.AnsibleMachine.parse(str(request))
            for key, item in combo.items():
                self.assertEqual(
                    parsed_resp['repo_info'][key], item,
                    msg="Key '{}' comparison failed".format(key))
    # test_urls()

    def test_invalid_urls(self):
        """
        Exercise different combinations of invalid URLs.
        """
        request = {
            'playbook': 'something/playbook.yml',
            'systems': [
                {
                    'name': 'kvm054',
                    'groups': ['target'],
                },
            ]
        }

        combos = (
            ('/dir/ansible-example.git', 'Invalid URL '),
            ('scheme://example._com/dir/ansible-example.git',
             'Unsupported source url specified'),
            ('http://user:pwd@example._com/dir/ansible-file.invalid',
             "Unsupported file format 'ansible-file.invalid'"),
        )

        for source, regex in combos:
            request['source'] = source
            with self.assertRaisesRegex(ValueError, regex):
                machine.AnsibleMachine.parse(str(request))
    # test_invalid_urls()
# TestAnsibleMachine