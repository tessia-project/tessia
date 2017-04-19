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
Unit test for user_keys resource module
"""

#
# IMPORTS
#
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia_engine.api.resources.user_keys import UserKeyResource
from tessia_engine.db import models

import json
import time

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestUserKey(TestSecureResource):
    """
    Validates the User resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/user-keys'
    # model associated with this resource
    RESOURCE_MODEL = models.UserKey
    # api object associated with the resource
    RESOURCE_API = UserKeyResource

    def _assert_created(self, resp, orig_data):
        """
        """
        # validate the response code
        self.assertEqual(200, resp.status_code, resp.data)

        # response is expected to be the id of the new item
        key_id, key_secret = json.loads(
            resp.get_data(as_text=True))

        # validate the response content
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            key_id=key_id).one()

        for key, value in orig_data.items():
            self.assertEqual(
                getattr(created_entry, key), value)

        return key_id, key_secret
    # _assert_created()

    def _assert_deleted(self, resp, orig_id):
        """
        Validate if a delete action was executed correctly.

        Args:
            resp (Response): flask response object
            orig_id (int): the key_id of the deleted item
        """
        resp_value = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200, resp_value)
        self.assertEqual(bool(resp_value), True)

        deleted_entry = self.RESOURCE_MODEL.query.filter_by(
            key_id=orig_id).one_or_none()
        self.assertIs(deleted_entry, None)
    # _assert_deleted()

    def _create_many_entries(self, owner, qty=1):
        """
        Helper to conveniently create many entries in the database

        Args:
            owner (str): login of user owning items
            qty (int): number of entries to create

        Returns:
            tuple: (list_of_entries, [start_time, end_time])
        """
        # store the start time for later comparison with datetime fields
        time_range = [int(time.time() - 5)]
        # create the entries to work with
        entries = []
        for _ in range(0, qty):
            data = next(self._get_next_entry)
            data['key_id'], data['key_secret'] = self._request_and_assert(
                'create', '{}:a'.format(owner), data)
            entries.append(data)
        # store the end time for later comparison with datetime fields
        time_range.append(int(time.time() + 5))

        return (entries, time_range)
    # _create_many_entries()

    @staticmethod
    def _entry_gen():
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'desc': 'Yet another key {}'.format(index),
            }
            index += 1
            yield data
    # _entry_gen()

    def test_add_key(self):
        """
        Test if api correctly create a key for the user.
        """
        self._create_many_entries('user_user@domain.com', 1)
    # test_add_key()

    def test_add_key_no_basic_auth(self):
        """
        Test if api refuses to create a key when not using basic
        authentication.
        """
        entry = self._create_many_entries('user_user@domain.com', 1)[0][0]
        auth = 'x-key {}:{}'.format(entry['key_id'], entry['key_secret'])
        resp = self.app.post(
            self.RESOURCE_URL,
            headers={
                'Authorization': auth, 'Content-type': 'application/json'},
            data=json.dumps({})
        )
        body = json.loads(resp.get_data(as_text=True))
        self.assertEqual(resp.status_code, 403, body)
        self.assertRegex(
            body,
            'For this operation login and password must be provided'
        )
    # test_add_key_no_basic_auth()

    def test_add_wrong_field(self):
        """
        Test if api correctly reports error when invalid values are used for
        a field during creation.
        """
        data = next(self._get_next_entry)

        # specify fields with wrong types
        wrong_data = [
            ('desc', 5),
            ('desc', True),
            ('key_id', 'some_key_id'),
            ('created', 'some_created'),
            ('last_used', 'some_last_used'),
            ('user', 'some_user'),
        ]
        # apply wrong values and try creation
        for entry in wrong_data:
            field = entry[0]
            value = entry[1]
            work_data = data.copy()
            work_data[field] = value
            resp = self._do_request(
                'create', '{}:a'.format('user_user@domain.com'), work_data)

            # validate the response received
            self.assertEqual(
                resp.status_code,
                400,
                "'field={}','value={}'".format(field, value)
            )
    # test_add_wrong_field()

    def test_del_as_user(self):
        """
        Exercise removing a key from user's keyring.
        """
        entry = self._create_many_entries('user_user@domain.com', 1)[0][0]

        # find the corresponding id by performing a search - this is to
        # exercise the real use case where the client does not have direct
        # access to the database
        params = 'where={}'.format(json.dumps({'key_id': entry['key_id']}))
        resp = self._do_request('list', 'user_user@domain.com:a', params)
        listed_entries = json.loads(resp.get_data(as_text=True))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(listed_entries), 1, 'More than one key_id found')
        table_id = int(listed_entries[0]['$uri'].split('/')[-1])

        self._request_and_assert(
            'delete', 'user_user@domain.com:a', table_id)
    # test_del_as_user()

    def test_del_as_admin(self):
        """
        Exercise removing a key from user's keyring using admin user.
        """
        entry = self._create_many_entries('user_user@domain.com', 1)[0][0]
        table_id = self.RESOURCE_MODEL.query.filter_by(
            key_id=entry['key_id']).one().id

        self._request_and_assert(
            'delete', 'user_admin@domain.com:a', table_id)
    # test_del_as_admin()

    def test_del_no_basic_auth(self):
        """
        Test if api refuses to delete a key when not using basic
        authentication.
        """
        entry = self._create_many_entries('user_user@domain.com', 1)[0][0]
        table_id = self.RESOURCE_MODEL.query.filter_by(
            key_id=entry['key_id']).one().id

        auth = 'x-key {}:{}'.format(entry['key_id'], entry['key_secret'])
        resp = self.app.delete(
            '{}/{}'.format(self.RESOURCE_URL, table_id),
            headers={
                'Authorization': auth, 'Content-type': 'application/json'},
            data=None
        )
        body = json.loads(resp.get_data(as_text=True))
        self.assertEqual(resp.status_code, 403, body)
        self.assertRegex(
            body,
            'For this operation login and password must be provided'
        )
    # test_del_no_basic_auth()

    def test_del_no_role(self):
        """
        Try to remove a key from another user. This should fail with
        ItemNotFoundError (and not Forbidden) for security reasons.
        """
        entry = self._create_many_entries('user_user@domain.com', 1)[0][0]
        table_id = self.RESOURCE_MODEL.query.filter_by(
            key_id=entry['key_id']).one().id

        resp = self._do_request(
            'delete', 'user_privileged@domain.com:a', table_id)

        self.assertEqual(resp.status_code, 422)
    # test_del_no_role()

    def test_dates(self):
        """
        Verify if the created date is correct and last used time is being
        updated after each request.
        """
        entries, time_range = self._create_many_entries(
            'user_user@domain.com', 1)

        table_id = self.RESOURCE_MODEL.query.filter_by(
            key_id=entries[0]['key_id']).one().id
        time_stamp = time.time() - 5

        # perform a request, will cause last_used to be updated
        resp = self._do_request('get', 'user_user@domain.com:a', table_id)
        self.assertEqual(resp.status_code, 200)
        entry = json.loads(resp.get_data(as_text=True))

        # compare dates
        created_datetime = entry['created']['$date'] / 1000.0
        self.assertTrue(
            (created_datetime > time_range[0] and
             created_datetime < time_range[1]))

        last_used_datetime = entry['last_used']['$date'] / 1000.0
        self.assertTrue(last_used_datetime > time_stamp)
    # test_dates()

    def test_list_and_read(self):
        """
        Verify if listing and reading permissions are correctly handled
        """
        entry = self._create_many_entries('user_user@domain.com', 1)[0][0]

        table_entry = self.RESOURCE_MODEL.query.filter_by(
            key_id=entry['key_id']).one()

        # try both with key's owner and admin user
        for user_login in ('user_user@domain.com', 'user_admin@domain.com'):
            # perform a read request
            resp = self._do_request(
                'get', '{}:a'.format(user_login), table_entry.id)

            # validate response
            self.assertEqual(resp.status_code, 200)
            check_entry = json.loads(resp.get_data(as_text=True))
            check_entry['key_secret'] = entry['key_secret']
            for field in ('key_id', 'key_secret', 'user', 'desc'):
                self.assertEqual(
                    check_entry[field], getattr(table_entry, field))

            # perform a list
            resp = self._do_request(
                'list', '{}:a'.format(user_login), None)

            # validate response
            self.assertEqual(resp.status_code, 200)
            listed_entries = json.loads(resp.get_data(as_text=True))
            self.assertTrue(len(listed_entries) > 0)

            # go over entries and find the created key
            found = False
            for resp_entry in listed_entries:
                # not the key we are looking for: keep searching
                if resp_entry['key_id'] != entry['key_id']:
                    continue

                found = True
                check_entry['key_secret'] = resp_entry.copy()
                check_entry['key_secret'] = entry['key_secret']
                for field in ('key_id', 'key_secret', 'user', 'desc'):
                    self.assertEqual(
                        check_entry[field], getattr(table_entry, field))
                break

            self.assertTrue(found)

    # test_list_and_read()

    def test_list_and_read_no_role(self):
        """
        List entries with a user without role in any project
        """
        entry = self._create_many_entries('user_user@domain.com', 1)[0][0]
        table_id = self.RESOURCE_MODEL.query.filter_by(
            key_id=entry['key_id']).one().id

        resp = self._do_request(
            'get', 'user_privileged@domain.com:a', table_id)
        self.assertEqual(resp.status_code, 422)

        resp = self._do_request(
            'list', 'user_privileged@domain.com:a', None)
        self.assertEqual(resp.status_code, 200)
        listed_entries = json.loads(resp.get_data(as_text=True))
        self.assertEqual(len(listed_entries), 0)
    # test_list_and_read_restricted_no_role()

    def test_list_filtered(self):
        """
        Test basic filtering capabilities
        """
        filter_values = {
            'user': 'user_user@domain.com',
            'key_id': 'some_key_id_for_filter',
            'desc': 'some_desc_for_filter',
        }
        entries, _ = self._create_many_entries(
            'user_user@domain.com:a', 1)

        item = self.RESOURCE_MODEL.query.filter_by(
            key_id=entries[0]['key_id']
        ).one()
        item_id = item.id

        for field, value in filter_values.items():
            # set the field to the value to be filtered by
            orig_value = getattr(item, field)
            setattr(item, field, value)
            self.db.session.add(item)
            self.db.session.commit()
            entries[0][field] = value

            # perform query
            params = 'where={}'.format(json.dumps({field: value}))
            resp = self._do_request('list', '{}:a'.format(
                'user_user@domain.com:a'), params)

            # validate result: see if all entries have the specified value for
            # the given field
            listed_entries = json.loads(resp.get_data(as_text=True))
            entry_uri = '{}/{}'.format(self.RESOURCE_URL, item_id)
            found = False
            for filtered_entry in listed_entries:
                self.assertEqual(entries[0][field], filtered_entry[field])
                # entry is the item we have set: save result and continue
                # validating other entries
                if filtered_entry['$uri'] == entry_uri:
                    found = True
            self.assertTrue(found, 'Item not found in list')

            # return field to original value
            setattr(item, field, orig_value)
            self.db.session.add(item)
            self.db.session.commit()
            entries[0][field] = orig_value
    # _test_list_filtered()

    def test_update_forbidden(self):
        """
        Test two scenarios:
        1- add an item with a login that already exists
        2- update an item to a login that already exists
        """
        resp = self._do_request(
            'update', '{}:a'.format('user_user@domain.com'), {'id': 1})
        self.assertEqual(resp.status_code, 403)
    # test_update_forbidden()
# TestUser
