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
from tessia.server.scheduler import spawner, wrapper
from unittest import TestCase
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import docker
import json
import multiprocessing
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


class MockClientContainer():
    """MockClientContainer for docker"""

    def __init__(self, container_name_or_id, status='running'):
        self.name = container_name_or_id
        self.status = status

    def stop(self):
        """Stop container"""

    def kill(self):
        """Force stop container"""


class TestForkSpawner(TestCase):
    """
    Test suite for process spawner
    """

    def setUp(self):
        # Mock the MachineWrapper class inside the module since the spawner
        # only imports the module inside the spawn function.
        patcher = patch.object(spawner.wrapper, 'MachineWrapper',
                               autospec=True)
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

# TestForkSpawner


class TestContainerSpawner(TestCase):
    """
    Test suite for container spawner
    """

    def setUp(self):
        # Mock the MachineWrapper class inside the module since the spawner
        # only imports the module inside the spawn function.
        patcher = patch.object(
            spawner.wrapper, 'MachineWrapper', autospec=True)
        self._mock_wrapper = patcher.start()
        self.addCleanup(patcher.stop)

        # open built-in function
        patcher = patch.object(spawner, 'open')
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)

        # os module
        patcher = patch.object(spawner, 'os', autospec=True)
        self._mock_os = patcher.start()
        self.addCleanup(patcher.stop)

        # logging module
        patcher = patch.object(spawner, 'logging', autospec=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(spawner, 'CONF', autospec=True)
        mock_conf = patcher.start()
        self.addCleanup(patcher.stop)
        mock_conf.get_config.return_value = {
            'scheduler': {'jobs_dir': '/tmp/spawner-unit-test/jobs'}
        }

        # docker API
        patcher = patch.object(spawner.docker, 'from_env')
        _mock_docker = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_client = Mock(spec_set=docker.DockerClient)
        self._mock_api = MagicMock(spec_set=docker.APIClient)
        type(self._mock_client).api = PropertyMock(
            return_value=self._mock_api)
        self._mock_containers = Mock(
            spec_set=docker.models.containers.ContainerCollection)
        type(self._mock_client).containers = PropertyMock(
            return_value=self._mock_containers)
        _mock_docker.return_value = self._mock_client

        self._mock_socket = Mock()

        # patch fork spawner for a weird edge case
        patcher = patch.object(spawner, 'ForkSpawner', autospec=True)
        self._mock_fork = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_fork.return_value.validate.return_value = \
            spawner.PROCESS_RUNNING

        self._container_spawner = spawner.ContainerSpawner()
    # setUp()

    def test_wrong_job(self):
        """
        Validate a wrong (non-containerized) job
        """
        job = MockJob()
        container_name = 'container_identifier'
        self._mock_open.return_value.__enter__.return_value.readline. \
            return_value = container_name

        # return an error trying to read file with container name
        self._mock_open.return_value.__enter__.side_effect = [
            PermissionError,
            FileNotFoundError,
        ]

        self.assertNotEqual(job.pid, 0)
        # non-zero pid, no container name is found -> refer to ForkSpawner
        validation_result = self._container_spawner.validate(job)
        self._mock_open.assert_called()
        self._mock_fork.assert_called()
        self.assertEqual(validation_result,
                         spawner.PROCESS_RUNNING)
        # same check, a different exception
        self.assertEqual(self._container_spawner.validate(job),
                         spawner.PROCESS_RUNNING)
    # test_wrong_job()

    def test_valid_job(self):
        """
        Validate containerized job
        """
        job = MockJob()
        container_name = 'container_identifier'
        self._mock_open.return_value.__enter__.return_value.readline. \
            return_value = container_name
        # return an error trying to read file with container name
        self._mock_open.return_value.__enter__.side_effect = [
            PermissionError,
            FileNotFoundError,
        ]

        job.pid = 0     # pid is zero and no container name
        self.assertEqual(self._container_spawner.validate(job),
                         spawner.PROCESS_DEAD)

        # reset effects to have good path on reading container name
        self._mock_open.return_value.__enter__.side_effect = None

        # container name is read, test docker api return values
        self._mock_containers.get.side_effect = [
            docker.errors.NotFound('no such container'),
            docker.errors.APIError('API error'),
            MockClientContainer(container_name, 'stopped'),
            MockClientContainer(container_name, 'paused'),
            MockClientContainer(container_name, 'running')
        ]

        self.assertEqual(self._container_spawner.validate(job),
                         spawner.PROCESS_DEAD)
        self.assertEqual(self._container_spawner.validate(job),
                         spawner.PROCESS_UNKNOWN)
        self.assertEqual(self._container_spawner.validate(job),
                         spawner.PROCESS_DEAD)
        self.assertEqual(self._container_spawner.validate(job),
                         spawner.PROCESS_RUNNING)
        self.assertEqual(self._container_spawner.validate(job),
                         spawner.PROCESS_RUNNING)
        self._mock_containers.get.assert_called_with(container_name)

    # test_valid_job()

    def test_spawn(self):
        """
        Test successful and failed container spawns
        """
        # We can pass bogus parameters since they are only actually used by
        # MachineWrapper, which is mocked.
        job_args = {
            'job_dir': "/jobs/2020",
            'job_type': "",
            'job_parameters': "",
            'timeout': 0}

        # I/O errors during directory creation
        self._mock_os.makedirs.side_effect = OSError()
        with self.assertRaises(
                spawner.SpawnerError,
                msg='Cannot create job directory ' + job_args['job_dir']):
            self._container_spawner.spawn(job_args=job_args)

        self._mock_os.makedirs.side_effect = None
        self._mock_open.return_value.__enter__.return_value.write. \
            side_effect = FileExistsError()
        with self.assertRaises(
                spawner.SpawnerError,
                msg='Cannot write container tag to ' + job_args['job_dir']):
            self._container_spawner.spawn(job_args=job_args)

        self._mock_open.return_value.__enter__.return_value.write. \
            side_effect = None
        self._mock_open.return_value.__enter__.return_value.write. \
            return_value = 0

        # Docker API errors during container startup
        self._mock_containers.run.side_effect = [
            docker.errors.NotFound('no such container'),
            docker.errors.APIError('unknown error')
        ]
        with self.assertRaises(spawner.SpawnerError,
                               msg='Failed to start a containerized job'):
            self._container_spawner.spawn(job_args=job_args)
        with self.assertRaises(spawner.SpawnerError,
                               msg='Failed to start a containerized job'):
            self._container_spawner.spawn(job_args=job_args)

        self._mock_containers.run.side_effect = None
        self._mock_client.api.attach_socket.side_effect = [
            docker.errors.APIError('unknown error')
        ]
        with self.assertRaises(spawner.SpawnerError,
                               msg='Failed to pass job arguments'):
            self._container_spawner.spawn(job_args=job_args)

        # test that job data is passed correctly
        self._mock_client.api.attach_socket.side_effect = None
        self._mock_client.api.attach_socket.return_value.__enter__. \
            return_value._sock.send.side_effect = lambda str_args: \
            spawner.SpawnerBase.exec_machine(**json.loads(str_args))

        pid = self._container_spawner.spawn(job_args=job_args)

        container_name = self._mock_open.return_value.__enter__.return_value. \
            write.call_args[0][0]
        self.assertEqual(pid, 0)
        self.assertRegex(container_name, 'tessia_job_executor_2020')

        self._mock_wrapper.assert_called_with(
            job_args['job_dir'],
            job_args['job_type'],
            job_args['job_parameters'],
            job_args['timeout'])

    # test_spawn()

    def test_terminate(self):
        """Job termination"""
        job = MockJob()

        container_name = 'container_identifier'
        self._mock_open.return_value.__enter__.return_value.readline. \
            return_value = container_name

        # return an error trying to read file with container name
        for effect in [PermissionError, FileNotFoundError]:
            self._mock_open.return_value.__enter__.side_effect = effect
            self._container_spawner.terminate(job)
            self._mock_containers.get.return_value.stop.assert_not_called()
            self._mock_containers.get.return_value.kill.assert_not_called()

        self._mock_open.return_value.__enter__.side_effect = None

        # container not found
        for effect in [
            docker.errors.NotFound('no such container'),
            docker.errors.APIError('API error'),
        ]:
            self._mock_containers.get.side_effect = effect
            self._container_spawner.terminate(job)
            self._mock_containers.get.return_value.stop.assert_not_called()
            self._mock_containers.get.return_value.kill.assert_not_called()

        # weird API errors do not throw
        container = Mock(spec=MockClientContainer)
        container.name = container_name
        container.stop.side_effect = docker.errors.APIError('API error')
        container.kill.side_effect = docker.errors.APIError('API error')
        self._mock_containers.get.side_effect = None
        self._mock_containers.get.return_value = container

        self._container_spawner.terminate(job)
        self._container_spawner.terminate(job, force=True)
        container.stop.assert_called()
        container.kill.assert_called()

        # correct calls are performed
        container.reset_mock()
        self._container_spawner.terminate(job)
        container.stop.assert_called()
        container.kill.assert_not_called()

        container.reset_mock()
        self._container_spawner.terminate(job, force=True)
        container.stop.assert_not_called()
        container.kill.assert_called()

    # test_terminate()

# TestContainerSpawner
