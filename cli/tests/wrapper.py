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
Helper to encapsulate the execution of a python testcase executor class
"""

#
# IMPORTS
#
from util.static_executor import StaticExecutor
import os
import sys
import traceback

#
# CONSTANTS AND DEFINITIONS
#
MY_DIR = os.path.dirname(os.path.abspath(__file__))

#
# CODE
#

def _run(testcase, server_url):
    """
    Wrap the testcase file in the python executor class and run it

    Args:
        testcase (str): path of testcase
        server_url (str): url where api is running

    Returns:
        int: 0 if test succeeded, 1 otherwise
    """
    executor = StaticExecutor(testcase, server_url)
    print("[run] testcase '{}'".format(testcase))
    ret_code = 0
    try:
        executor.run()
    except Exception:
        ret_code = 1
        print("[stop] caught exception")
        traceback.print_exc()

    print("[cleanup] testcase '{}'".format(testcase))
    try:
        executor.cleanup()
    except Exception:
        print('[cleanup] warning: cleanup failed')
        traceback.print_exc()
        ret_code = 1

    print("[end] testcase '{}'".format(testcase))
    return ret_code
# _run()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise RuntimeError('Missing arguments')
    sys.exit(_run(*(sys.argv[1:]), **{}))
