#!/usr/bin/env python3
# Copyright 2016, 2017 IBM Corp.
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
Wrapper script to execute coverage on unit tests
"""

#
# IMPORTS
#
from tempfile import NamedTemporaryFile
import os
import subprocess
import sys

#
# CONSTANTS AND DEFINITIONS
#
CMD_COVERAGE = (
    "python3 -m coverage run -a --{import_method}={source_path} {subcmd}")
CMD_COVERAGE_ERASE = "python3 -m coverage erase"
CMD_COVERAGE_REPORT = "python3 -m coverage report -m"
SUBCMD_UNITTEST_DISCOVER = "-m unittest discover {} -p '*.py'"
SUBCMD_UNITTEST_MODULE = "-m unittest {}"

#
# CODE
#
def main():
    """
    Process the command line arguments and create the appropriate coverage
    command

    Args:
        None

    Returns:
        int: exit code from coverage shell command

    Raises:
        None
    """
    # determine repository's root dir
    my_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.abspath('{}/..'.format(my_dir))

    # switch to root dir to make sure paths are found
    cmds = ['cd {}'.format(lib_dir)]

    # erase previously collected coverage data
    cmds.append(CMD_COVERAGE_ERASE)

    # no arguments provided: execute all tests
    if len(sys.argv) < 2:
        subcmd_unittest = SUBCMD_UNITTEST_DISCOVER.format('tests/unit')
        cmds.append(CMD_COVERAGE.format(
            import_method='source',
            source_path='tessia_engine',
            subcmd=subcmd_unittest
        ))

    # module path provided: use module's command version
    elif sys.argv[1].endswith('.py'):
        subcmd_unittest = SUBCMD_UNITTEST_MODULE.format(sys.argv[1])
        cmds.append(CMD_COVERAGE.format(
            import_method='include',
            source_path=sys.argv[1].replace("tests/unit", "tessia_engine"),
            subcmd=subcmd_unittest
        ))

    # package path provided: use discover option
    else:
        subcmd_unittest = SUBCMD_UNITTEST_DISCOVER.format(sys.argv[1])
        cmds.append(CMD_COVERAGE.format(
            import_method='source',
            source_path=sys.argv[1].replace("tests/unit", "tessia_engine"),
            subcmd=subcmd_unittest
        ))

    # display report
    cmds.append(CMD_COVERAGE_REPORT)

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
