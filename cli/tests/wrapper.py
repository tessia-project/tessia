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
Helper to encapsulate the execution of a test fixture
"""

#
# IMPORTS
#
from importlib.machinery import SourceFileLoader

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

def _run(fixture_name, data_url, server_url):
    """
    Dynamically imports the module containing the fixture and run it

    Args:
        fixture_name (str): name of fixture
        data_url (str): url where fixture variable data can be found
        server_url (str): url where api is running

    Returns:
        int: 0 if test succeeded, 1 otherwise
    """
    module_path = '{}/fixtures/{}.py'.format(MY_DIR, fixture_name)
    module_name = 'tests.fixtures.{}'.format(fixture_name)

    module = SourceFileLoader(module_name, module_path).load_module()
    obj = module.Fixture(data_url=data_url, server_url=server_url)
    print("[run] fixture '{}'".format(fixture_name))
    ret_code = 0
    try:
        obj.run()
    except Exception:
        ret_code = 1
        print("[stop] caught exception")
        traceback.print_exc()

    if hasattr(obj, 'cleanup'):
        print("[cleanup] fixture '{}'".format(fixture_name))
        try:
            obj.cleanup()
        except Exception:
            print('[cleanup] warning: cleanup failed')
            traceback.print_exc()
            ret_code = 1

    print("[end] fixture '{}'".format(fixture_name))
    return ret_code
# _run()

if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise RuntimeError('Missing arguments')
    sys.exit(_run(*(sys.argv[1:])))
