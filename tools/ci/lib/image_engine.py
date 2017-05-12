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
import os

#
# CONSTANTS AND DEFINITIONS
#
MY_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath('{}/../../..'.format(MY_DIR))

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

        ret_code, output = self._session.run(
            "grep 'egg=tessia_baselib' {}/requirements.txt".format(ROOT_DIR))
        if ret_code != 0:
            raise RuntimeError(
                'Failed to determine tessia_baselib source url: {}'.format(output))
        baselib_url = output.strip().rsplit('@', 1)[0]

        ret_code, output = self._session.run(
            'git clone {} {}/assets/tessia_baselib.git'.format(
                baselib_url, context_dir))
        if ret_code != 0:
            raise RuntimeError(
                'Failed to download tessia_baselib source: {}'.format(output))

        return context_dir
    # _prepare_context()
# DockerImageEngine
