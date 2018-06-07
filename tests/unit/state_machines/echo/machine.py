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
Unit test for echo machine module
"""

#
# IMPORTS
#
from tessia.server.state_machines.echo import machine
from unittest import TestCase
from unittest.mock import call
from unittest.mock import patch


#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class TestEcho(TestCase):
    """
    Unit test for the machine module of the echo state machine.
    """

    def setUp(self):
        """
        Prepare the necessary mocks at the beginning of each testcase.
        """
        patcher = patch.object(machine, 'print', autospect=True)
        self._mock_print = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, 'sleep', autospect=True)
        self._mock_sleep = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, 'CONF', autospec=True)
        self._mock_conf = patcher.start()
        self.addCleanup(patcher.stop)

    def test_good_content(self):
        """
        Test the methods with valid content.
        """
        # create a valid content
        lines = (
            'VERBOSITY DEBUG',
            'USE EXCLUSIVE guest01 guest03',
            'USE SHARED lpar01 # our lpar',
            '# an entire line of comment',
            'ECHO Hello world!',
            'ECHO Testing a more long message to see if it works...',
            'SLEEP 20',
            'RETURN 0',
        )
        content = '\n'.join(lines)
        # check the parser method
        result = machine.EchoMachine.parse(content)

        # verify results
        self.assertEqual(result['description'], machine.MACHINE_DESCRIPTION)
        self.assertEqual(result['resources']['shared'], ['lpar01'])
        self.assertEqual(result['resources']['exclusive'],
                         ['guest01', 'guest03'])
        self.assertEqual(
            result['commands'],
            [
                ['echo', 'Hello world!'],
                ['echo', 'Testing a more long message to see if it works...'],
                ['sleep', 20],
                ['return', 0]
            ]
        )

        # check the executor method
        echo_obj = machine.EchoMachine(content)
        ret_code = echo_obj.start()
        self.assertEqual(ret_code, 0)
        self._mock_print.assert_has_calls([
            call('Hello world!'),
            call('Testing a more long message to see if it works...')
        ])
        self._mock_sleep.assert_has_calls([call(20)])
        # check that verbosity was properly set
        self._mock_conf.log_config.assert_called_with(
            conf=machine.EchoMachine._LOG_CONFIG,
            log_level='DEBUG')

    # test_good_content()

    def test_no_return(self):
        """
        Test a normal execution that doesn't return.
        """
        lines = (
            'ECHO Hello world!',
            'SLEEP 20'
        )
        content = '\n'.join(lines)

        echo_obj = machine.EchoMachine(content)
        ret_code = echo_obj.start()

        self.assertEqual(ret_code, 0)

    def test_ok_cleanup(self):
        """
        Test a normal with a cleanup that succeeds.
        """
        lines = (
            'ECHO Hello world!',
            'SLEEP 20',
            'RETURN 1',
            'CLEANUP',
            'RETURN 0'
        )
        content = '\n'.join(lines)

        echo_obj = machine.EchoMachine(content)
        ret_code = echo_obj.start()

        self.assertEqual(ret_code, 1)

    def test_bad_cleanup(self):
        """
        Test a normal with a cleanup that fails.
        """
        lines = (
            'ECHO Hello world!',
            'SLEEP 20',
            'RETURN 1',
            'CLEANUP',
            'RETURN 2'
        )
        content = '\n'.join(lines)

        echo_obj = machine.EchoMachine(content)
        ret_code = echo_obj.start()

        self.assertEqual(ret_code, 2)

    def test_raise(self):
        """
        Test raising an exception from the state machine.
        """
        lines = (
            'ECHO Hello world!',
            'RAISE',
        )
        content = '\n'.join(lines)

        echo_obj = machine.EchoMachine(content)

        with self.assertRaises(RuntimeError):
            echo_obj.start()

    def test_parse_errors(self):
        """
        Test the handling of various syntax errors
        in the machine parameters.
        """

        # USE in cleanup section
        lines = (
            'CLEANUP',
            'USE EXCLUSIVE guest01'
        )
        content = '\n'.join(lines)

        with self.assertRaisesRegex(SyntaxError,
                                    'USE statement in cleanup section'):
            machine.EchoMachine.parse(content)

        # Wrong number of arguments in USE section
        lines = (
            'USE EXCLUSIVE',
        )
        content = '\n'.join(lines)

        with self.assertRaisesRegex(SyntaxError,
                                    'Wrong number of arguments in USE'):
            machine.EchoMachine.parse(content)

        # Bad mode in USE command
        lines = (
            'USE EXCLUSHARED guest01',
        )
        content = '\n'.join(lines)

        with self.assertRaisesRegex(SyntaxError,
                                    'Invalid mode.*USE statement'):
            machine.EchoMachine.parse(content)

        # Wrong number of arguments in echo
        lines = (
            'ECHO',
        )
        content = '\n'.join(lines)

        with self.assertRaisesRegex(SyntaxError,
                                    'Wrong number of arguments in ECHO'):
            machine.EchoMachine.parse(content)

        # Wrong number of arguments in sleep
        lines = (
            'SLEEP',
        )
        content = '\n'.join(lines)

        with self.assertRaisesRegex(SyntaxError,
                                    'Wrong number of arguments in SLEEP'):
            machine.EchoMachine.parse(content)

        # Non-number sleep time
        lines = (
            'SLEEP TWO',
        )
        content = '\n'.join(lines)

        with self.assertRaisesRegex(SyntaxError,
                                    'SLEEP argument must be a number'):
            machine.EchoMachine.parse(content)

        # Wrong number of arguments in return
        lines = (
            'RETURN',
        )
        content = '\n'.join(lines)

        with self.assertRaisesRegex(SyntaxError,
                                    'Wrong number of arguments in RETURN'):
            machine.EchoMachine.parse(content)

        # Non-int return code
        lines = (
            'RETURN ZERO',
        )
        content = '\n'.join(lines)

        with self.assertRaisesRegex(SyntaxError,
                                    'RETURN argument must be a number'):
            machine.EchoMachine.parse(content)

        # VERBOSITY not in first line
        lines = (
            'SLEEP 2',
            'VERBOSITY INFO'
        )
        content = '\n'.join(lines)
        with self.assertRaisesRegex(
            SyntaxError, 'VERBOSITY statement must come in first line'):
            machine.EchoMachine.parse(content)

        # VERBOSITY with wrong value
        lines = (
            'VERBOSITY WRONGVALUE',
            'SLEEP 2'
        )
        content = '\n'.join(lines)
        with self.assertRaisesRegex(
            ValueError, "Verbosity 'WRONGVALUE' is invalid"):
            machine.EchoMachine.parse(content)
    # test_parse_errors()

    def test_invalid_command(self):
        """
        Test the methods with valid content.
        """
        # create a valid content
        lines = (
            'USE EXCLUSIVE guest01 guest03',
            'INVALID call',
        )
        content = '\n'.join(lines)
        # check the parser method
        with self.assertRaisesRegex(SyntaxError,
                                    'Invalid command INVALID at line 2'):
            machine.EchoMachine.parse(content)

    # test_invalid_command()

# TestEcho
