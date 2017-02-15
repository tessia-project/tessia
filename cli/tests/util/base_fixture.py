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
Base class for all fixtures classes
"""

#
# IMPORTS
#
from click.testing import CliRunner
from tessia_cli import main
from urllib.parse import urlsplit

import abc
import json
import os
import re
import requests
import shlex
import sys
import yaml

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class BaseFixture(object):
    """
    This class provides basic functionality for all classes implementing a
    test fixture
    """
    @abc.abstractmethod
    def __init__(self, data_url, server_url, module_path):
        """
        Initialization
        """
        self._cmds_map = {}
        self._data = self._fetch_data(module_path, data_url)
        self._server_url = server_url
        self._runner = CliRunner()

        # set address for api server
        self.invoke(
            'conf set-server ' + server_url,
            'Server successfully configured.'
        )

        self.switch_user(self._data['base_user'], 'somepassword')
    # __init__()

    def _fetch_data(self, module_path, data_url):
        """
        Retrieve the corresponding data file
        """
        fixture_name = re.sub('.py[co]?$', '', os.path.basename(module_path))

        file_url = '{}/{}.yaml'.format(data_url, fixture_name)
        try:
            file_content = yaml.load(self._read_file(file_url))
        except FileNotFoundError:
            file_url = '{}/{}.json'.format(data_url, fixture_name)
            file_content = json.loads(self._read_file(file_url))

        # TODO: validate against a schema

        return file_content
    # _fetch_data()

    @staticmethod
    def _read_file(data_url):
        """
        Download the file specified by the url and return its contents.
        """
        parsed_url = urlsplit(data_url)
        if parsed_url.scheme == 'file':
            with open(parsed_url.path, 'r') as file_fd:
                file_content = file_fd.read()
        elif parsed_url.scheme in ['http', 'https']:
            response = requests.get(data_url)
            if response.status_code == 400:
                raise FileNotFoundError()
            file_content = response.text
        else:
            raise RuntimeError(
                'Unsupported url scheme {}'.format(parsed_url.scheme))

        return file_content
    # _read_file()

    def invoke(self, cmd_str, assert_msg=None, check=True, **extra):
        """
        Convenient method to call and validate if a result from client
        invocation was as expected.

        Args:
            cmd_str (str): command to execute
            assert_msg (str): when specified, regex to validate output
            check (bool): whether to check the exit code
            extra (dict): parameters to be passed directly to command function

        Returns:
            None

        Raises:
            Exception: exception raised by the command function
            AssertionError: if regex (when specified) does not match output
        """
        print('[cmd] ' + cmd_str)
        parts = shlex.split(cmd_str)
        # small tweak - add attribute to pretend our function is a click
        # command
        main.name = 'main'
        # mock argv so click will grab the arguments from cmd_str
        orig_argv = sys.argv
        sys.argv = ['tessia'] + parts
        # call click to execute the client
        result = self._runner.invoke(main, **extra)
        # restore argv
        sys.argv = orig_argv

        print('[output] ' + result.output)

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

    @abc.abstractmethod
    def run(self):
        """
        Entry point to start execution, must be defined by concrete classes.
        """
        pass
    # run()

    def switch_user(self, user, passwd):
        """
        Convenience method to switch to the specified user
        """
        # generate auth token
        input_prompt = "{}\n{}\n".format(user, passwd)
        self.invoke(
            'conf key-gen',
            'Key successfully created and added to client configuration.',
            input=input_prompt
        )
    # switch_user()
# BaseFixture
