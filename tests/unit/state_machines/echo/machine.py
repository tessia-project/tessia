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
from tessia_engine.state_machines.echo import machine
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

    @patch.object(machine, 'print')
    @patch.object(machine, 'sleep')
    def test_good_content(self, mock_sleep, mock_print):
        """
        Test the methods with valid content.
        """
        # create a valid content
        lines = (
            'USE EXCLUSIVE guest01 guest03',
            'USE SHARED lpar01 # our lpar',
            '# an entire line of comment',
            'ECHO Hello world!',
            'ECHO Testing a more long message to see if it works...',
            'SLEEP 20',
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
                ['sleep', 20]
            ]
        )

        # check the executor method
        echo_obj = machine.EchoMachine(content)
        result = echo_obj.start()
        self.assertEqual(result, 0)
        mock_print.assert_has_calls([
            call('Hello world!'),
            call('Testing a more long message to see if it works...')
        ])
        mock_sleep.assert_has_calls([call(20)])

    # test_good_content()

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
