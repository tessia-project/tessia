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
Test executor of yaml based testcase files
"""

#
# IMPORTS
#
from click.testing import CliRunner
from tessia.cli import main

import jsonschema
import os
import re
import shlex
import sys
import yaml

#
# CONSTANTS AND DEFINITIONS
#
MY_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.abspath('{}/../static_testcases'.format(MY_DIR))
# the allowed schema for yaml static testcase files
STATIC_SCHEMA = {
    'type': 'object',
    'properties': {
        'base_user': {
            'type': 'string'
        },
        'cleanup': {
            'type': 'array',
            'items': {
                'type': 'string'
            }
        },
        'description': {
            'type': 'string'
        },
        'tasks': {
            'type': 'object',
            'additionalProperties': {
                'type': 'array',
                'items': {
                    'anyOf': [
                        # a single command, no output expected
                        {
                            'type': 'string'
                        },
                        # a list with [command_or_inputlist, output_regex]
                        {
                            'type': 'array',
                            'items': [
                                {
                                    'anyOf': [
                                        # single command (no further input)
                                        {
                                            'type': 'string'
                                        },
                                        # command and input entries (i.e. for
                                        # entering user and password)
                                        {
                                            'type': 'array',
                                            'items': {
                                                'type': 'string'
                                            },
                                            'minItems': 2,
                                        }
                                    ],
                                },
                                # the expected output regex
                                {
                                    'type': 'string'
                                }
                            ],
                            # in order to assure exactly 2 items are specified
                            'minItems': 2,
                            'maxItems': 2,
                        }
                    ],
                },
            },
        },
        'tasks_order': {
            'type': 'array',
            'items': {
                'type': 'string'
            },
            'minItems': 1,
        },
    },
    'required': [
        'base_user',
        'description',
        'tasks',
        'tasks_order',
    ],
    'additionalProperties': False
}

#
# CODE
#
class StaticExecutor(object):
    """
    This class provides functionality to parse a yaml file (known as static
    testcase) and execute its content.
    """
    def __init__(self, testcase, server_url):
        """
        Initialization, load yaml file and perform initial client configuration

        Args:
            testcase (str): name
            server_url (str): API server url
        """
        self._cmds_map = {}
        self._data = self.load_testcase(testcase)
        self._server_url = server_url
        self._runner = CliRunner()

        # set address for api server
        self.invoke(
            'conf set-server ' + server_url,
            'Server successfully configured.'
        )

        self.switch_user(self._data['base_user'], 'somepassword')
    # __init__()

    @staticmethod
    def _print(*args, **kwargs):
        """
        Simple wrapper for 'print' built-in to enable flush by default
        """
        if 'flush' not in kwargs:
            # by default force line to be flushed right away to provide better
            # user feedback
            kwargs['flush'] = True

        print(*args, **kwargs)
    # _print()

    def cleanup(self):
        """
        Process the cleanup statements
        """
        try:
            statements = self._data['cleanup']
        except KeyError:
            statements = []

        for statement in statements:
            self.exec_statement(statement)
    # cleanup()

    def exec_statement(self, statement):
        """
        Process and execute a statement entry
        """
        # statement has output regex specified: use it
        if isinstance(statement, list):
            # exception will not happen as input was validated by schema
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
    # exec_statement()

    @staticmethod
    def load_testcase(test_path):
        """
        Retrieve and load the yaml testcase file

        Args:
            test_path (str): testcase's file location

        Returns:
            str: testcase content

        Raises:
            SyntaxError: if tasks_order entry is invalid
        """
        with open(test_path, 'r') as file_fd:
            testcase = yaml.load(file_fd.read())

        try:
            jsonschema.validate(testcase, STATIC_SCHEMA)
        # in case of validation error print a nice error message to the user
        except jsonschema.exceptions.ValidationError as exc:
            print('file {}: {}'.format(test_path, exc.message),
                  file=sys.stderr)
            sys.exit(1)

        # make sure all tasks listed in the order list are really defined
        for task in testcase['tasks_order']:
            if not task in testcase['tasks']:
                raise SyntaxError(
                    "Task '{}' present in tasks_order but not defined".format(
                        task))

        return testcase
    # load_testcase()

    def invoke(self, cmd_str, assert_msg=None, check=True, **extra):
        """
        Convenient method to call and validate if a result from client
        invocation was as expected.

        Args:
            cmd_str (str): command to execute
            assert_msg (str): when specified, regex to validate output
            check (bool): whether to check the exit code
            extra (dict): parameters to be passed directly to command function

        Raises:
            exc: exception raised by the command function
            AssertionError: if regex (when specified) does not match output
        """
        # force line to be flushed right away to provide better user feedback
        self._print('[cmd] ' + cmd_str)
        parts = shlex.split(cmd_str)
        # small tweak - add attribute to pretend our function is a click
        # command
        main.name = 'main'
        # mock argv to make click grab the arguments from cmd_str
        orig_argv = sys.argv
        sys.argv = ['tess'] + parts
        # call click to execute the client
        result = self._runner.invoke(main, **extra)
        # restore argv
        sys.argv = orig_argv

        self._print('[output] ' + result.output)

        if check and result.exit_code != 0:
            exc = AssertionError(
                "expected exit_code 0 != {}\ncommand: <{}>\n"
                "output: <{}>".format(result.exit_code, cmd_str, result.output)
            )
            if result.exception is not None:
                raise exc from result.exception
            raise exc
        elif (result.exception is not None and not
              isinstance(result.exception, SystemExit)):
            raise result.exception
        if assert_msg is not None:
            assert re.search(assert_msg, result.output) is not None, \
                    'output does not match assertion regex'
    # invoke()

    def run(self):
        """
        Entry point to start execution
        """
        tasks = self._data['tasks_order']

        for task in tasks:
            self._print("[exec-task] '{}'".format(task))
            for statement in self._data['tasks'][task]:
                self.exec_statement(statement)
    # run()

    def switch_user(self, user, passwd):
        """
        Convenient method to switch client config to the specified user
        """
        # generate auth token
        input_prompt = "{}\n{}\n".format(user, passwd)
        self.invoke(
            'conf key-gen',
            'Key successfully created and added to client configuration.',
            input=input_prompt
        )
    # switch_user()
# StaticExecutor
