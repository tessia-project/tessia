# Copyright 2016 IBM Corp.
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
Unit test for secure_resouces module
"""

#
# IMPORTS
#
from base64 import b64encode
from tessia_engine.api.app import API
from tessia_engine import config
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest.mock import patch

import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestSecureResource(TestCase):
    """
    Given the fact that SecureResource has no model associated but serves as a
    base class for the actual resources here we only implement some base
    functions for unit tests to be consumed by the unit tests of the actual
    resources. No real test is performed in this unit test.
    """
    # entry point for resource in api, to be defined by child class
    RESOURCE_URL = None
    # model associated with the resource, to be defined by child class
    RESOURCE_MODEL = None

    def _assert_created(self, resp, orig_data):
        """
        Validate if a create action was executed correctly and return the id of
        the new item.

        Args:
            resp (Response): flask response object
            orig_data (dict): the item created

        Returns:
            int: the id of the created item
        """
        # pylint: disable=no-member

        # validate the response code
        self.assertEqual(200, resp.status_code)

        # response is expected to be the id of the new item
        created_id = int(resp.get_data(as_text=True))

        # validate the response content
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()

        for key, value in orig_data.items():
            self.assertEqual(
                getattr(created_entry, key), value)

        return created_id
    # _assert_created()

    def _assert_deleted(self, resp, orig_id):
        """
        Validate if a delete action was executed correctly.

        Args:
            resp (Response): flask response object
            orig_id (int): the id of the deleted item
        """
        # pylint: disable=no-member
        resp_value = bool(resp.get_data(as_text=True))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_value, True)

        deleted_entry = self.RESOURCE_MODEL.query.filter_by(
            id=orig_id).one_or_none()
        self.assertIs(deleted_entry, None)
    # _assert_deleted()

    def _assert_listed_or_read(self, resp, entries, owner, time_range,
                               read=False):
        """
        Validate a list or read action and the resulting list contents.

        Args:
            resp (Response): flask response object
            entries (list): the original items to be checked in response
            owner (str): the owner of the listed items
            time_range (list): [start_time, end_time] to validate datetime
                               fields
            read (bool): if True, means the action to validate is a read
                         instead of list
        """
        listed_entries = json.loads(resp.get_data(as_text=True))
        # read action: enclose response in a list
        if read:
            listed_entries = [listed_entries]
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            len(entries), len(listed_entries),
            'number of entries is different')

        # compare each entry, the order by default is by id number which
        # matches our list
        for i in range(0, len(listed_entries)):
            for key in listed_entries[i]:
                db_field = listed_entries[i][key]
                if key in ('modified',):
                    mod_datetime = db_field['$date'] / 1000.0
                    self.assertTrue(
                        (mod_datetime > time_range[0] and
                         mod_datetime < time_range[1]))

                # login based fields
                elif key in ('modifier', 'owner'):
                    self.assertEqual(db_field, owner)

                # id field
                elif key == '$uri':
                    self.assertEqual(
                        '{}/{}'.format(self.RESOURCE_URL, entries[i]['id']),
                        db_field)

                # item content
                else:
                    self.assertEqual(entries[i][key], db_field)
    # _assert_listed_or_read()

    def _assert_updated(self, resp, updated_data):
        """
        Validate if an update action was executed correctly. Since the
        assertion of a created item provides the same verification steps this
        method is essentially a wrapper to that one.

        Args:
            resp (Response): flask response object
            updated_data (dict): the values updated that will be checked
        """
        self._assert_created(resp, updated_data)
    # _assert_updated()

    def _do_request(self, action, user, params=None):
        """
        Perform a http request

        Args:
            action (str): action type (create, delete, get, list, update)
            user (str): username:password
            params (any): for create: object to be json serialized in request
                                      body
                          for delete: id of the item to delete
                          for get: id of the item to retrieve
                          for list: parameters to add to url
                          for update: object to be json serialized in request
                                      body

        Returns:
            Response: flask response object
        """
        auth = 'basic {}'.format(
            b64encode(bytes(user, 'ascii')).decode('ascii'))
        action_types = {
            'create': self.app.post,
            'delete': self.app.delete,
            'get': self.app.get,
            'list': self.app.get,
            'update': self.app.patch
        }
        req_method = action_types[action]
        if action == 'create':
            url = self.RESOURCE_URL
            data = json.dumps(params)
        elif action in ('delete', 'get'):
            url = '{}/{}'.format(self.RESOURCE_URL, params)
            data = None
        elif action == 'list':
            url = '{}?{}'.format(self.RESOURCE_URL, params)
            data = None
        elif action == 'update':
            url = '{}/{}'.format(self.RESOURCE_URL, params['id'])
            updated_params = params.copy()
            updated_params.pop('id')
            data = json.dumps(updated_params)

        resp = req_method(
            url,
            headers={
                'Authorization': auth, 'Content-type': 'application/json'},
            data=data
        )

        return resp
    # _do_request()

    def _request_and_assert(self, action, user, params=None):
        """
        Perform a http request and assert that operation worked.

        Args:
            action (str): action type (create, delete, get, list, update)
            user (str): username:password
            params (any): for create: object to be json serialized in request
                                      body
                          for delete: id of the item to delete
                          for get: id of the item to retrieve
                          for list: parameters to add to url
                          for update: object to be json serialized in request
                                      body

        Returns:
            Response: flask response object
        """
        assert_map = {
            'create': self._assert_created,
            'delete': self._assert_deleted,
            'update': self._assert_updated,
        }
        assert_method = assert_map[action]

        resp = self._do_request(action, user, params)
        return assert_method(resp, params)
    # _request_and_assert()

    @classmethod
    def setUpClass(cls):
        """
        Called once before any test in this test class runs.
        Create the database instance and the flask app client to allow
        requests.
        """
        cls.db = DbUnit
        cls.db.create_db()

        # at this point we can import the app as the db configuration was
        # already stablished
        cls._conf_patcher = patch.object(config.CONF, 'get_config')
        mock_conf = cls._conf_patcher.start()
        conf = {
            'auth': {
                'login_method': 'free', 'realm': 'test realm'
            },
            'log': {
                'version': 1,
                'loggers': {'tessia_engine': {'level': 'ERROR'}},
                'handlers': {},
            },
        }
        mock_conf.return_value = conf
        # turn off warning messages from our custom exception handler
        config.CONF.log_config()

        # force recreation of objects
        API._api = None # pylint: disable=protected-access
        # the potion resource might be tied to a previous instance so we remove
        # the association
        from tessia_engine.api.resources import RESOURCES
        for resource in RESOURCES:
            resource.api = None
        API.app.config['TESTING'] = True
        cls.app = API.app.test_client()

    # setUpClass()

    @classmethod
    def tearDownClass(cls):
        # stop the CONF mock to avoid affecting other testcases
        cls._conf_patcher.stop()
    # tearDownClass()

# TestSecureResource
