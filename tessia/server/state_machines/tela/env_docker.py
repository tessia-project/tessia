# Copyright 2024, 2024 IBM Corp.
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
Docker based run environment
"""

#
# IMPORTS
#
from io import BytesIO
from tessia.server.state_machines.tela.env_base import EnvBase
from urllib.parse import urlsplit

import docker
import json
import logging
import os
import tarfile
import uuid

#
# CONSTANTS AND DEFINITIONS
#
IMAGE_NAME = 'tessia-tela'

CONTAINER_NAME_FILE = '.docker_container_name'

TELA_DIR = '/home/tela/test-workspace/tela'

TELA_RC = '/home/tela/.telarc'

TESSIA_CONFIG_DIR = '/home/tela/test-workspace/.config'

TESTS_WORKDIR = '/home/tela/test-workspace'

#
# CODE
#


class EnvDocker(EnvBase):
    """
    Class to build a docker environment to execute tests with the tela
    framework.
    """

    def __init__(self):
        """
        Constructor, creates logger instance and initialize connection
        to docker daemon.
        """
        self._logger = logging.getLogger(__name__)

        # docker client
        self._client = docker.from_env()

        self._image_name = '{}:latest'.format(IMAGE_NAME)
    # __init__()

    def _docker_build(self):
        """
        Build the docker image
        """
        context_dir = os.path.abspath('{}/docker_build'.format(
            os.path.dirname(os.path.abspath(__file__))))

        self._logger.info('building docker image %s, this might take a while',
                          self._image_name)
        lines = self._client.api.build(
            path=context_dir, tag=self._image_name,
            nocache=True,
            # Removes the intermediate containers after an unsuccessful build.
            # The intermediate containers are not removed when the build
            # process is killed by any signal.
            # In this case the cleanup method deletes the dangling images.
            forcerm=True
        )

        output = ""
        for line in lines:
            line_json = json.loads(line.decode('utf-8'))
            # WARNING: be careful when parsing the json output as it
            # can also contain a key named 'aux'.
            if 'stream' in line_json:
                self._logger.debug(line_json['stream'])
                output += line_json['stream']
            if 'errorDetail' in line_json:
                raise RuntimeError('Image build failed: {}'.format(
                    line_json['errorDetail']['message'])) from None

        # Detect if the build process was killed by a signal e.g. an external
        # entity calls docker kill.
        # Check if the output contains the final two success messages,
        # otherwise raise an exception.
        if not ("Successfully built" in output and
                "Successfully tagged" in output):
            raise RuntimeError('Image build failed: The build process is '
                               'incomplete')
    # _docker_build()

    def _upload_configuration(self, container_obj, config_dir):
        """
        Upload tela configuration to container
        """
        def _tar_filter(tarinfo):
            """Change user for configuration files"""
            tarinfo.uid = tarinfo.gid = 1000     # default user (tela)
            tarinfo.uname = tarinfo.gname = "tela"
            return tarinfo

        with BytesIO() as temp_fd:
            with tarfile.TarFile(fileobj=temp_fd, mode='w') as tar_fd:
                tar_fd.add(config_dir, arcname='.', filter=_tar_filter)
            temp_fd.seek(0)

            self._logger.debug('transferring config files to container')

            # put_archive is used because docker py doesn't have the
            # copy command in the current version of the API.
            container_obj.put_archive(TESSIA_CONFIG_DIR, temp_fd)

    def build(self):
        """
        Build docker image
        """
        # build is not run in __init__ method because the cleanup process gets
        # stuck when the build fails.
        try:
            self._client.images.get(self._image_name)
        except docker.errors.ImageNotFound:
            self._docker_build()
    # build()

    def run(self, repo_url, repo_dir, tests, tela_opts=None, runlocal=None,
            preexec=None, postexec=None):
        """
        Run tela tests inside the environment

        Args:
            repo_url (str): URL to an tela test repository.
            repo_dir (str): TemporaryDirectory path with configuration files
                            which are transferred to the container
                            environment.
            tests (str): tests to be executed.
            tela_opts (str): additional options passed to the tela execution
            runlocal (str): execute tela in docker or on remote
            preexec (dict): preexec script with optional arguments
            postexec (dict): postexec script with optional arguments

        Returns:
            int: exit code of the tela execution

        Raises:
            RuntimeError: raised when docker run or docker exec fails
        """

        # generate unique container name
        container_name = '{}_{}'.format(
            IMAGE_NAME, str(uuid.uuid4()).replace('-', ''))

        # Write the container name to a file for cleanup purposes.
        # The file is written to the working directory of the job.
        with open(CONTAINER_NAME_FILE, 'w') as container_name_file:
            container_name_file.write(container_name)

        # start the new container
        self._logger.debug('starting container %s', container_name)
        try:
            # TODO: runtime-constraints-on-resources e.g. --memory=""
            container_obj = self._client.containers.run(
                image=self._image_name, name=container_name,
                hostname=container_name,
                detach=True,             # immediately return Container object
                remove=True,             # Removes container when finished
                stdout=True, stderr=True,
                security_opt=["no-new-privileges:true"],  # disables sudo
                tty=True
            )
        # also catches docker.errors.ImageNotFound (inherits from api error)
        except docker.errors.APIError as exc:
            raise RuntimeError('Failed to run docker container with'
                               ' tela test') from exc

        self._logger.debug('container status is <%s>', container_obj.status)

        # To get the ExitCode of docker exec the low level api of
        # docker py is used because there is no way at a higher level.

        # Get repository name
        parsed_url = urlsplit(repo_url)
        repo_name = os.path.splitext(parsed_url.path.split(
            '@')[0].split('/')[-1])[0]
        test_workdir = os.path.join(TESTS_WORKDIR, repo_name)

        # Create test case directory
        cmd = ['mkdir', repo_name]
        exec_id = self._client.api.exec_create(
            container_obj.name,
            cmd,
            workdir=TESTS_WORKDIR)
        lines = self._client.api.exec_start(exec_id['Id'], stream=True)
        ret = {'Running': True, 'ExitCode': 0}
        while ret['Running']:
            ret = self._client.api.exec_inspect(exec_id['Id'])
            for line in lines:
                print(line.decode('utf-8'), end='')
        if ret['ExitCode'] != 0:
            raise RuntimeError('Failed to create repo directory')

        repos = {
            'test': {
                'workdir': test_workdir,
                'environment': {
                    'ASSETS_REPO_URL': repo_url,
                    'ASSETS_LOG_LEVEL': (
                        self._logger.getEffectiveLevel())
                },
            }
        }

        for repo in repos.values():
            # Download test case
            exec_id = self._client.api.exec_create(
                container_obj.name,
                '/assets/downloader.py',
                environment=repo['environment'],
                workdir=repo['workdir'])
            lines = self._client.api.exec_start(exec_id['Id'], stream=True)
            ret = {'Running': True, 'ExitCode': 0}
            while ret['Running']:
                ret = self._client.api.exec_inspect(exec_id['Id'])
                for line in lines:
                    print(line.decode('utf-8'), end='')
            if ret['ExitCode'] != 0:
                raise RuntimeError(
                    'Failed to download repository to {}'.format(
                        repo['workdir']))

        # Copy inventory and config files to the tela container.
        self._upload_configuration(container_obj, repo_dir)

        if preexec:
            # execute preexec script
            cmd = []
            env = None
            if isinstance(preexec, str):
                cmd = [preexec]
            elif isinstance(preexec, dict):
                cmd = [preexec['path']] + preexec.get('args', [])
                env = preexec.get('env')
            else:
                raise RuntimeError('Invalid preexec_script argument')

            self._logger.info('starting preexec script %s', cmd[0])
            exec_id = self._client.api.exec_create(
                container_obj.name,
                cmd,
                environment=env,
                workdir=test_workdir)
            lines = self._client.api.exec_start(exec_id['Id'], stream=True)
            ret = {'Running': True, 'ExitCode': 0}
            while ret['Running']:
                ret = self._client.api.exec_inspect(exec_id['Id'])
                for line in lines:
                    print(line.decode('utf-8'), end='')
            self._logger.info('preexec script finished with exit code %d',
                              ret['ExitCode'])
            if ret['ExitCode']:
                raise RuntimeError(f"Error code '{ret['ExitCode']}' from"
                                   f" preexec_script execution of '{cmd[0]}'")

        # Start tela tests
        exec_id = self._client.api.exec_create(
            container_obj.name,
            '/assets/tela-worker.sh',
            environment={
                'ASSETS_REPO_NAME': repo_name,
                'ASSETS_REPO_URL': repo_url,
                'ASSETS_TELA_TESTS': tests,
                'ASSETS_TELA_OPTS': tela_opts,
                'ASSETS_TELA_RUN_LOCAL': int(runlocal is True),
                'ASSETS_LOG_LEVEL': (
                    logging.getLevelName(self._logger.getEffectiveLevel()))
            },
            workdir=test_workdir)
        lines = self._client.api.exec_start(exec_id['Id'], stream=True)
        ret = {'Running': True, 'ExitCode': 0}
        while ret['Running']:
            ret = self._client.api.exec_inspect(exec_id['Id'])
            for line in lines:
                print(line.decode('utf-8'), end='')

        if ret['ExitCode']:
            self._logger.info('Container exited abnormally, exit code %d',
                              ret['ExitCode'])

        if postexec:
            # execute postexec script
            cmd = []
            env = None
            if isinstance(postexec, str):
                cmd = [postexec]
            elif isinstance(postexec, dict):
                cmd = [postexec['path']] + postexec.get('args', [])
                env = postexec.get('env')
            else:
                raise RuntimeError('Invalid postexec_script argument')

            self._logger.info('starting postexec script %s', cmd[0])
            exec_id = self._client.api.exec_create(
                container_obj.name,
                cmd,
                environment=env,
                workdir=test_workdir)
            lines = self._client.api.exec_start(exec_id['Id'], stream=True)
            ret = {'Running': True, 'ExitCode': 0}
            while ret['Running']:
                ret = self._client.api.exec_inspect(exec_id['Id'])
                for line in lines:
                    print(line.decode('utf-8'), end='')
            self._logger.info('postexec script finished with exit code %d',
                              ret['ExitCode'])
            if ret['ExitCode']:
                raise RuntimeError(f"Error code '{ret['ExitCode']}' from"
                                   f" postexec_script execution of '{cmd[0]}'")

        self._logger.info('removing container...')
        container_obj.stop()

        return ret['ExitCode']
    # run()

    def cleanup(self):
        """
        Cleanup docker container and dangling images.
        """
        if not self._client:
            return

        self._logger.info("cleaning up docker run environment")

        try:
            with open(CONTAINER_NAME_FILE, "r") as container_name_file:
                container_name = container_name_file.read()

                self._logger.debug("cleanup docker container")

                # If the container still exists force a removal.
                try:
                    container = self._client.containers.get(container_name)

                    try:
                        container.remove(
                            v=False,    # do not remove the volume
                            force=True  # kill a running container with SIGKILL
                        )
                        self._logger.debug("container was force removed")
                    except docker.errors.APIError:
                        pass
                except docker.errors.NotFound:
                    pass
        except OSError:
            self._logger.warning("no container to cleanup found")

        # Delete dangling images. Dangling images exist if you cancel a job
        # during the build process of the image.
        images = self._client.images.list(filters=({'dangling': True}))
        for image in images:
            try:
                self._client.images.remove(image.id)
                self._logger.debug(
                    "the dangling image %s was removed", image.id)
            except docker.errors.APIError:
                # In case the image is currently in a build process the image
                # is not removed. Continue with removing other dangling images.
                pass
    # cleanup()
# EnvDocker()
