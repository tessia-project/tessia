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
spawner.py unit test
"""
import multiprocessing
from tessia.server.scheduler import spawner
from tessia.server.scheduler import wrapper
from unittest import TestCase
from unittest.mock import patch

import os
#
# CONSTANTS AND DEFINITIONS
#
UNIT_JOBS_DIR = '/tmp/test-looper/jobs-dir'


#
# CODE
#


class MockProcess():
    """MockProcess class"""

    def __init__(self, target=None, args=None, kwargs=None):
        self.pid = 100000
        self.target = target
        self.args = args if args else ()
        self.kwargs = kwargs if kwargs else {}

    def start(self):
        """Run target function"""
        self.target(*self.args, **self.kwargs)


class MockJob():
    """MockJob class to skip on the database"""

    def __init__(self):
        self.id = 20    # pylint: disable=invalid-name
        self.pid = 180


class TestSpawner(TestCase):
    """
    Test suite for process spawner
    """

    def setUp(self):
        # Mock the MachineWrapper class inside the module since the spawner
        # only imports the module inside the spawn function.
        patcher = patch.object(wrapper, 'MachineWrapper', autospec=True)
        self._mock_wrapper = patcher.start()
        self.addCleanup(patcher.stop)

        # multiprocessing module
        patcher = patch.object(spawner.multiprocessing, 'Process', spec=True)
        self._mock_mp = patcher.start()
        self._mock_mp.side_effect = MockProcess
        self.addCleanup(patcher.stop)

        # open built-in function
        patcher = patch.object(spawner, 'open')
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)

        # os module
        patcher = patch.object(spawner, 'os', autospec=True)
        self._mock_os = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_os.getcwd.return_value = UNIT_JOBS_DIR
        self._mock_os.path.basename = os.path.basename

        # logging module
        patcher = patch.object(spawner, 'logging', autospec=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self._fork_spawner = spawner.ForkSpawner()
    # setUp()

    def test_fork_comm(self):
        """
        Test different cases for reading comm of the forked process
        """
        job = MockJob()

        # set valid cwd
        self._mock_os.readlink.return_value = '{}/{}'.format(
            UNIT_JOBS_DIR, job.id)

        # try different comm read return values
        self._mock_open.return_value.__enter__.return_value.read. \
            side_effect = [FileNotFoundError,
                           PermissionError,
                           ProcessLookupError,
                           "bogus-value\n",
                           wrapper.WORKER_COMM + "\n"]

        self.assertEqual(self._fork_spawner.validate(job),
                         spawner.PROCESS_DEAD)
        self.assertEqual(self._fork_spawner.validate(job),
                         spawner.PROCESS_DEAD)
        self.assertEqual(self._fork_spawner.validate(job),
                         spawner.PROCESS_DEAD)
        self.assertEqual(self._fork_spawner.validate(job),
                         spawner.PROCESS_UNKNOWN)
        self.assertEqual(self._fork_spawner.validate(job),
                         spawner.PROCESS_RUNNING)

        self._mock_os.readlink.assert_called_with(
            '/proc/{}/cwd'.format(job.pid))

    # test_fork_comm()

    def test_fork_cwd(self):
        """
        Test different cases for reading cwd of the forked process
        """
        job = MockJob()

        # return a valid content for reading /proc/$pid/comm
        self._mock_open.return_value.__enter__.return_value.read. \
            return_value = wrapper.WORKER_COMM + "\n"

        # fail the call to open /proc/$pid/cwd file several times
        self._mock_os.readlink.side_effect = [
            PermissionError,
            FileNotFoundError,
            '/some/wrong/path',
            '{}/{}'.format(UNIT_JOBS_DIR, job.id)]

        self.assertEqual(self._fork_spawner.validate(job),
                         spawner.PROCESS_DEAD)
        self.assertEqual(self._fork_spawner.validate(job),
                         spawner.PROCESS_DEAD)
        self.assertEqual(self._fork_spawner.validate(job),
                         spawner.PROCESS_DEAD)
        self.assertEqual(self._fork_spawner.validate(job),
                         spawner.PROCESS_RUNNING)

        self._mock_os.readlink.assert_called_with(
            '/proc/{}/cwd'.format(job.pid))

    # test_fork_cwd()

    def test_fork_spawner(self):
        """
        Test successful and failed fork spawns
        """
        # We can pass bogus parameters since they are only actually used by
        # MachineWrapper, which is mocked.
        job_args = {
            'job_dir': "",
            'job_type': "",
            'job_parameters': "",
            'timeout': 0}
        pid = self._fork_spawner.spawn(job_args=job_args)

        self.assertEqual(pid, 100000)
        self._mock_wrapper.assert_called_with('', '', '', 0)

        # test failure
        self._mock_mp.side_effect = multiprocessing.ProcessError
        with self.assertRaises(spawner.SpawnerError):
            self._fork_spawner.spawn(job_args=job_args)

    # test_fork_spawner()


# TestSpawner
