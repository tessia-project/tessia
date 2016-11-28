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
Simple state machine which echoes the messages specified.
"""

#
# IMPORTS
#
from tessia_engine.state_machines.base import BaseMachine
from time import sleep

#
# CONSTANTS AND DEFINITIONS
#
MACHINE_DESCRIPTION = 'Echo executor'

#
# CODE
#
class EchoMachine(BaseMachine):
    """
    Simple state machine which echoes the messages specified.
    """
    NAME = 'echo'

    def __init__(self, params):
        """
        See base class docstring
        """
        super(EchoMachine, self).__init__(params)

        self._params = self.parse(params)
    # __init__()

    def cleanup(self):
        """
        See base class docstring
        """
        print('cleanup done')
    # cleanup()

    @staticmethod
    def parse(content):
        """
        Parse an echo-format content. The syntax is one statement per line,
        which can be a system allocation, a message to be echoed, or a sleep.
        Example:
        USE SHARED lpar01
        USE EXCLUSIVE guest01 guest02
        ECHO Hello world!
        SLEEP 50
        ECHO Test ended.

        Args:
            content (str): the content to be parsed

        Returns:
            dict: containing resources allocated and list of messages to be
                  echoed

        Raises:
            SyntaxError: if content is in wrong format
        """

        ret = {
            'resources': {'shared': [], 'exclusive': []},
            'description': MACHINE_DESCRIPTION,
            'commands': [],
        }

        lines = content.split('\n')
        for i in range(0, len(lines)):
            fields = lines[i].split('#', 1)[0].split()

            # empty line or comments: skip it
            if len(fields) == 0:
                continue

            if fields[0].lower() == 'use':
                # syntax check
                if len(fields) < 3:
                    raise SyntaxError(
                        'Wrong number of arguments in USE statement at '
                        'line {}'.format(i+1))

                try:
                    ret['resources'][fields[1].lower()].extend(fields[2:])
                except KeyError:
                    raise SyntaxError(
                        'Invalid mode {} in USE statement at line {}'.format(
                            fields[1].lower(), i+1))

            elif fields[0].lower() == 'echo':
                # syntax check
                if len(fields) < 2:
                    raise SyntaxError(
                        'Wrong number of arguments in ECHO statement at line '
                        '{}'.format(i+1))
                ret['commands'].append(['echo', ' '.join(fields[1:])])

            elif fields[0].lower() == 'sleep':
                if len(fields) != 2:
                    raise SyntaxError(
                        'Wrong number of arguments in SLEEP statement at line '
                        '{}'.format(i+1))
                try:
                    seconds = int(fields[1])
                except ValueError:
                    raise SyntaxError(
                        'SLEEP argument must be a number at line {}'.format(
                            i+1))

                ret['commands'].append(['sleep', seconds])

            else:
                raise SyntaxError('Invalid command {} at line {}'.format(
                    fields[0], i+1))

        return ret
    # parse()

    def start(self):
        """
        The state machine itself which processes the instructions and executes
        them.

        Returns:
            int: exit code
        """
        for cmd in self._params['commands']:
            if cmd[0] == 'echo':
                print(cmd[1])
            elif cmd[0] == 'sleep':
                sleep(cmd[1])

        return 0
    # start()

# EchoMachine
