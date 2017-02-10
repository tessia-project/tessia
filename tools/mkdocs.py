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
Wrapper script to call mkdocs
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

#
# CODE
#
def main():
    """
    Change to doc directory and call mkdocs

    Args:
        None

    Returns:
        int: exit code

    Raises:
        None
    """
    # determine the repository root dir
    root_dir = os.path.abspath(
        '{}/..'.format(os.path.dirname(os.path.abspath(__file__)))
    )

    # no arguments specified: use default
    if len(sys.argv) < 2:
        args = 'build -c -d ../build/html'
    # pass user arguments to mkdocs
    else:
        args = ' '.join(sys.argv[1:])

    # create the command
    cmd = 'cd {} && mkdocs {}'.format(root_dir, args)

    # show command to the user
    print(cmd)

    # execute and return exit code
    return subprocess.call(cmd, shell=True)
# parse_and_run()

if __name__ == '__main__':
    sys.exit(main())
