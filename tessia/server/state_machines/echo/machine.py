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
from tessia.server.config import CONF
from tessia.server.state_machines.base import BaseMachine
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
    def __init__(self, params):
        """
        See base class docstring
        """
        super(EchoMachine, self).__init__(params)

        self._params = self.parse(params)
    # __init__()

    @staticmethod
    def _execute_commands(commands):
        for cmd in commands:
            if cmd[0] == 'echo':
                print(cmd[1])
            elif cmd[0] == 'sleep':
                sleep(cmd[1])
            elif cmd[0] == 'return':
                return cmd[1]
            elif cmd[0] == 'raise':
                raise RuntimeError

        return 0

    def cleanup(self):
        """
        See base class docstring
        """
        if self._params['cleanup_commands']:
            self.cleaning_up = True
            return self._execute_commands(self._params['cleanup_commands'])
        return 0
    # cleanup()

    @classmethod
    def parse(cls, content):
        """
        Parse an echo-format content. The syntax is one statement per line,
        which can be a system allocation, a message to be echoed, or a sleep.
        Example:
        VERBOSITY DEBUG
        USE SHARED lpar01
        USE EXCLUSIVE guest01 guest02
        ECHO Hello world!
        SLEEP 50
        ECHO Test ended.
        CLEANUP
        ECHO cleanup started
        SLEEP 2
        ECHO cleanup done

        Args:
            content (str): the content to be parsed

        Returns:
            dict: containing resources allocated and list of commands
                  to be executed

        Raises:
            SyntaxError: if content is in wrong format
            ValueError: if wrong verbosity level is specified
        """

        ret = {
            'resources': {'shared': [], 'exclusive': []},
            'description': MACHINE_DESCRIPTION,
            'commands': [],
            'cleanup_commands': []
        }

        cleanup = False
        commands = ret['commands']

        lines = content.split('\n')
        for index, line in enumerate(lines):
            fields = line.split('#', 1)[0].split()

            # empty line or comments: skip it
            if not fields:
                continue

            if fields[0].lower() == 'cleanup':
                cleanup = True
                commands = ret['cleanup_commands']

            elif fields[0].lower() == 'use':

                if cleanup:
                    raise SyntaxError(
                        'USE statement in cleanup section.')

                # syntax check
                if len(fields) < 3:
                    raise SyntaxError(
                        'Wrong number of arguments in USE statement at '
                        'line {}'.format(index+1))

                try:
                    ret['resources'][fields[1].lower()].extend(fields[2:])
                except KeyError:
                    raise SyntaxError(
                        'Invalid mode {} in USE statement at line {}'.format(
                            fields[1].lower(), index+1))

            elif fields[0].lower() == 'echo':
                # syntax check
                if len(fields) < 2:
                    raise SyntaxError(
                        'Wrong number of arguments in ECHO statement at line '
                        '{}'.format(index+1))

                commands.append(['echo', ' '.join(fields[1:])])

            elif fields[0].lower() == 'sleep':
                if len(fields) != 2:
                    raise SyntaxError(
                        'Wrong number of arguments in '
                        'SLEEP statement at line '
                        '{}'.format(index+1))
                try:
                    seconds = int(fields[1])
                except ValueError:
                    raise SyntaxError(
                        'SLEEP argument must be a number at line {}'
                        .format(index+1))

                commands.append(['sleep', seconds])

            elif fields[0].lower() == 'return':
                if len(fields) != 2:
                    raise SyntaxError(
                        'Wrong number of arguments in RETURN '
                        'statement at line '
                        '{}'.format(index+1))
                try:
                    ret_value = int(fields[1])
                except ValueError:
                    raise SyntaxError(
                        'RETURN argument must be a number at line {}'
                        .format(index+1))

                commands.append(['return', ret_value])

            elif fields[0].lower() == 'raise':
                commands.append(['raise'])

            elif fields[0].lower() == 'verbosity':
                if index != 0:
                    raise SyntaxError(
                        'VERBOSITY statement must come in first line.')

                if fields[1] not in cls._LOG_LEVELS:
                    raise ValueError(
                        "Verbosity '{}' is invalid, choose from {}".format(
                            fields[1], ', '.join(cls._LOG_LEVELS)))

                CONF.log_config(conf=cls._LOG_CONFIG, log_level=fields[1])

            else:
                raise SyntaxError('Invalid command {} at line {}'.format(
                    fields[0], index+1))

        return ret
    # parse()

    def start(self):
        """
        The state machine itself which processes the instructions and executes
        them.

        Returns:
            int: exit code

        Args:
        """

        ret = self._execute_commands(self._params['commands'])
        ret_cleanup = self.cleanup()

        if not ret_cleanup:
            return ret

        return ret_cleanup
    # start()

# EchoMachine
