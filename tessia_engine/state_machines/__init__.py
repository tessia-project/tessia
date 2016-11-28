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
Package containing the state machines used to execute the jobs
"""

#
# IMPORTS
#
from importlib.machinery import SourceFileLoader
import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
def _load_machines():

    # dict containing the state machines loaded
    machines = {}
    my_dir = os.path.dirname(os.path.abspath(__file__))

    for sub_dir in os.listdir(my_dir):
        # not a valid package: skip it
        if sub_dir.startswith('_'):
            continue

        base_path = '{}/{}'.format(my_dir, sub_dir)
        # not a package: skip it
        if not os.path.isdir(base_path) or base_path.startswith('_'):
            continue

        package_path = '{}/__init__.py'.format(base_path)
        package_name = '{}.{}'.format(__name__, sub_dir)

        # syntax error could occur here
        package = SourceFileLoader(package_name, package_path).load_module()

        machines[package.MACHINE.NAME] = package.MACHINE

    return machines
# _load_machines()

MACHINES = _load_machines()
