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
    def unit_test(self):
        """
        Run a container from the image to perform unit testing.
        """
        # start the container with a hanging command so that it does not exit
        docker_cmd = self._gen_docker_cmd(
            'run', args='--rm -v $PWD:/root/tessia-server:ro',
            cmd='bash -c "cd /root/tessia-server && tools/run_pylint.py && '
                'tools/run_tests.py && tools/run_pytest_tests.py"'
        )
        ret_code, output = self._session.run(docker_cmd)
        if ret_code != 0:
            raise RuntimeError(
                'failed to run unit tests: {}'.format(output))
    # unit_test()

# DockerImageServer
