# Copyright 2019 IBM Corp.
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
Unit test for the bulkop machine module
"""

#
# IMPORTS
#
from tessia.server.state_machines import base
from tessia.server.state_machines.bulkop import machine
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest.mock import patch
from unittest.mock import Mock

import csv
import io
import json
import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class TestBulkOperator(TestCase):
    """
    Unit test for the machine module of the bulkop state machine.
    """

    @classmethod
    def setUpClass(cls):
        """
        Called once to create the db content for this test.
        """
        DbUnit.create_db()
        sample_file = '{}/data.json'.format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(sample_file, 'r') as sample_fd:
            data = sample_fd.read()
        DbUnit.create_entry(json.loads(data))
        cls.db = DbUnit
    # setUpClass()

    def setUp(self):
        """
        Prepare the necessary mocks at the beginning of each testcase.
        """
        # mock config object
        patcher = patch.object(base, 'CONF', autospec=True)
        self._mock_conf = patcher.start()
        self.addCleanup(patcher.stop)

        # mock sys object
        patcher = patch.object(base, 'sys', autospec=True)
        self._mock_sys = patcher.start()
        self._mock_sys_tblimit = 10
        self._mock_sys.tracebacklimit = self._mock_sys_tblimit
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, 'MANAGER', autospec=True)
        self._mock_manager = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)
        mock_logging.getLogger.return_value = Mock(
            spec=['warning', 'error', 'debug', 'info'])

        # mock handlers
        patcher = patch.object(
            machine, 'ResourceHandlerSystem', autospec=True)
        self._mock_handler_sys = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_handler_sys.headers_match.return_value = True
        mocked_handlers = {
            'system': {
                'type': 'systems',
                'class': self._mock_handler_sys,
            }
        }
        dict_patcher = patch.dict(machine.HANDLERS, values=mocked_handlers)
        dict_patcher.start()
        self.addCleanup(dict_patcher.stop)
    # setUp()

    def test_parse(self):
        """
        Exercise different scenarios for the parse operation
        """
        content = {
            'field1': 'value1', 'field2': 'value2', 'field3': 'value3'}
        request = {
            'content': '{}\n{}'.format(','.join(content.keys()),
                                       ','.join(content.values())),
            'requester': 'admin',
        }

        result = machine.BulkOperatorMachine.parse(json.dumps(request))
        self.assertEqual(result['resources']['exclusive'], [])
        self.assertEqual(result['resources']['shared'], [])
        self.assertEqual(result['description'], "Bulk operation for systems")
        self.assertEqual(
            list(result['params']['content']),
            list(csv.DictReader(io.StringIO(request['content'])))
        )

        # invalid request parameters
        request = {'something': 'invalid'}
        with self.assertRaisesRegex(
                SyntaxError, 'Invalid request parameters'):
            machine.BulkOperatorMachine.parse(json.dumps(request))

        # invalid requester
        request = {
            'content': 'field1,field2,field3',
            'requester': 'wrong_user'
        }
        with self.assertRaisesRegex(
                ValueError, 'Requester wrong_user does not exist'):
            machine.BulkOperatorMachine.parse(json.dumps(request))

        # invalid headers
        self._mock_handler_sys.headers_match.return_value = False
        request = {
            'content': 'some_invalid_content',
            'requester': 'admin'
        }
        with self.assertRaisesRegex(
                ValueError, 'Error trying to parse input header'):
            machine.BulkOperatorMachine.parse(json.dumps(request))

        # content does not match requested type
        self._mock_handler_sys.headers_match.return_value = True
        request = {
            'content': 'field1,field2,field3',
            'requester': 'admin',
            'resource_type': 'svol'
        }
        with self.assertRaisesRegex(
                ValueError,
                'Input provided does not match requested resource type'):
            machine.BulkOperatorMachine.parse(json.dumps(request))
    # test_parse()

    def test_start(self):
        """
        Test a correct machine execution
        """
        content = {
            'field1': 'value1', 'field2': 'value2', 'field3': 'value3'}
        request = {
            'content': '{}\n{}'.format(','.join(content.keys()),
                                       ','.join(content.values())),
            'resource_type': 'system'
        }
        complete_request = machine.BulkOperatorMachine.recombine(
            json.dumps(request), {'requester': 'admin'})
        mac_obj = machine.BulkOperatorMachine(complete_request)
        mac_obj.start()

        self._mock_handler_sys.return_value.render_item.assert_called_with(
            content)
        self._mock_manager.session.rollback.assert_called_with()

        # try with commit enabled
        request['commit'] = True
        complete_request = machine.BulkOperatorMachine.recombine(
            json.dumps(request), {'requester': 'admin'})
        mac_obj = machine.BulkOperatorMachine(complete_request)
        mac_obj.start()

        self._mock_handler_sys.return_value.render_item.assert_called_with(
            content)
        self._mock_manager.session.commit.assert_called_with()
    # test_start()
# TestBulkOperator
