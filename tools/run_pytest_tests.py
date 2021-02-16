#!/usr/bin/env python3
# Copyright 2021 IBM Corp.
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
Wrapper script to execute unit tests
"""

#
# IMPORTS
#
from tempfile import NamedTemporaryFile
from tessia.server.config import CONF

import os
import subprocess
import sys

#
# CONSTANTS AND DEFINITIONS
#
CMD_RUN_PYTEST = "python3 -m pytest {}"

#
# CODE
#
def main():
    """
    Execute pytest command

    Args:
        None

    Returns:
        int: exit code from pytest shell command

    Raises:
        None
    """
    # determine repository's root dir
    my_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.abspath('{}/..'.format(my_dir))
    os.chdir(lib_dir)

    cmds = []

    # execute all tests
    cmds.append(CMD_RUN_PYTEST.format('tests_pytest'))

    if not os.environ.get('TESSIA_DB_TEST_URI'):
        try:
            test_db_url = CONF.get_config().get('db')['test_url']
            os.environ['TESSIA_DB_TEST_URI'] = test_db_url
        except KeyError:
            pass

    # given that many modules can use the config module it's possible that some
    # tests fail to appropriately mock all the necessary modules which will
    # cause them to 'leak' and eventually use a config file from the
    # filesystem, which might lead to unexpected/unwanted results. To prevent
    # that we set an env variable pointing to an empty config file so that
    # any 'leaked' modules will reach this file instead of a random file from
    # the filesystem.
    temp_file = NamedTemporaryFile()
    os.environ['TESSIA_CFG'] = temp_file.name

    # show command line to user
    cmd = ' && '.join(cmds)
    print(cmd)

    # execute and return exit code
    return subprocess.call(cmd, shell=True)
# main()

if __name__ == '__main__':
    sys.exit(main())
