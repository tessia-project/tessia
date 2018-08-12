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
# TODO: expose image name in conf file
IMAGE_NAME = 'tessia-ansible-docker'

#
# CODE
#
class EnvDocker(EnvBase):
    """
    Abstract class to define the environment interface to be implemented by
    specialized classes.
    """
    def __init__(self):
        """
        """
        self._logger = logging.getLogger(__name__)

        # docker client
        self._client = docker.from_env()

        # build image if not available
        self._image_name = '{}:latest'.format(IMAGE_NAME)
        try:
            self._client.images.get(self._image_name)
        except docker.errors.ImageNotFound:
            self._docker_build()
    # __init__()

    def _docker_build(self):
        """
        Build the docker image
        """
        context_dir = os.path.abspath('{}/docker'.format(
            os.path.dirname(os.path.abspath(__file__))))

        self._logger.info('building docker image %s', self._image_name)
        lines = self._client.api.build(
            path=context_dir, tag=self._image_name, forcerm=True)

        for line in lines:
            line_json = json.loads(line.decode('utf-8'))
            if 'stream' in line_json:
                self._logger.info(line_json['stream'])
            if 'errorDetail' in line_json:
                raise RuntimeError('Image build failed: {}'.format(
                    line_json['errorDetail']['message'])) from None
    # _docker_build()

    def run(self, repo_url, repo_dir, playbook_name):
        """
        Run ansible inside the docker environment

        Args:
            repo_dir (str): ansible repository dir

        Returns:
            int: exit code
        """
        container_name = '{}_{}'.format(
            IMAGE_NAME, str(uuid.uuid4()).replace('-', ''))

        #bind_mount = docker.types.Mount(
        #    target='/home/ansible', source=repo_dir, type='bind')

        # start the new container
        self._logger.info('starting container %s', container_name)
        container_obj = self._client.containers.run(
            image=self._image_name, name=container_name,
            hostname=container_name, detach=True,
            remove=True,
            auto_remove=True,
            entrypoint='/bin/cat',
            #working_dir='/home/ansible'
            stdout=True, stderr=True,
            tty=True
        )

        self._logger.info('Container status is %s', container_obj.status)

        exec_id = self._client.api.exec_create(
            container_obj.name,
            '/assets/downloader',
            environment={'TESSIA_ANSIBLE_DOCKER_REPO_URL': repo_url},
            workdir='/home/ansible')
        lines = self._client.api.exec_start(exec_id['Id'], stream=True)
        ret = {'Running': True, 'ExitCode': 0}
        while ret['Running']:
            ret = self._client.api.exec_inspect(exec_id['Id'])
            for line in lines:
                print(line.decode('utf-8'))
        if ret['ExitCode'] != 0:
            raise RuntimeError('Failed to download repository')

        temp_fd = BytesIO()
        with tarfile.TarFile(fileobj=temp_fd, mode='w') as tar_fd:
            tar_fd.add(repo_dir, arcname='.')
        temp_fd.seek(0)

        self._logger.info('transferring config files to container')
        container_obj.put_archive('/home/ansible', temp_fd)
        temp_fd.close()

        exec_id = self._client.api.exec_create(
            container_obj.name,
            ['ansible-playbook', playbook_name],
            workdir='/home/ansible')
        lines = self._client.api.exec_start(exec_id['Id'], stream=True)
        ret = {'Running': True, 'ExitCode': 0}
        while ret['Running']:
            ret = self._client.api.exec_inspect(exec_id['Id'])
            for line in lines:
                print(line.decode('utf-8'))

        self._logger.info('stopping container...')
        container_obj.kill()

        return ret['ExitCode']
    # run()
# EnvDocker()
