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
    def __init__(self, image_name, image_tag, prod_build, session, git_name):
        """
        Constructor, store values (usually provided by manager)

        Args:
            image_name (str): docker image name
            image_tag (str): docker image tag
            prod_build (bool): whether to build for production
            session (Session): object conected to builder system
            git_name (str): name of source git repository
        """
        self._logger = logging.getLogger(__name__)
        # docker image name
        self._image_name = image_name
        # docker image tag
        self._image_tag = image_tag
        # whether it's a production build
        self._prod_build = prod_build
        # open session to the build machine
        self._session = session
        # git repository name where source code is located
        self._git_name = git_name
    # __init__()

    def _gen_docker_cmd(self, action, args='', context_dir=None):
        """
        Helper method to generate docker command strings

        Args:
            action (str): build, run
            args (str): additional arguments to include in cmd string
            context_dir (str): path of context dir, mandatory for build action

        Returns:
            str: command string

        Raises:
            RuntimeError: in case of missing parameters
        """
        cmd = ''
        if action == 'build':
            if context_dir is None:
                raise RuntimeError(
                    'cannot generate docker build string without context dir')

            docker_build = (
                'docker build --force-rm --build-arg prod_build={prod_build} '
                '-t {image_name}:{image_tag} {args} {context_dir}'
            )
            cmd = docker_build.format(
                prod_build=str(self._prod_build).lower(),
                image_name=self._image_name,
                image_tag=self._image_tag,
                context_dir=context_dir,
                args=args
            )
        elif action == 'run':
            docker_run = (
                'docker run -t --rm --name {container_name} {args} '
                '{image_name}'
            )
            cmd = docker_run.format(
                container_name=self._image_name,
                image_name='{}:{}'.format(self._image_name, self._image_tag),
                args=args
            )

        return cmd
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
        self._logger.info('[image-build] build start at %s', context_dir)
        ret_code, output = self._session.run(cmd)
        if ret_code != 0:
            raise RuntimeError('build of {} failed: {}'.format(
                self._image_name, output))
    # _exec_build()

    def _prepare_context(self, work_dir):
        """
        Prepare the context directory in the work dir of the builder

        Args:
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
            '[image-build] preparing context dir at %s', context_dir)
        # send the content from source docker dir to target context dir
        self._session.send(docker_dir, work_dir)
        ret_code, output = self._session.run('cp {}/{}.git {}/assets/'.format(
            work_dir, self._git_name, context_dir))
        if ret_code != 0:
            raise RuntimeError(
                'Failed to copy git bundle to context dir: {}'.format(output))

        return context_dir
    # _prepare_context()

    def build(self, work_dir):
        """
        Use the passed work directory as staging area to store the context and
        start the image build.

        Args:
            work_dir (str): path to work dir in builder
        """
        context_dir = self._prepare_context(work_dir)
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
                '[clean-up] failed to list containers for %s: %s',
                image_fullname,
                output)
        else:
            containers = output.replace('\n', ' ').strip()
            # containers found: delete them
            if len(containers) > 0:
                ret_code, output = self._session.run(
                    'docker rm -v {}'.format(containers)
                )
                if ret_code != 0:
                    self._logger.warning(
                        '[clean-up] failed to remove containers for %s: %s',
                        image_fullname,
                        output)

        # delete the image (use --no-prune to keep parent layers so that they
        # can be used as cache for other builds)
        ret_code, output = self._session.run(
            'docker rmi --no-prune {}'.format(image_fullname))
        if ret_code != 0:
            self._logger.warning(
                '[clean-up] failed to remove image %s: %s',
                image_fullname,
                output)
    # cleanup()

    def deploy(self):
        """
        Deploy the image on the controller. To be implemented.
        """
        pass
    # deploy()

    def int_test(self):
        """
        Run a container from the image to perform integration testing. Does
        nothing by default.
        """
        pass
    # int_test()

    def lint(self):
        """
        Run a container from the image to perform lint verification. Does
        nothing by default.
        """
        pass
    # lint()

    def unit_test(self):
        """
        Run a container from the image to perform unit testing. Does nothing
        by default.
        """
        pass
    # unit_test()
# DockerImage
