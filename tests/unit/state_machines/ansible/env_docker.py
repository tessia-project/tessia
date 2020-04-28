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
Unit test for env docker
"""

#
# IMPORTS
#
from tessia.server.state_machines.ansible import env_docker
from unittest import mock
from unittest.mock import MagicMock
from unittest import TestCase

# WARNING: There is a local docker folder/package in the file hierarchy
#          which would be imported instead of docker py. To mitigate issues
#          this folder was renamed to docker_build.
import docker
import json
import tarfile

#
# CONSTANTS AND DEFINITIONS
#
REPO_URL = "https://github.com/ansible/ansible-examples.git"

REPO_DIR = "/tmp/1d3r5e"

PLAYBOOK_NAME = "test-playbook"


#
# CODE
#
class TestEnvDocker(TestCase):
    """
    Base class for testing EnvDocker class. The mocks are covering the
    successful cases. Those can be overridden or extended to other cases.

    Generators are used for fake docker output generation.
    e.g. this command converts the output from docker py generator to a string:
        json.loads(next(lines).decode('utf-8'))["stream"]
    And the following is the reverse operation:
        json.dumps({'stream': item}).encode('utf-8') + b'\r\n'
    """

    # Always create a new generator. (used as side_effect)
    def _gen_docker_api_exec_successful(self):
        """
        docker py produces no output when something is executed
        successfully with docker exec. Simulate this behaviour.
        """
        output = []
        for item in output:
            yield json.dumps({'stream': item}).encode('utf-8') + b'\r\n'
        self.docker_exec_is_running = False

    def _docker_api_exec_start_mock_successful(self, *args, **kwargs):
        """
        Simulate a successful docker exec call
        """
        return self._gen_docker_api_exec_successful()

    def _docker_api_exec_inspect_mock(self, *args, **kwargs):
        """
        Simulate a docker inspect call
        """
        if not self.docker_exec_is_running:
            # set to True for the next while loop
            self.docker_exec_is_running = True
            # Also reset the generator to start because the generator object
            # is shared

            return {'Running': False, 'ExitCode': 0}
        return {'Running': self.docker_exec_is_running, 'ExitCode': 0}

    @staticmethod
    def _gen_docker_output_successful():
        """
        Simulate a successful docker build process
        """
        output = ["Sending build context to Docker daemon  16.38kB",
                  "Step 1/7 : FROM ubuntu:18.04",
                  " ---> cd6d8154f1e1",
                  "Step 2/7 : ARG DEBIAN_FRONTEND=noninteractive",
                  "...",
                  {'aux': {'ID': 'sha256:0353f734562c15d8832eb600fcfb0dd17202b'
                                 'e0127087973fd067f6d5bf5e90c'}},
                  "Removing intermediate container d00160f5b378",
                  " ---> ddc72650454e",
                  "Successfully built ddc72650454e",
                  "Successfully tagged tessia_ansible_docker:latest"]
        for item in output:
            if isinstance(item, dict):
                yield json.dumps(item).encode('utf-8') + b'\r\n'
            else:
                yield json.dumps({'stream': item}).encode('utf-8') + b'\r\n'

    def setUp(self):
        """
        Provides a complete mock for EnvDocker class in the env_docker module.

        This mock provides the case of a successful execution.
        """

        # Construct a mock class which is returned by docker.from_env()
        attrs = \
            {'images.get.side_effect':
                 docker.errors.ImageNotFound("image not found"),
             'api.build.return_value':
                 TestEnvDocker._gen_docker_output_successful()}
        # Monkeypatch docker.cient.DockerClient to be able to patch api
        docker.client.DockerClient.api = {}
        # Load all attributes from client.DockerClient
        # and override them with attributes defined in attrs
        self.docker_client_mock = MagicMock(spec=docker.client.DockerClient,
                                            **attrs)

        patcher = mock.patch.object(docker, 'from_env',
                                    return_value=self.docker_client_mock,
                                    auto_spec=True)
        self.patch_from_env = patcher.start()
        self.addCleanup(patcher.stop)

        # mock print built-in to avoid sending output to test result
        patcher = mock.patch.object(env_docker, 'print')
        patcher.start()
        self.addCleanup(patcher.stop)

        # Mock logging module
        patcher = mock.patch.object(env_docker, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)

        # Mock the return_value of the getLogger method
        mock_logging.getLogger.return_value = MagicMock(
            spec=['warning', 'error', 'debug', 'info', 'getEffectiveLevel'])
        # read info log example: self._mock_logger.info.mock_calls
        self._mock_logger = mock_logging.getLogger.return_value

        # Additional Mocks for run method
        self.docker_containers_mock = MagicMock(
            spec=docker.models.containers.Container)

        # Add name Property
        self.docker_containers_mock.configure_mock(
            name='tessia_ansible_docker_123456')

        # Mock self._client.containers.run
        tmp_attrs = {
            'containers.run.return_value': self.docker_containers_mock,
            'api.exec_create.return_value': {'Id': '123456'},
            # to always generate a new generator object, the method is replaced
            'api.exec_start.side_effect':
                self._docker_api_exec_start_mock_successful,
            'api.exec_inspect.side_effect': self._docker_api_exec_inspect_mock}
        self.docker_client_mock.configure_mock(**tmp_attrs)

        # This variable is automatically set to False when
        # gen_docker_api_exec_successful finished generating output.
        self.docker_exec_is_running = True

        # Mock TarFile fd
        self.tarfile_fd_mock = MagicMock(spec=tarfile.TarFile)

        # tarfile.TarFile is mocked.
        patcher = mock.patch.object(tarfile, 'TarFile',
                                    return_value=self.tarfile_fd_mock,
                                    auto_spec=True)
        self._mock_tarfile = patcher.start()
        self.addCleanup(patcher.stop)

        # Mock open calls
        patcher = mock.patch.object(env_docker, 'open')
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_open_fd = MagicMock()
        self._mock_open.return_value = self._mock_open_fd
        self._mock_open_fd.__enter__.return_value = self._mock_open_fd


class TestEnvDockerSuccessful(TestEnvDocker):
    """
    Test successful cases in EnvDocker class.
    """

    def test_docker_build(self):
        """
        Create a docker environment and test the successful run of docker build
        """
        # By default the docker build process is mocked
        # to have a successful build output.
        env = env_docker.EnvDocker()
        env.build()

        # Check Output for successful build messages
        success_msg_1 = 'Successfully built ddc72650454e'
        success_msg_2 = 'Successfully tagged tessia_ansible_docker:latest'
        self._mock_logger.debug.assert_any_call(success_msg_1)
        self._mock_logger.debug.assert_any_call(success_msg_2)

    def test_run(self):
        """
        Test the successful run of an ansible playbook in the docker env
        """
        # Create EnvDocker
        env = env_docker.EnvDocker()

        ret = env.run(REPO_URL, REPO_DIR, PLAYBOOK_NAME)

        # expect successful run
        self.assertEqual(ret, 0)

        # Check if docker run was called
        self.assertTrue(
            len(self.docker_client_mock.containers.run.mock_calls) == 3)
        # Check if security parameters were used
        args, kwargs = self.docker_client_mock.containers.run.call_args
        self.assertEqual(kwargs["user"], "ansible")
        self.assertListEqual(kwargs["security_opt"],
                             ["no-new-privileges:true"])

        # Check call to logger
        self._mock_logger.debug.assert_any_call(
            'container status is <%s>',
            self.docker_containers_mock.status)

        # Check if downloader py was executed
        args, kwargs = \
            self.docker_client_mock.api.exec_create.call_args_list[0]
        self.assertEqual(args[0], self.docker_containers_mock.name)
        self.assertEqual(args[1], "/assets/downloader.py")
        exp_log_level = self._mock_logger.getEffectiveLevel.return_value
        self.assertEqual(kwargs["environment"],
                         {'TESSIA_ANSIBLE_DOCKER_REPO_URL': REPO_URL,
                          'TESSIA_ANSIBLE_DOCKER_LOG_LEVEL': exp_log_level})
        self.assertEqual(kwargs["workdir"], "/home/ansible/playbook")

        # Check if transferring the config files to the container was executed
        self.assertTrue(
            len(self.docker_containers_mock.put_archive.mock_calls) == 1)

        # Check if the ansible playbook is executed
        args, kwargs = \
            self.docker_client_mock.api.exec_create.call_args_list[1]
        self.assertEqual(args[0], "tessia_ansible_docker_123456")
        self.assertListEqual(args[1], ["ansible-playbook", PLAYBOOK_NAME])

        # Check kill call
        self.assertTrue(
            len(self.docker_containers_mock.kill.mock_calls) == 1)


class TestEnvDockerUnsuccessful(TestEnvDocker):
    """
    Test basic unsuccessful cases in EnvDocker class.
    """

    def _gen_docker_api_exec_unsuccessful(self):
        """
        This output mimics docker py when the Dockerfile contains an error
        and build is executed.
        """
        output = [
            'Traceback (most recent call last):\n  File "/assets/downloade'
            'r.py", line 200, in _download_git\n    check=True,\n  File "'
            '/usr/lib/python3.6/subprocess.py", line 418, in run\n    outp'
            'ut=stdout, stderr=stderr)\nsubprocess.CalledProcessError: Com'
            'mand \'[\'git\', \'clone\', \'-n\', \'--depth\', \'1\', \'--s'
            'ingle-branch\', \'-b\', \'master\', \'https://github.com/ansi'
            'ble/ansible-examples.git\', \'.\']\' returned non-zero exit s'
            'tatus 128.\n\nDuring handling of the above exception, another'
            ' exception occurred:\n\nTraceback (most recent call last):\n '
            ' File "/assets/downloader.py", line 341, in <module>\n    mai'
            'n()\n  File "/assets/downloader.py", line 337, in main\n    d'
            'ownloader.download()\n  File "/assets/downloader.py", line 29'
            '5, in download\n    self._download_git()\n  File "/assets/dow'
            'nloader.py", line 205, in _download_git\n    repo[\'url\'], r'
            'epo[\'url_obs\'])))\nValueError: Failed to git clone: fatal: '
            'destination path \'.\' already exists and is not an empty dir'
            'ectory.\n\n']
        for item in output:
            yield item.encode('utf-8')
        self.docker_exec_is_running = False

    # Mock api.exec with an unsuccessful output.
    def _docker_api_exec_start_mock_unsuccessful(self, *args, **kwargs):
        """
        Simulate an unsuccessful command, run with docker exec
        """
        # Always create a new generator. (used as side_effect)
        return self._gen_docker_api_exec_unsuccessful()

    # Mock api.build with an unsuccessful output.
    @staticmethod
    def _gen_docker_build_output_unsuccessful():
        """
        Simulate an unsuccessful docker build process
        """
        output = [
            "Step 4/7 : RUN apt-get -q update > /dev/null &&     apt-get -yq "
            "install --no-install-recommends     locales     python3-pip     "
            "rsync     git > /dev/null &&     MISTAKE &&     apt-get -q clean"
            " &&     locale-gen en_US.UTF-8 &&     "
            "update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 &&     pip3 -q"
            " install -U setuptools pip &&     apt-get -y remove python3-pip"
            " && hash -r &&     pip3 -q install -U ansible     requests &&    "
            " chmod a+x /assets/downloader.py &&     useradd --create-home "
            "--shell /bin/bash ansible &&     mkdir /home/ansible/playbook && "
            "    chown ansible:ansible /home/ansible/playbook",
            "---> Running in b049d003d131",
            "debconf: delaying package configuration, "
            "since apt-utils is not installed",
            "/bin/sh: 1: ERRORFUNC: not found",
            "Removing intermediate container b049d003d131"]
        for item in output:
            yield json.dumps({'stream': item}).encode('utf-8') + b'\r\n'
        msg = ("The command '/bin/sh -c apt-get -q update > /dev/null &&"
               "     apt-get -yq install --no-install-recommends"
               "     locales     python3-pip     rsync     git > /dev/null &&"
               "     MISTAKE &&"
               "     apt-get -q clean &&     locale-gen en_US.UTF-8 &&"
               "     update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 &&"
               "     pip3 -q install -U setuptools pip &&"
               "     apt-get -y remove python3-pip && hash -r &&"
               "     pip3 -q install -U ansible     requests &&"
               "     chmod a+x /assets/downloader.py &&"
               "     useradd --create-home --shell /bin/bash ansible &&"
               "     mkdir /home/ansible/playbook &&"
               "     chown ansible:ansible /home/ansible/playbook'"
               " returned a non-zero code: 127")
        error_msg = (
            "The command '/bin/sh -c apt-get -q update > /dev/null &&"
            "     apt-get -yq install --no-install-recommends"
            "     locales     python3-pip     rsync     git > /dev/null &&"
            "     MISTAKE &&"
            "     apt-get -q clean &&     locale-gen en_US.UTF-8 &&"
            "     update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 &&"
            "     pip3 -q install -U setuptools pip &&"
            "     apt-get -y remove python3-pip && hash -r &&"
            "     pip3 -q install -U ansible     requests &&"
            "     chmod a+x /assets/downloader.py &&"
            "     useradd --create-home --shell /bin/bash ansible &&"
            "     mkdir /home/ansible/playbook &&"
            "     chown ansible:ansible /home/ansible/playbook'"
            " returned a non-zero code: 127")
        yield json.dumps({'errorDetail': {'code': 127, 'message': msg},
                          'error': error_msg}).encode('utf-8') + b'\r\n'

    def _docker_api_exec_inspect_mock_unsuccessful(self, *args, **kwargs):
        """
        Mimic an unsuccessful docker inspect command
        """
        if not self.docker_exec_is_running:
            # set to True for the next while loop
            self.docker_exec_is_running = True
            return {'Running': False, 'ExitCode': 1}
        return {'Running': self.docker_exec_is_running, 'ExitCode': 0}

    def setUp(self):
        super().setUp()

        tmp_attrs = {'api.build.return_value':
                     TestEnvDockerUnsuccessful.
                     _gen_docker_build_output_unsuccessful()}
        self.docker_client_mock.configure_mock(**tmp_attrs)

    def test_docker_build(self):
        """
        Execute the build process with docker py throwing an exception.
        """
        # Check for a RuntimeError which should occur.
        env = env_docker.EnvDocker()
        self.assertRaises(RuntimeError, env.build)

    def test_run_api_error(self):
        """
        Case: When the docker client throws an api error exception
        """
        env = env_docker.EnvDocker()

        tmp_attrs = {'containers.run.side_effect': docker.errors.APIError(
            "Some API Error")}
        self.docker_client_mock.configure_mock(**tmp_attrs)

        self.assertRaises(RuntimeError, env.run, REPO_URL, REPO_DIR,
                          PLAYBOOK_NAME)

    def test_run_exec_unsuccessful(self):
        """
        When an error occurs in the docker container it should be
        handled through the ExitCode != 0 and come out as an RuntimeError.
        """
        env = env_docker.EnvDocker()

        tmp_attrs = {
            'api.exec_start.side_effect':
                self._docker_api_exec_start_mock_unsuccessful,
            'api.exec_inspect.side_effect':
                self._docker_api_exec_inspect_mock_unsuccessful}
        self.docker_client_mock.configure_mock(**tmp_attrs)

        self.assertRaises(RuntimeError, env.run, REPO_URL, REPO_DIR,
                          PLAYBOOK_NAME)


class TestEnvDockerKilledBySignal(TestEnvDocker):
    """
    Test unsuccessful cases in EnvDocker class where the process got killed
    by a signal.
    """

    # Mock api.build with an signal killed docker build process
    @staticmethod
    def _gen_docker_output_killed_by_signal():
        """
        Fakes the output of docker py when the build process is stopped by
        a SIGKILL or something similar.
        """
        output = ["Sending build context to Docker daemon  16.38kB",
                  "Step 1/7 : FROM ubuntu:18.04",
                  " ---> cd6d8154f1e1",
                  "Step 2/7 : ARG DEBIAN_FRONTEND=noninteractive"]
        for item in output:
            yield json.dumps({'stream': item}).encode('utf-8') + b'\r\n'

    def setUp(self):
        super().setUp()

        tmp_attrs = {
            'api.build.return_value':
            TestEnvDockerKilledBySignal._gen_docker_output_killed_by_signal()}
        self.docker_client_mock.configure_mock(**tmp_attrs)

    def test_docker_build(self):
        """
        When the build process is manually canceled e.g. by a signal, a
        runtime error should occur.
        """
        env = env_docker.EnvDocker()
        self.assertRaises(RuntimeError, env.build)
