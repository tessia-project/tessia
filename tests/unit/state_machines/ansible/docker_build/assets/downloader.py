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
Unittest for RepoDownloader class from downloader module
"""

#
# IMPORTS
#
from tessia.server.state_machines.ansible import machine

from importlib import util
from itertools import chain, cycle
from unittest import mock
from unittest import TestCase

import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestRepoDownloader(TestCase):
    """
    RepoDownloader can download ansible playbooks from git or from a
    tarball web url. If the url is valid is tested beforehand.
    """
    @classmethod
    def setUpClass(cls):
        """
        Load the download module dynamically
        """
        mod_path = '{}/docker_build/assets/downloader.py'.format(
            os.path.dirname(machine.__file__))
        spec = util.spec_from_file_location('downloader', mod_path)
        cls.downloader = util.module_from_spec(spec)
        spec.loader.exec_module(cls.downloader)
    # setUpClass

    def setUp(self):
        """
        Called before each test to set up the necessary mocks.
        """
        # mock for request library
        patcher = mock.patch.object(self.downloader, 'requests', autospec=True)
        self._mock_reqs_mod = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_reqs_mod_get_resp = self._mock_reqs_mod.get.return_value
        # prepare the response for the usual case
        self._mock_reqs_mod_get_resp.headers = {
            'content-length': (
                self.downloader.MAX_REPO_MB_SIZE * 1024 * 1024) - 1
        }
        self._mock_reqs_mod_get_resp.iter_content.return_value = [
            bytes('line{}'.format(index), 'ascii') for index in range(0, 5)]

        # mock some os functions
        patcher = mock.patch.object(self.downloader.os, 'set_blocking')
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(self.downloader.os.path, 'exists')
        self._mock_os_exists = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_os_exists.return_value = True
        patcher = mock.patch.object(self.downloader.os, 'remove')
        patcher.start()
        self.addCleanup(patcher.stop)

        # patch logger
        patcher = mock.patch.object(self.downloader, 'getLogger')
        mock_get_logger = patcher.start()
        self.addCleanup(patcher.stop)
        mock_get_logger.return_value = mock.Mock(
            spec=['warning', 'error', 'debug', 'info'])
        self._mock_logger = mock_get_logger.return_value

        # patch the print function
        patcher = mock.patch.object(self.downloader, 'print')
        patcher.start()
        self.addCleanup(patcher.stop)

        # patch the open function
        patcher = mock.patch.object(self.downloader, 'open')
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_open_fd = mock.MagicMock()
        self._mock_open.return_value = self._mock_open_fd
        self._mock_open_fd.__enter__.return_value = self._mock_open_fd

        # mocks for subprocess
        patcher = mock.patch.object(
            self.downloader, 'subprocess', autospec=True)
        self._mock_subproc = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_subproc.CalledProcessError.side_effect = Exception()
        self._mock_proc = mock.Mock(spec=['stdout', 'poll', 'returncode'])
        self._mock_subproc.Popen.return_value = self._mock_proc

        # Return a specific value for git ls-remote
        # It is only checked in test_download_git,
        # in other cases it should be non-empty
        self._mock_subproc.run.return_value.stdout.splitlines.side_effect = (
            chain([['mocked-commit-id\trefs/heads/master']],
                  cycle(['unchecked'])))

        # prepare the playbook exec for the usual case (read two lines then
        # process ends)
        self._mock_proc.stdout.readline.side_effect = [
            'fake_output1\n', None, 'fake_output2\n', None]
        self._mock_proc.poll.side_effect = [None, 500]
        self._mock_proc.returncode = 0
    # setUp()

    def test_download_git(self):
        """
        Download from a git repository
        """
        source = 'https://user:pwd@example._com/dir/ansible-example.git'
        exp_url_obs = 'https://****@example._com/dir/ansible-example.git'

        tmp_downloader = self.downloader.RepoDownloader(source)
        # _parse_source and _get_url_type was executed
        self.assertEqual(tmp_downloader._repo_info['url_obs'], exp_url_obs)

        tmp_downloader.download()

        # validate call to logger
        down_msg = ('cloning git repo from %s branch %s/%s commit %s',
                    exp_url_obs, 'master', 'mocked-commit-id', 'HEAD')
        self.assertIn(mock.call(*down_msg), self._mock_logger.info.mock_calls)

        # validate stage download
        clone_call_args = self._mock_subproc.run.call_args_list[1][0]
        cmd = 'git clone -n --depth 1 --single-branch -b master {} .'.format(
            source)
        for index, param in enumerate(cmd.split()):
            self.assertEqual(clone_call_args[0][index], param)
    # test_download_git()

    def test_download_web(self):
        """
        Download a repository from an archive
        """
        source = 'https://example._com/ansible/ansible-example.tgz'

        tmp_downloader = self.downloader.RepoDownloader(source)
        # _parse_source and _get_url_type was executed

        tmp_downloader.download()

        # validate call to logger
        down_msg = ('downloading compressed file from %s', source)
        self.assertIn(mock.call(*down_msg), self._mock_logger.info.mock_calls)

        # validate stage download
        get_call_args = self._mock_reqs_mod.get.call_args_list[-1][0]
        self.assertEqual(get_call_args[0], source)
        self._mock_reqs_mod_get_resp.raise_for_status.assert_called_with()
        self.assertTrue(self._mock_reqs_mod_get_resp.iter_content.called)
        run_call = self._mock_subproc.run.call_args[0]
        # don't need to validate the complete command, only that the correct
        # tar flags were used
        cmd = 'tar zxf'
        for index, param in enumerate(cmd.split()):
            self.assertEqual(run_call[0][index], param)
    # test_download_web()

    def test_invalid_urls(self):
        """
        Exercise different combinations of invalid URLs.
        """
        combos = (
            ('/dir/ansible-example.git', 'Invalid URL '),
            ('scheme://example._com/dir/ansible-example.git',
             'Unsupported source url specified'),
            ('http://user:pwd@example._com/dir/ansible-file.invalid',
             "Unsupported file format 'ansible-file.invalid'"),
        )

        for source, regex in combos:
            with self.assertRaisesRegex(ValueError, regex):
                tmp_downloader = self.downloader.RepoDownloader(source)
                tmp_downloader.download()
    # test_invalid_urls()

    def test_valid_urls(self):
        """
        Exercise different combinations of valid URLs.
        """
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
                    'https://example._com/dir/ansible-example.git@:mycommit'),
                'url': 'https://example._com/dir/ansible-example.git',
                'url_obs': ('https://example._com/dir/ansible-example.git@'
                            ':mycommit'),
                'type': 'git',
                'git_branch': 'master',
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
            source = combo.pop('source')
            tmp_downloader = self.downloader.RepoDownloader(source)

            parsed_resp = tmp_downloader._parse_source(source)
            for key, item in combo.items():
                self.assertEqual(
                    parsed_resp[key], item,
                    msg="Key '{}' comparison failed".format(key))
    # test_valid_urls()

# TestRepoDownloader
