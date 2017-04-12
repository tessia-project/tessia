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
Module specialized in handling the tessia-engine image.
"""

#
# IMPORTS
#
from lib.image import DockerImage

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class DockerImageEngine(DockerImage):
    """
    Specialized class for dealing with the tessia-engine image
    """
    def _prepare_context(self, work_dir):
        """
        Prepare the context directory in the work dir of the builder

        Args:
            work_dir (str): path to work dir

        Returns:
            str: path to the context dir created

        Raises:
            RuntimeError: in case the git repo copy fails
        """
        # let the base class do it's work
        context_dir = super()._prepare_context(work_dir)

        # add the specific bits: we need to download the tessia_baselib repository
        self._logger.info(
            '[image-build] downloading tessia_baselib to context dir')

        ret_code, output = self._session.run('cat {}/baselib_url'.format(
            context_dir))
        if ret_code != 0:
            raise RuntimeError(
                'Failed to determine tessia_baselib source url: {}'.format(output))
        baselib_url = output.strip()

        ret_code, output = self._session.run(
            'git clone {} {}/assets/tessia_baselib.git'.format(
                baselib_url, context_dir))
        if ret_code != 0:
            raise RuntimeError(
                'Failed to download tessia_baselib source: {}'.format(output))

        return context_dir
    # _prepare_context()

    def lint(self):
        """
        Run a container with the image to perform lint verification.
        """
        self._logger.info(
            '[lint-check] executing tools/run_pylint.py on %s',
            self._image_name)
        cmd = self._gen_docker_cmd(
            'run',
            args='--entrypoint /assets/tessia-engine/tools/run_pylint.py')
        ret_code, _ = self._session.run(cmd, stdout=True)
        if ret_code != 0:
            raise RuntimeError('lint check for {} failed'.format(
                self._image_name))
    # lint()

    def unit_test(self):
        """
        Run a container with the image to perform unit testing.
        """
        self._logger.info(
            '[unittest-run] executing tools/run_tests.py on %s',
            self._image_name)
        cmd = self._gen_docker_cmd(
            'run',
            args='--entrypoint /assets/tessia-engine/tools/run_tests.py')
        ret_code, _ = self._session.run(cmd, stdout=True)
        if ret_code != 0:
            raise RuntimeError('unit test for {} failed'.format(
                self._image_name))
    # unit_test()
# DockerImageEngine
