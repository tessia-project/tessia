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
Wrapper script to execute pylint for code guidelines verification
"""

#
# IMPORTS
#
import os
import subprocess
import sys

#
# CONSTANTS AND DEFINITIONS
#
LINT_CMD = 'python3 -m pylint'

#
# CODE
#
def main():
    """
    Execute pylint with specific configuration file and user provided options

    Args:
        None

    Returns:
        None

    Raises:
        None
    """
    # determine the repository root dir
    my_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.abspath('{}/..'.format(my_dir))

    # use our configuration file
    cmd = '{} --rcfile {}/.pylintrc'.format(LINT_CMD, lib_dir)

    # no arguments provided: check all the files
    if len(sys.argv) < 2:
        cmd += ' {0}/tessia_engine {0}/tests/unit'.format(lib_dir)
    # process arguments and add them to the command
    else:
        # flag to control whether a module path was provided
        path_set = False
        for arg in sys.argv[1:]:
            cmd += ' {}'.format(arg)
            # not a parameter: mark that a module path was provided
            if not arg.startswith('-'):
                path_set = True
        # no module path provided: check all files
        if not path_set:
            cmd += ' {0}/tessia_engine {0}/tests/unit'.format(lib_dir)

    # execute command and return exit code
    return subprocess.call(cmd, shell=True)
# main()

if __name__ == '__main__':
    sys.exit(main())
