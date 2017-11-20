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
Module specialized in handling the tessia-server image.
"""

#
# IMPORTS
#
from lib.image import DockerImage
import os

#
# CONSTANTS AND DEFINITIONS
#
MY_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath('{}/../../..'.format(MY_DIR))

#
# CODE
#
class DockerImageServer(DockerImage):
    """
    Specialized class for dealing with the tessia-server image
    """
    def _prepare_context(self, git_name, work_dir):
        """
        Prepare the context directory in the work dir of the builder

        Args:
            git_name (str): repository name where source code is located
            work_dir (str): path to work dir

        Returns:
            str: path to the context dir created

        Raises:
            RuntimeError: in case the git repo copy fails
        """
        # let the base class do it's work
        context_dir = super()._prepare_context(git_name, work_dir)

        # add the specific bits: we need to download the tessia-baselib repo
        self._logger.info(
            '[build] downloading tessia-baselib to context dir')

        ret_code, output = self._session.run(
            "grep 'egg=tessia-baselib' {}/requirements.txt".format(ROOT_DIR))
        if ret_code != 0:
            raise RuntimeError(
                'Failed to determine tessia-baselib source url: {}'
                .format(output))
        baselib_url = output.strip().rsplit('@', 1)[0]

        ret_code, output = self._session.run(
            'git clone --mirror {} {}/assets/tessia-baselib.git'.format(
                baselib_url, context_dir))
        if ret_code != 0:
            raise RuntimeError(
                'Failed to download tessia-baselib source: {}'.format(output))

        return context_dir
    # _prepare_context()

    def unit_test(self):
        """
        Run a container from the image to perform unit testing.
        """
        # start the container with a hanging command so that it does not exit
        docker_cmd = self._gen_docker_cmd(
            'run', args='-d', cmd='tail -f /dev/null')
        ret_code, output = self._session.run(docker_cmd)
        if ret_code != 0:
            raise RuntimeError(
                'failed to start unittest container: {}'.format(output))

        try:
            # pipe the tar file from the repo to a tar cmd reading from stdin
            # in the container
            repo_dir = '/root/{}'.format(self._name)
            cmd = (
                "bash -c '{ mkdir " + repo_dir + " && "
                "tar -C " + repo_dir + " -xf -; }'"
            )
            docker_cmd = self._gen_docker_cmd('exec', args='-i', cmd=cmd)
            ret_code, output = self._session.run(
                "git archive HEAD | {}".format(docker_cmd))
            if ret_code != 0:
                raise RuntimeError(
                    'failed to copy repo to container: {}'.format(
                        output))

            # run the lint and unit test commands
            cmd = (
                "bash -c 'cd {} && tools/run_pylint.py && "
                "tools/run_tests.py'".format(repo_dir))
            docker_cmd = self._gen_docker_cmd('exec', cmd=cmd)
            ret_code, output = self._session.run(docker_cmd)
            if ret_code != 0:
                raise RuntimeError(
                    'failed to run unit tests: {}'.format(output))
        finally:
            # stop and remove the container
            ret_code, output = self._session.run(
                self._gen_docker_cmd('rm', args='-f'))
            if ret_code != 0:
                self._logger.warning(
                    '[unittest] failed to remove container: %s', output)

    # unit_test()

# DockerImageServer
