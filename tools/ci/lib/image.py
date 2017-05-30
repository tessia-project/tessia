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
Module containing the class used to represent a docker image
"""

#
# IMPORTS
#
import logging
import os

#
# CONSTANTS AND DEFINITIONS
#
MY_DIR = os.path.dirname(os.path.abspath(__file__))
DOCKER_DIR = os.path.abspath('{}/../docker'.format(MY_DIR))

#
# CODE
#
class DockerImage(object):
    """
    Represents a docker image to build, test, deploy
    """
    def __init__(self, image_name, image_tag, session):
        """
        Constructor, store values (usually provided by manager)

        Args:
            image_name (str): docker image name
            image_tag (str): docker image tag
            session (Session): object connected to builder system
        """
        self._logger = logging.getLogger(__name__)
        # docker image name
        self._image_name = image_name
        # docker image tag
        self._image_tag = image_tag
        # open session to the build machine
        self._session = session
    # __init__()

    def _gen_docker_cmd(self, action, args='', cmd='', context_dir=None):
        """
        Helper method to generate docker command strings

        Args:
            action (str): build, exec, rm, run
            args (str): additional arguments to include in cmd string
            cmd (str): for actions 'run' and 'exec', define cmd to execute
            context_dir (str): path of context dir, mandatory for build action

        Returns:
            str: command string

        Raises:
            RuntimeError: in case of missing parameters
        """
        docker_cmd = ''
        container_name = '{name}-{tag}'.format(
            name=self._image_name, tag=self._image_tag)
        image_name = '{}:{}'.format(self._image_name, self._image_tag)
        if action == 'build':
            if context_dir is None:
                raise RuntimeError(
                    'cannot generate docker build string without context dir')

            docker_build = (
                'docker build --force-rm -t {image_name} {args} '
                '{context_dir}'
            )
            docker_cmd = docker_build.format(
                image_name=image_name,
                image_tag=self._image_tag,
                context_dir=context_dir,
                args=args
            )
        elif action == 'run':
            docker_run = (
                'docker run -t --name {container_name} {args} '
                '{image_name} {cmd}'
            )
            docker_cmd = docker_run.format(
                container_name=container_name,
                image_name=image_name,
                args=args,
                cmd=cmd
            )
        elif action == 'exec':
            docker_cmd = (
                'docker exec {args} {container_name} {cmd}'.format(
                    container_name=container_name, args=args, cmd=cmd)
            )
        elif action == 'rm':
            docker_cmd = (
                'docker rm {args} {container_name}'.format(
                    args=args, container_name=container_name)
            )

        return docker_cmd
    # _gen_docker_cmd()

    def _exec_build(self, context_dir):
        """
        Execute the actual docker build action.

        Args:
            context_dir (str): context directory to use for build

        Raises:
            RuntimeError: in case build process fails
        """
        cmd = self._gen_docker_cmd('build', context_dir=context_dir)
        self._logger.info('[build] build start at %s', context_dir)
        ret_code, output = self._session.run(cmd)
        if ret_code != 0:
            raise RuntimeError('build of {} failed: {}'.format(
                self._image_name, output))
    # _exec_build()

    def _prepare_context(self, git_name, work_dir):
        """
        Prepare the context directory in the work dir of the builder

        Args:
            git_name (str): repository name where source code is located
            work_dir (str): path to work dir

        Returns:
            str: path of the context dir created

        Raises:
            RuntimeError: in case the git repo copy fails
        """
        # source dir containing DockerFile
        docker_dir = '{}/{}'.format(DOCKER_DIR, self._image_name)
        # target location for context dir
        context_dir = '{}/{}'.format(work_dir, self._image_name)
        self._logger.info(
            '[build] preparing context dir at %s', context_dir)
        # send the content from source docker dir to target context dir
        self._session.send(docker_dir, work_dir)
        ret_code, output = self._session.run(
            'git clone {}/{}.git {}/assets/{}.git'.format(
                work_dir, git_name, context_dir, git_name))
        if ret_code != 0:
            raise RuntimeError(
                'Failed to copy git bundle to context dir: {}'.format(output))

        return context_dir
    # _prepare_context()

    def build(self, git_name, work_dir):
        """
        Use the passed work directory as staging area to store the context and
        start the image build.

        Args:
            git_name (str): repository name where source code is located
            work_dir (str): path to work dir in builder
        """
        context_dir = self._prepare_context(git_name, work_dir)
        self._exec_build(context_dir)
    # build()

    def cleanup(self):
        """
        Remove image and containers associated with this image
        """
        # list all containers which have our image as ancestor
        image_fullname = '{}:{}'.format(self._image_name, self._image_tag)
        ret_code, output = self._session.run(
            "docker ps -a -q -f 'ancestor={}'".format(image_fullname),
        )
        if ret_code != 0:
            self._logger.warning(
                '[cleanup] failed to list containers for %s: %s',
                image_fullname,
                output)
        else:
            containers = output.replace('\n', ' ').strip()
            # containers found: delete them
            if containers:
                ret_code, output = self._session.run(
                    'docker rm -v {}'.format(containers)
                )
                if ret_code != 0:
                    self._logger.warning(
                        '[cleanup] failed to remove containers for %s: %s',
                        image_fullname,
                        output)

        # delete the image (use --no-prune to keep parent layers so that they
        # can be used as cache for other builds)
        ret_code, output = self._session.run(
            'docker rmi --no-prune {}'.format(image_fullname))
        if ret_code != 0:
            self._logger.warning(
                '[cleanup] failed to remove image %s: %s',
                image_fullname,
                output)
    # cleanup()

    def push(self, registry_url, rel_version):
        """
        Push the image to the docker registry.

        Args:
            registry_url (str): location of docker registry
            rel_version (str): release version used to tag image on registry

        Raises:
            RuntimeError: in case push command fails
        """
        # name of image on builder
        local_name = '{}:{}'.format(self._image_name, self._image_tag)
        # how image will be named on registry
        remote_name = '{}/{}:{}'.format(
            registry_url, self._image_name, rel_version)
        self._logger.info(
            'pushing image %s to %s', local_name, remote_name)

        ret_code, output = self._session.run(
            'docker tag {local_image} {remote_image} && '
            'docker push {remote_image}'.format(
                local_image=local_name, remote_image=remote_name)
        )
        # regardless of success or failure, remove the tag created
        rm_code, rm_output = self._session.run(
            'docker rmi {}'.format(remote_name))
        if rm_code != 0:
            self._logger.warning(
                'failed to remove remote tag: %s', rm_output)
        # push operation failed: report error
        if ret_code != 0:
            raise RuntimeError('failed to push to registry: {}'.format(output))
    # push()

    def unit_test(self):
        """
        Run a container from the image to perform unit testing. Does nothing
        by default.
        """
        pass
    # unit_test()
# DockerImage
