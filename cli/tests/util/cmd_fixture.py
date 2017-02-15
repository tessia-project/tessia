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
Module for the command based fixture class
"""

#
# IMPORTS
#
from tests.util.base_fixture import BaseFixture

import abc

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class CmdBasedFixture(BaseFixture):
    """
    A utility class for command-based fixtures
    """
    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        """
        Entry point
        """
        try:
            variants = self._data['variants_order']
        except KeyError:
            variants = self._data['variants'].keys()

        for variant in variants:
            print("[exec-variant] '{}'".format(variant))
            for statement in self._data['variants'][variant]:
                # statement has validation regex specified: use it
                if isinstance(statement, list):
                    # let exception be raised in case of invalid input
                    cmd, output_re = statement
                else:
                    cmd = statement
                    output_re = None

                # cmd has input specified: use it
                if isinstance(cmd, list):
                    cmd_str = cmd[0]
                    cmd_input = '\n'.join(cmd[1:])
                else:
                    cmd_str = cmd
                    cmd_input = None
                self.invoke(
                    cmd_str, output_re, check=False, input=cmd_input)

    # run()
# CmdBasedFixture
