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
Docker based run environment
"""

#
# IMPORTS
#
from io import BytesIO
from tessia.server.state_machines.ansible.env_base import EnvBase

import docker
import json
import logging
import os
import tarfile
import uuid

#
# CONSTANTS AND DEFINITIONS
#
IMAGE_NAME = 'tessia_ansible_docker'

CONTAINER_NAME_FILE = '.docker_container_name'

INVENTORY_DIR = '/home/ansible'

PLAYBOOK_DIR = '/home/ansible/playbook'

#
# CODE
#
class EnvDocker(EnvBase):
    """
    Class to build a docker environment to execute ansible playbooks
    independently from each other.
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


    def run(self, repo_url, repo_dir, playbook_name):
        """
        Run an ansible playbook inside the environment

        Args:
            repo_url (str): URL to an ansible playbook repository.
            repo_dir (str): TemporaryDirectory path with configuration files
                            which are transferred to the container
                            environment.
            playbook_name (str): playbook name to be executed.

        Returns:
            int: exit code of the ansible playbook

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
                user="ansible",          # less privileged user
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
                               ' ansible playbook') from exc

        self._logger.debug('container status is <%s>', container_obj.status)

        # To get the ExitCode of docker exec the low level api of
        # docker py is used because there is no way at a higher level.
        exec_id = self._client.api.exec_create(
            container_obj.name,
            '/assets/downloader.py',
            environment={
                'TESSIA_ANSIBLE_DOCKER_REPO_URL': repo_url,
                'TESSIA_ANSIBLE_DOCKER_LOG_LEVEL': (
                    self._logger.getEffectiveLevel())
            },
            workdir=PLAYBOOK_DIR)
        lines = self._client.api.exec_start(exec_id['Id'], stream=True)
        ret = {'Running': True, 'ExitCode': 0}
        while ret['Running']:
            ret = self._client.api.exec_inspect(exec_id['Id'])
            for line in lines:
                print(line.decode('utf-8'), end='')
        if ret['ExitCode'] != 0:
            raise RuntimeError('Failed to download repository')

        # Copy inventory and config files to the ansible container.
        with BytesIO() as temp_fd:
            with tarfile.TarFile(fileobj=temp_fd, mode='w') as tar_fd:
                tar_fd.add(repo_dir, arcname='.')
            temp_fd.seek(0)

            self._logger.debug('transferring config files to container')

            # put_archive is used because docker py doesn't have the
            # copy command in the current version of the API.
            container_obj.put_archive(INVENTORY_DIR, temp_fd)

        # Start ansible playbook
        exec_id = self._client.api.exec_create(
            container_obj.name,
            ['ansible-playbook', playbook_name],
            workdir=PLAYBOOK_DIR)
        lines = self._client.api.exec_start(exec_id['Id'], stream=True)
        ret = {'Running': True, 'ExitCode': 0}
        while ret['Running']:
            ret = self._client.api.exec_inspect(exec_id['Id'])
            for line in lines:
                print(line.decode('utf-8'), end='')

        self._logger.info('stopping container...')
        container_obj.kill()  # SIGKILL

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
