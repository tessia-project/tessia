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

from tessia.server.state_machines import base
from tessia.server.state_machines.ansible import machine
from tessia.server.db.models import System, SystemProfile
from tessia.server.lib.mediator import MEDIATOR
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock

import inspect
import json
import os
import secrets
import yaml

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
        # Load data from json file
        sample_file = '{}/data.json'.format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(sample_file, 'r') as sample_fd:
            data = sample_fd.read()
        # Write data to fake Database
        DbUnit.create_db()
        DbUnit.create_entry(json.loads(data))
        # Access database through db property
        cls.db = DbUnit

        url = os.environ.get('TESSIA_MEDIATOR_URI')
        if not url:
            raise RuntimeError('env variable TESSIA_MEDIATOR_URI not set')

        # switch to test database
        MEDIATOR._mediator_uri = url.replace('/0', '/1')
        cls._mediator = MEDIATOR
    # setUpClass()

    def setUp(self):
        # mock config object
        patcher = mock.patch.object(base, 'CONF', autospec=True)
        self._mock_conf = patcher.start()
        self.addCleanup(patcher.stop)

        # mock sys object
        patcher = mock.patch.object(base, 'sys', autospec=True)
        self._mock_sys = patcher.start()
        self._mock_sys_tblimit = 10
        self._mock_sys.tracebacklimit = self._mock_sys_tblimit
        self.addCleanup(patcher.stop)

        # patch the open function
        patcher = mock.patch.object(machine, 'open')
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_open_fd = MagicMock()
        self._mock_open.return_value = self._mock_open_fd
        self._mock_open_fd.__enter__.return_value = self._mock_open_fd

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

        # patch logger
        patcher = mock.patch.object(machine, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)
        mock_logging.getLogger.return_value = mock.Mock(
            spec=['warning', 'error', 'debug', 'info'])
        self._mock_logger = mock_logging.getLogger.return_value

        # patch env_docker
        patcher = mock.patch.object(machine, "EnvDocker", autospec=True)
        self._mock_env_docker = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_env_docker.return_value.run.return_value = 0

        # patch requests library (just used by run web)
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
    # setUp()

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
                'url': (
                    'http://user:pwd@example._com/dir/ansible-example.git@'
                    'mybranch'),
                'url_obs': ('http://****@example._com/dir/ansible-example.git@'
                            'mybranch'),
                'type': 'git',
                'git_branch': 'mybranch',
                'git_commit': 'HEAD',
            },
            {
                'source': (
                    'https://example._com/dir/ansible-example.git@:mycommit'),
                'url': (
                    'https://example._com/dir/ansible-example.git@:mycommit'),
                'url_obs': ('https://example._com/dir/ansible-example.git@'
                            ':mycommit'),
                'type': 'git',
                'git_branch': 'master',
                'git_commit': 'mycommit',
            },
            {
                'source': (
                    'git://example._com/dir/ansible-example.git@'
                    'mybranch:mycommit'),
                'url': ('git://example._com/dir/ansible-example.git@'
                        'mybranch:mycommit'),
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
    # test_valid_urls()

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

    @staticmethod
    def _get_profile(system, profile=None):
        """
        Helper function to query the fake db for a given profile
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

    def test_preexec(self):
        """
        Test running preexec script
        """
        # collect necessary db objects
        test_system = 'kvm054'

        request = {
            'source': 'https://example._com/ansible/ansible-example.tgz',
            'playbook': 'workload1/site.yaml',
            'systems': [
                {
                    'name': test_system,
                    'groups': ['webservers', 'dbservers'],
                }
            ],
            'preexec_script': 'prepare.sh',
            'galaxy_req': 'requirements.yaml',
            'verbosity': 'DEBUG'
        }
        machine_obj = machine.AnsibleMachine(str(request))
        machine_obj.start()

        # validate exec playbook
        self._mock_env_docker.return_value.run.assert_called_with(
            request['source'],
            machine_obj._temp_dir,
            request['playbook'],
            request['galaxy_req'],
            request['preexec_script'])
        self.assertEqual(
            len(self._mock_env_docker.return_value.run.mock_calls), 1)

        # validate preexec object
        request['preexec_script'] = {
            'path': 'prepare.sh',
            'args': ['--apply-token'],
            'env': {
                'TOKEN': 'secret'
            }
        }
        machine_obj = machine.AnsibleMachine(str(request))
        machine_obj.start()
        self._mock_env_docker.return_value.run.assert_called_with(
            request['source'],
            machine_obj._temp_dir,
            request['playbook'],
            request['galaxy_req'],
            request['preexec_script'])
        self.assertEqual(
            len(self._mock_env_docker.return_value.run.mock_calls), 2)
    # test_preexec()

    def test_start_git(self):
        """
        Start the ansible machine with a git repo as ansible playbook source.
        This test also executes parse which executes _get_url_type,
        _parse_source and _get_resources in the process.
        """
        # Prepare parameters to create an AnsibleMachine object
        # The params are the actual request parameters which were sent
        # by the tessia client.
        kvm_system = 'kvm054'
        # Get data from fake Database
        kvm_obj = System.query.filter_by(name=kvm_system).one()
        kvm_prof_obj = self._get_profile(kvm_obj.name)

        lpar_system = 'cpc3lp52'
        lpar_obj = System.query.filter_by(name=lpar_system).one()
        lpar_prof_obj = self._get_profile(lpar_obj.name)

        request = {
            'source': 'https://user:pwd@example._com/dir/ansible-example.git',
            'playbook': 'something/playbook.yml',
            'vars': {
                'globalint': 1,
                'globalstr': 'globalstr',
                'globalarr': ['item1', 'item2'],
                'globalobj': {
                    'nestedvar': 'nestedvar'
                }
            },
            'groups': {
                'ioclient': {
                    'vars': {
                        'groupint': 1,
                        'groupstr': 'groupstr',
                        'grouparr': ['item1', 'item2'],
                        'groupobj': {
                            'nestedvar': 'nestedvar'
                        }
                    }
                },
                'all': {
                    'vars': {
                        'globalgroupint': 1,
                        'globalgroupstr': 'globalgroupstr',
                        'globalgrouparr': ['item1', 'item2'],
                        'globalgroupobj': {
                            'nestedvar': 'nestedvar'
                        }
                    }
                }
            },
            'systems': [
                {
                    'name': kvm_system,
                    'groups': ['ioclient'],
                    'vars': {
                        'systemint': 1,
                        'systemstr': 'systemstr',
                        'systemarr': ['item1', 'item2'],
                        'systemobj': {
                            'nestedvar': 'nestedvar'
                        }
                    },
                },
                {
                    'name': lpar_system,
                    'groups': ['ioserver'],
                    'profile': 'fcp1',
                }
            ]
        }
        exp_url_obs = 'https://****@example._com/dir/ansible-example.git'

        # check that parse works without duplication of resources
        parsed_resp = machine.AnsibleMachine.parse(str(request))

        self.assertEqual(parsed_resp['repo_info']['url_obs'], exp_url_obs)
        self.assertSetEqual(
            set(parsed_resp['resources']['shared']),
            {lpar_obj.hypervisor}
        )
        self.assertSetEqual(
            set(parsed_resp['resources']['exclusive']),
            {kvm_system, lpar_system}
        )

        # create ansible machine object
        machine_obj = machine.AnsibleMachine(str(request))
        # start the state machine
        machine_obj.start()

        # now validate all stages

        # no verbosity check - check that config was not called
        self._mock_conf.assert_not_called()
        self.assertEqual(self._mock_sys.tracebacklimit, 0,
                         'sys.tracebacklimit not set to 0')

        # validate stage build environment
        # Validate that the method was called once
        self.assertTrue(
            len(self._mock_env_docker.return_value.build.mock_calls) == 1)

        # validate stage create config
        # get temp dir from temp_dir_file.write(self._temp_dir) call
        temp_dir_path = self._mock_open_fd.write.call_args_list[0][0][0]

        # collect var files
        exp_var_files = []

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
                        '{hostname} ansible_host={hostname} '
                        'ansible_user={user} '
                        'ansible_ssh_pass={pwd}\n'.format(
                            hostname=system_obj.hostname,
                            user=prof_obj.credentials['admin-user'],
                            pwd=prof_obj.credentials['admin-password']),
                    )
                ]
                self._mock_open_fd.write.assert_has_calls(
                    inv_calls, any_order=True)

        # add to validate system vars file creation
        exp_var_files.append(
            os.path.join(temp_dir_path, 'host_vars', kvm_system + '.yml'))
        exp_var_files.append(
            os.path.join(temp_dir_path, 'host_vars',
                         kvm_obj.hostname + '.yml'))

        # add to validate groups var file creation
        for group_name, _ in request['groups'].items():
            if group_name == 'all':
                exp_var_files.append(
                    os.path.join(temp_dir_path, 'group_vars', 'all',
                                 'all_2.yml'))
            else:
                exp_var_files.append(
                    os.path.join(temp_dir_path, 'group_vars',
                                 group_name + '.yml'))

        # add to validate global var file creation
        exp_var_files.append(
            os.path.join(temp_dir_path, 'group_vars', 'all', 'all_1.yml'))

        # validate var file creation
        for exp_var_file in exp_var_files:
            self._mock_open.assert_has_calls([mock.call(exp_var_file, 'w')])

        # TODO: validate stage_activate_systems

        # validate exec playbook
        self.assertTrue(
            len(self._mock_env_docker.return_value.run.mock_calls) == 1)

        # check cleanup
        # check if directory was removed
        self.assertFalse(os.path.exists(machine_obj._temp_dir))
    # test_start_git()

    def test_start_shared(self):
        """
        Test shared execution
        """
        request = inspect.cleandoc("""
            ---
            source: 'https://example._com/ansible/ansible-example.tgz'
            playbook: 'workload1/site.yaml'
            systems:
                - name: kvm054
                  groups: [webservers, dbservers]
        """)

        parsed = machine.AnsibleMachine.parse(request)
        self.assertNotIn('kvm054', parsed['resources']['shared'])
        self.assertEqual(['kvm054'], parsed['resources']['exclusive'])

        request += '\nshared: true'
        parsed = machine.AnsibleMachine.parse(request)
        self.assertIn('kvm054', parsed['resources']['shared'])
        self.assertEqual([], parsed['resources']['exclusive'])
    # test_start_shared()

    def test_start_web(self):
        """
        Execute a playbook from an archive downloaded from an url
        """
        # collect necessary db objects
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name)

        request = {
            'source': 'https://example._com/ansible/ansible-example.tgz',
            'playbook': 'workload1/site.yaml',
            'systems': [
                {
                    'name': test_system,
                    'groups': ['webservers', 'dbservers'],
                }
            ],
            'verbosity': 'DEBUG'
        }
        machine_obj = machine.AnsibleMachine(str(request))
        machine_obj.start()

        # validate inventory file creation
        for system in request['systems']:
            for group in system['groups']:
                inv_calls = [
                    mock.call('[{}]\n'.format(group)),
                    mock.call(
                        '{hostname} ansible_host={hostname} '
                        'ansible_user={user} '
                        'ansible_ssh_pass={pwd}\n'.format(
                            hostname=system_obj.hostname,
                            user=prof_obj.credentials['admin-user'],
                            pwd=prof_obj.credentials['admin-password']),
                    )
                ]
                self._mock_open_fd.write.assert_has_calls(
                    inv_calls, any_order=True)

        # TODO: validate stage_activate_systems

        # verbosity was set, validate config was called
        self._mock_conf.log_config.assert_called_with(
            conf=machine.AutoInstallMachine._LOG_CONFIG,
            log_level=request['verbosity'])
        self.assertEqual(self._mock_sys.tracebacklimit, self._mock_sys_tblimit,
                         'sys.tracebacklimit was altered')

        # validate exec playbook
        self.assertTrue(
            len(self._mock_env_docker.return_value.run.mock_calls) == 1)

        # check cleanup
        # check if directory was removed
        self.assertFalse(os.path.exists(machine_obj._temp_dir))
    # test_start_web()

    def test_start_wrong_profile(self):
        """
        Try to run a playbook while specifying a system profile that does not
        exist.
        """
        test_system = 'kvm054'

        request = {
            'source': 'https://example._com/ansible/ansible-example.tgz',
            'playbook': 'workload1/site.yaml',
            'systems': [
                {
                    'name': test_system,
                    'groups': ['webservers', 'dbservers'],
                    'profile': 'does_not_exist',
                }
            ],
            'verbosity': 'DEBUG'
        }
        with self.assertRaisesRegex(ValueError, 'Profile .* not found'):
            machine_obj = machine.AnsibleMachine(str(request))
            machine_obj.start()
    # test_start_wrong_profile()

    def test_secrets(self):
        """
        Test secret data recombine
        """
        test_system = 'kvm054'
        token = secrets.token_urlsafe()
        request = {
            'source': 'https://oauth:${TOKEN}@example.com/ansible/'
                      'ansible-example.tgz',
            'playbook': 'workload1/site.yaml',
            'systems': [
                {
                    'name': test_system,
                    'groups': ['webservers', 'dbservers'],
                }
            ],
            'secrets': {
                'TOKEN': token
            },
            'verbosity': 'DEBUG'
        }
        # make sure secret extraction and recombination works
        parmfile, extra_vars = machine.AnsibleMachine.prefilter(
            yaml.dump(request, default_flow_style=False))
        self.assertIsNotNone(extra_vars)
        self.assertNotIn('secrets', yaml.safe_load(parmfile))
        self._mediator.set("request:id", extra_vars, expire=10)
        extra_vars = self._mediator.get("request:id")
        combined = machine.AnsibleMachine.recombine(parmfile, extra_vars)
        self.assertIn("oauth:{}".format(token), combined)
    # test_secrets()

    def test_var(self):
        """
        Test that environment variables are converted into strings
        """
        request = inspect.cleandoc("""
            ---
            source: "https://git@example.com/ansible/ansible-example.git"
            playbook: workload1/site.yaml
            systems:
                - name: kvm054
                  groups: [webservers, dbservers]
            secrets:
                explicit: "2"
                implicit: 2
                tagged: !!str 2
                block: |
                    2
                fold: >
                    2
                foldquote: >
                    "2"
                var: "something-in"
                invar: "${var}"
            preexec_script:
                path: "./preexec.sh"
                env:
                    e: ${explicit}
                    i: ${implicit}
                    t: ${tagged}
                    b: ${block}
                    f: ${fold}
                    fq: ${foldquote}
                    qe: "${explicit}"
                    qi: "${implicit}"
                    qt: "${tagged}"
                    qb: "${block}"
                    qf: "${fold}"
                    qfq: "${foldquote}"
                    ${var}: "anything"
                    invar: ${var}-${invar}
            verbosity: DEBUG
        """)
        # make sure secret extraction and recombination works
        parmfile, extra_vars = machine.AnsibleMachine.prefilter(request)
        self.assertIsNotNone(extra_vars)
        filtered_parmfile = yaml.safe_load(parmfile)
        self.assertNotIn('secrets', filtered_parmfile)
        for var in ('e', 'i', 't', 'b', 'f', 'fq'):
            self.assertIsInstance(
                filtered_parmfile['preexec_script']['env'][var], str)
            self.assertIsInstance(
                filtered_parmfile['preexec_script']['env']['q' + var], str)

        combined = machine.AnsibleMachine.recombine(parmfile, extra_vars)
        combined_parmfile = yaml.safe_load(combined)
        for var in ('e', 'i', 't', 'b', 'f', 'fq'):
            self.assertIsInstance(
                combined_parmfile['preexec_script']['env'][var], str)
            self.assertIsInstance(
                combined_parmfile['preexec_script']['env']['q' + var], str)
            self.assertEqual(
                combined_parmfile['preexec_script']['env'][var],
                combined_parmfile['preexec_script']['env']['q' + var])
        self.assertEqual(
            'anything',
            combined_parmfile['preexec_script']['env']['something-in'])
        self.assertEqual(
            'something-in-${var}',
            combined_parmfile['preexec_script']['env']['invar'])
        self.assertIn("e: '2'", combined)
    # test_var()

    def test_url_autoprotect(self):
        """
        Test url auth data protection
        """
        test_system = 'kvm054'
        request = {
            'source': 'https://oauth:password@example.com/ansible/'
                      'ansible-example.tgz',
            'playbook': 'workload1/site.yaml',
            'systems': [
                {
                    'name': test_system,
                    'groups': ['webservers', 'dbservers'],
                }
            ],
            'verbosity': 'DEBUG'
        }
        # make sure password is extracted and replaced with a variable
        parmfile, extra_vars = machine.AnsibleMachine.prefilter(
            yaml.dump(request, default_flow_style=False))
        self.assertIsNotNone(extra_vars)
        self.assertEqual(extra_vars['token'], 'password')
        self.assertNotIn('password', parmfile)
        self.assertIn('${token}', parmfile)
    # test_url_autoprotect()

    # TODO: simulate a signal kill and verify cleanup

# TestAnsibleMachine
