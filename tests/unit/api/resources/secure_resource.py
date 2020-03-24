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
Unit test for secure_resources module
"""

#
# IMPORTS
#
from base64 import b64encode
from tessia.server import config
from tessia.server.api.app import API
from tessia.server.db import models
from tessia.server.db.models import ResourceMixin
from tests.unit.config import EnvConfig
from tests.unit.db.models import DbUnit
from unittest import TestCase

import abc
import json
import time

#
# CONSTANTS AND DEFINITIONS
#
DEFAULT_CONFIG = {
    'auth': {
        'login_method': 'free',
        'realm': 'test realm'
    },
    'log': {
        'version': 1,
        'loggers': {
            'tessia.server': {
                'level': 'ERROR'
            }
        },
        'handlers': {},
    },
}

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
    # api object associated with the resource, to be defined by child class
    RESOURCE_API = None

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
        # validate the response code
        self.assertEqual(200, resp.status_code, resp.data)

        # response is expected to be the id of the new item
        created_id = int(resp.get_data(as_text=True))

        # validate the response content
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()

        for key, value in orig_data.items():
            self.assertEqual(
                getattr(created_entry, key), value,
                '{} is not {}'.format(key, value))

        return created_id
    # _assert_created()

    def _assert_deleted(self, resp, orig_id):
        """
        Validate if a delete action was executed correctly.

        Args:
            resp (Response): flask response object
            orig_id (int): the id of the deleted item
        """
        resp_value = bool(resp.get_data(as_text=True))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_value, True)

        deleted_entry = self.RESOURCE_MODEL.query.filter_by(
            id=orig_id).one_or_none()
        self.assertIs(deleted_entry, None)
    # _assert_deleted()

    def _assert_listed_or_read(self, resp, entries, time_range, read=False):
        """
        Validate a list or read action and the resulting list contents.

        Args:
            resp (Response): flask response object
            entries (list): the original items to be checked in response
            time_range (list): [start_time, end_time] to validate datetime
                               fields
            read (bool): if True, means the action to validate is a read
                         instead of list
        """
        is_resource = issubclass(self.RESOURCE_MODEL, ResourceMixin)

        listed_entries = json.loads(resp.get_data(as_text=True))
        # read action: enclose response in a list
        if read:
            listed_entries = [listed_entries]
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            len(entries), len(listed_entries),
            'number of entries is different')

        # sort lists to make sure the order of entries are the same
        listed_entries.sort(key=lambda entry: entry['$uri'].split('/')[-1])
        entries.sort(
            key=lambda entry: str(
                entry.get('id', entry.get('$uri', '').split('/')[-1]))
        )

        # compare each entry
        for index, entry in enumerate(listed_entries):

            # model is a resourcemixin: check modified time
            if is_resource:
                modified_field = entry['modified']
                mod_datetime = modified_field['$date'] / 1000.0
                self.assertTrue(
                    (mod_datetime > time_range[0] and
                     mod_datetime < time_range[1]),
                    'start_range: {} mod_datetime: {} end_range: {}'.format(
                        time_range[0], mod_datetime, time_range[1]))

            for key, value in entries[index].items():
                # id field
                if key == 'id':
                    self.assertEqual(
                        '{}/{}'.format(self.RESOURCE_URL, value),
                        entry['$uri'], "key <uri> didn't match"
                    )

                # item content
                else:
                    db_field = entry[key]
                    self.assertEqual(value, db_field,
                                     "key <{}> didn't match".format(key))
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

    def _create_many_entries(self, owner, qty=1):
        """
        Helper to conveniently create many entries in the database

        Args:
            owner (str): login of user owning items
            qty (int): number of entries to create

        Returns:
            tuple: (list_of_entries, [start_time, end_time])
        """
        is_resource = issubclass(self.RESOURCE_MODEL, ResourceMixin)

        # store the start time for later comparison with datetime fields
        time_range = [int(time.time() - 5)]
        # create the entries to work with
        entries = []
        for _ in range(0, qty):
            data = next(self._get_next_entry)
            created_id = self._request_and_assert(
                'create', '{}:a'.format(owner), data)
            data['id'] = created_id
            # model is a resource mixin: add the login fields
            if is_resource:
                data['owner'] = owner
                data['modifier'] = owner
            entries.append(data)
        # store the end time for later comparison with datetime fields
        time_range.append(int(time.time() + 5))

        return (entries, time_range)
    # _create_many_entries()

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

    @abc.abstractclassmethod
    def _entry_gen(cls):
        """
        This is the generator responsible for creating new items of the given
        resource. Should be implemented by children classes
        """
        raise NotImplementedError()
    # _entry_gen()

    def _request_and_assert(self, action, user, params=None):
        """
        Perform a http request and assert that operation worked.

        Args:
            action (str): action type (create, delete, update)
            user (str): username:password
            params (any): for create: object to be json serialized in request
                                      body
                          for delete: id of the item to delete
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
        if cls.RESOURCE_API is None:
            raise RuntimeError('Child class did not define RESOURCE_API')

        cls.db = DbUnit
        cls.db.create_db()

        # at this point we can import the app as the db configuration was
        # already stablished

        # use the helper class to manage the config file
        cls._env_config = EnvConfig()
        cls._env_config.start(DEFAULT_CONFIG)
        # turn off warning messages by applying our log config
        config.CONF.log_config()

        # force recreation of objects
        API.reset()
        API.app.config['TESTING'] = True
        cls.app = API.app.test_client()

        # define the generator for creating new items
        cls._get_next_entry = cls._entry_gen()

        # create some useful users, roles and projects
        project_name = '{} project'.format(cls.RESOURCE_URL.strip('/'))
        cls._db_entries = {
            "User": [
                {
                    "name": "user_sandboxed",
                    "admin": False,
                    "title": "Sandboxed user",
                    "restricted": False,
                    "login": "user_sandbox@domain.com"
                },
                {
                    "name": "user_restricted",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": True,
                    "login": "user_restricted@domain.com"
                },
                {
                    "name": "user_user",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_user@domain.com"
                },
                {
                    "name": "user_privileged",
                    "admin": False,
                    "title": "Title of privileged user",
                    "restricted": False,
                    "login": "user_privileged@domain.com"
                },
                {
                    "name": "user_project_owner",
                    "admin": False,
                    "title": "Title of project owner",
                    "restricted": False,
                    "login": "user_project_owner@domain.com"
                },
                {
                    "name": "user_project_admin",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_project_admin@domain.com"
                },
                {
                    "name": "lab_admin",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_hw_admin@domain.com"
                },
                {
                    "name": "admin",
                    "admin": True,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_admin@domain.com"
                },
            ],
            "Project": [
                {
                    "name": project_name,
                    "desc": "{} test".format(project_name),
                },
                {
                    "name": '{} 2'.format(project_name),
                    "desc": "{} 2 test".format(project_name),
                }
            ],
            "UserRole": [
                {
                    "project": project_name,
                    "user": "user_sandbox@domain.com",
                    "role": "USER_SANDBOX"
                },
                {
                    "project": project_name,
                    "user": "user_user@domain.com",
                    "role": "USER"
                },
                {
                    "project": project_name,
                    "user": "user_privileged@domain.com",
                    "role": "USER_PRIVILEGED"
                },
                {
                    "project": project_name,
                    "user": "user_project_owner@domain.com",
                    "role": "OWNER_PROJECT"
                },
                {
                    "project": project_name,
                    "user": "user_project_admin@domain.com",
                    "role": "ADMIN_PROJECT"
                },
                {
                    "project": project_name,
                    "user": "user_hw_admin@domain.com",
                    "role": "ADMIN_LAB"
                }
            ],
        }
        cls.db.create_entry(cls._db_entries)

    # setUpClass()

    @classmethod
    def tearDownClass(cls):
        # restore original config
        cls._env_config.stop()
    # tearDownClass()

    # TESTCASES SECTION: the methods below are implemented in such a way to
    # allow the concrete classes to pass they specific parameters and still
    # shared the same testcase steps
    def _test_add_all_fields_many_roles(self, logins):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying all possible fields.

        Args:
            logins (list): user logins to be tested
        """
        for login in logins:
            data = next(self._get_next_entry)
            self._request_and_assert(
                'create', '{}:a'.format(login), data)

    # _test_add_all_fields_many_roles()

    def _test_add_all_fields_no_role(self, logins):
        """
        Exercise the scenario where a user without an appropriate role tries to
        create an item and fails.

        Args:
            logins (list): user logins to be tested
        """
        for login in logins:
            data = next(self._get_next_entry)
            resp = self._do_request('create', '{}:a'.format(login), data)
            # validate the response received, should be forbidden
            self.assertEqual(
                resp.status_code,
                403,
                'Login was: {}'.format(login))
    # _test_add_all_fields_no_role()

    def _test_add_mandatory_fields(self, login, pop_fields):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying only the mandatory fields.

        Args:
            login (str): user login for request
            pop_fields (list): the fields to be omitted and their expected
                               values on response
        """
        data = next(self._get_next_entry)

        # pop specified fields
        for field in pop_fields:
            data.pop(field[0])

        resp = self._do_request(
            'create', '{}:a'.format(login), data)
        # validate the response received
        for field in pop_fields:
            data[field[0]] = field[1]
        self._assert_created(resp, data)
    # _test_add_mandatory_fields()

    def _test_add_mandatory_fields_as_admin(self, login):
        """
        Exercise the scenario where using the admin user to create an item
        makes project a mandatory field.

        Args:
            login (str): admin user for request
        """
        data = next(self._get_next_entry)

        data.pop('project')

        # try to add as admin - without project specified it should fail as api
        # does not know which project to add since this admin user entry has no
        # role in any project
        resp = self._do_request(
            'create', '{}:a'.format(login), data)
        # validate the response received 403 forbidden
        self.assertEqual(resp.status_code, 403)
    # _test_add_mandatory_fields_as_admin()

    def _test_add_missing_field(self, login, pop_fields):
        """
        Test if api correctly reports error when a mandatory field is missing
        during creation.

        Args:
            login (str): user login for request
            pop_fields (list): the fields to be omitted
        """
        data = next(self._get_next_entry)

        # pop specified fields
        for field in pop_fields:
            work_data = data.copy()
            work_data.pop(field)

            resp = self._do_request(
                'create', '{}:a'.format(login), work_data)
            # validate the response received
            self.assertEqual(resp.status_code, 400)
    # _test_add_missing_field()

    def _test_add_update_wrong_field(self, login, wrong_fields):
        """
        Test if api correctly reports error when invalid values are used for
        a field during creation and update.

        Args:
            login (str): user login for request
            wrong_fields (list): fields with the wrong values [(field, value)]
                                 or optionally also a regex for error message
                                 as in [(field, value, re_error)]
        """
        data = next(self._get_next_entry)

        # apply wrong values for creation
        for entry in wrong_fields:
            field = entry[0]
            value = entry[1]
            work_data = data.copy()
            work_data[field] = value
            resp = self._do_request(
                'create', '{}:a'.format(login), work_data)

            # validate the response received
            self.assertEqual(
                resp.status_code,
                400,
                "'field={}','value={}'".format(field, value)
            )

            # regex for error message provided: check it
            if len(entry) > 2:
                body = json.loads(resp.get_data(as_text=True))
                self.assertRegex(body['message'], entry[2])

        # for update, create an item with good values first
        item = self._create_many_entries(login, 1)[0][0]
        # apply wrong values
        for entry in wrong_fields:
            field = entry[0]
            value = entry[1]
            work_data = {'id': item['id']}
            work_data[field] = value
            resp = self._do_request(
                'update', '{}:a'.format(login), work_data)

            # validate the response received
            self.assertEqual(resp.status_code, 400)

            # regex for error message provided: check it
            if len(entry) > 2:
                body = json.loads(resp.get_data(as_text=True))
                self.assertRegex(body['message'], entry[2])

    # _test_add_update_wrong_field()

    def _test_del_many_roles(self, combos):
        """
        Exercise to remove entries with different roles

        Args:
            combos (list): [(login_for_add, login_for_del)]
        """
        for login_add, login_del in combos:
            # create the item to be deleted
            data = next(self._get_next_entry)
            created_id = self._request_and_assert(
                'create', '{}:a'.format(login_add), data)
            # now request to remove it
            self._request_and_assert(
                'delete', '{}:a'.format(login_del), created_id)

    # _test_del_many_roles()

    def _test_del_has_dependent(self, login, item_id, assoc_item=None):
        """
        Try to delete an item which has another item associated with it. Since
        the relation between the items is specific this has to be set by the
        concrete class before calling this method.

        Args:
            login (str): user login for request
            item_id (int): id of item to try the deletion
            assoc_item (Model): db's entry of associated item
        """
        if assoc_item is not None:
            self.db.session.add(assoc_item)
            self.db.session.commit()

        resp = self._do_request(
            'delete', '{}:a'.format(login), item_id)
        # validate a conflict response
        # TODO: validate return message when running under postgres
        self.assertEqual(resp.status_code, 409)

        # remove associated item to avoid problems with other testcases
        if assoc_item is not None:
            self.db.session.delete(assoc_item)
            self.db.session.commit()
    # _test_del_has_dependent()

    def _test_del_invalid_id(self):
        """
        Test if api correctly handles the case when trying to delete an
        invalid id
        """
        resp = self._do_request(
            'delete', 'user_admin@domain.com:a', -1)
        # validate deletion failed with 404 not found
        self.assertEqual(resp.status_code, 404)
    # _test_del_invalid_id()

    def _test_del_no_role(self, combos):
        """
        Try to remove an entry without permissions

        Args:
            combos (list): [(login_for_add, login_for_del)]
        """
        for login_add, login_del in combos:
            # create the target entry
            data = next(self._get_next_entry)
            created_id = self._request_and_assert(
                'create', '{}:a'.format(login_add), data)

            # delete as a user without a valid role - should fail
            resp = self._do_request(
                'delete', '{}:a'.format(login_del), created_id)
            # validate deletion failed
            self.assertEqual(resp.status_code, 403)
    # _test_del_no_role()

    def _test_list_and_read(self, login_add, logins_list):
        """
        Verify if listing and reading permissions are correctly handled

        Args:
            login_add (str): user login to be used as owner
            logins_list (list): logins to be used for request
        """
        time_range = [int(time.time())]

        # store the existing entries and add them to the new ones for
        # later validation
        resp = self._do_request(
            'list', '{}:a'.format(login_add), None)
        entries = json.loads(resp.get_data(as_text=True))
        # adjust id field to make the http response look like the same as the
        # dict from the _create_many_entries return
        for entry in entries:
            entry['id'] = entry.pop('$uri').split('/')[-1]
            try:
                mod_datetime = int(entry['modified']['$date'] / 1000.0)
            # target has no modified time: skip it
            except KeyError:
                continue
            if mod_datetime < time_range[0]:
                time_range[0] = mod_datetime
        time_range[0] = time_range[0] - 5

        # create some more entries to work with
        new_entries, create_time_range = self._create_many_entries(
            login_add, 5)
        # put existing and new entries together
        entries += new_entries
        # use end time from create operation
        time_range.append(create_time_range[1])

        # retrieve list
        for login in logins_list:
            resp = self._do_request('list', '{}:a'.format(login), None)
            self._assert_listed_or_read(resp, entries, time_range)

        # perform a read
        for login in logins_list:
            resp = self._do_request(
                'get', '{}:a'.format(login), entries[0]['id'])
            self._assert_listed_or_read(
                resp, [entries[0]], time_range, read=True)
    # _test_list_and_read()

    def _test_list_and_read_restricted_no_role(self, login_add, login_rest,
                                               allowed=True, http_code=403):
        """
        List entries with a restricted user without role in any project

        Args:
            login_add (str): user login used to create items
            login_rest (str): restricted user login used to list items
            allowed (str): whether the resource being tested allow
                           listing/reading
            http_code (int): http status code expected when trying to read
        """
        # store the existing entries and add them to the new ones for
        # later validation
        resp = self._do_request(
            'list', '{}:a'.format(login_add), None)
        entries = json.loads(resp.get_data(as_text=True))
        # adjust id field to make the http response look like the same as the
        # dict from the _create_many_entries return
        for entry in entries:
            entry['id'] = entry.pop('$uri').split('/')[-1]

        # create some more entries to work with
        new_entries, time_range = self._create_many_entries(login_add, 5)
        entries += new_entries

        block_read = (issubclass(self.RESOURCE_MODEL, ResourceMixin) or
                      not allowed)

        # retrieve the existing entries
        resp = self._do_request('list', '{}:a'.format(login_rest))
        listed_entries = json.loads(resp.get_data(as_text=True))
        # regular resource or allowed False: listing and read should not work
        if block_read:
            self.assertEqual(
                len(listed_entries), 0, 'Restricted user was able to list')

            # perform a read
            for entry in entries:
                resp = self._do_request(
                    'get', '{}:a'.format(login_rest), entry['id'])
                self.assertEqual(resp.status_code, http_code)

        # types resource or allowed True: listing and read are allowed
        else:
            resp = self._do_request('list', '{}:a'.format(login_rest), None)
            self._assert_listed_or_read(resp, entries, time_range)

            # perform a read
            for entry in entries:
                resp = self._do_request(
                    'get', '{}:a'.format(login_rest), entry['id'])
                self._assert_listed_or_read(
                    resp, [entry], time_range, read=True)

    # _test_list_and_read_restricted_no_role()

    def _test_list_and_read_restricted_with_role(self, login_add, login_rest):
        """
        List entries with a restricted user who has a role in a project.

        Args:
            login_add (str): user login used to create items
            login_rest (str): restricted user login used to list items
        """
        # make sure table is empty
        prev_entries = self.RESOURCE_MODEL.query.join(
            'project_rel'
        ).filter(
            self.RESOURCE_MODEL.project ==
            self._db_entries['Project'][0]['name']
        ).all()
        for prev_entry in prev_entries:
            self.db.session.delete(prev_entry)
        self.db.session.commit()

        # create the entries to work with
        entries, time_range = self._create_many_entries(login_add, 5)

        # add the role for the restricted user
        role = models.UserRole(
            project=self._db_entries['Project'][0]['name'],
            user=login_rest,
            role="USER_RESTRICTED"
        )
        self.db.session.add(role)
        self.db.session.commit()

        # retrieve list
        resp = self._do_request('list', '{}:a'.format(login_rest))
        self._assert_listed_or_read(resp, entries, time_range)

        # perform a read
        resp = self._do_request(
            'get', '{}:a'.format(login_rest), entries[0]['id'])
        self._assert_listed_or_read(
            resp, [entries[0]], time_range, read=True)

        # remove the added role to avoid conflict with other testcases
        self.db.session.delete(role)
        self.db.session.commit()
    # _test_list_and_read_restricted_with_role()

    def _test_list_filtered(self, login, filter_fields):
        """
        Test simple filtering by specifying each field individually.

        Args:
            login (str): user login for creating and listing
            filter_fields (dict): field and values to filter upon
        """
        entries, _ = self._create_many_entries(login, 1)

        item = self.RESOURCE_MODEL.query.filter_by(
            id=entries[0]['id']
        ).one()

        for field, value in filter_fields.items():
            # set the field to the value to be filtered by
            orig_value = getattr(item, field)
            setattr(item, field, value)
            self.db.session.add(item)
            self.db.session.commit()
            entries[0][field] = value

            # perform query
            params = 'where={}'.format(json.dumps({field: value}))
            resp = self._do_request('list', '{}:a'.format(login), params)

            # validate result: see if all entries have the specified value for
            # the given field
            listed_entries = json.loads(resp.get_data(as_text=True))
            entry_uri = '{}/{}'.format(self.RESOURCE_URL, entries[0]['id'])
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

    def _test_update_project(self, logins=None):
        """
        Exercise the update of the item's project. For that operation a user
        requires permission on both projects.

        Args:
            logins (list): list of users to test

        Raises:
            ValueError: if test is attempted on an invalid resource type
        """
        is_resource = issubclass(self.RESOURCE_MODEL, ResourceMixin)
        if not is_resource:
            raise ValueError(
                'This test cannot be executed on a resource without project')

        if not logins:
            logins = [
                'user_restricted@domain.com',
                'user_user@domain.com',
                'user_privileged@domain.com',
                'user_hw_admin@domain.com',
            ]

        # prepare the necessary projects and the role
        clean_objs = []
        proj_name = 'Project _test_update_project'
        proj_obj = models.Project(name=proj_name, desc=proj_name)
        self.db.session.add(proj_obj)
        clean_objs.append(proj_obj)
        proj_2_name = 'Project _test_update_project 2'
        proj_obj_2 = models.Project(name=proj_2_name, desc=proj_2_name)
        self.db.session.add(proj_obj_2)
        clean_objs.append(proj_obj_2)
        role_name = '_test_update_project'
        role_obj = models.Role(name=role_name, desc=role_name)
        self.db.session.add(role_obj)
        clean_objs.append(role_obj)
        action_obj = models.RoleAction(
            role=role_name,
            resource=self.RESOURCE_MODEL.__tablename__.upper(),
            action='UPDATE'
        )
        self.db.session.add(action_obj)
        clean_objs.append(action_obj)
        self.db.session.commit()

        for login in logins:
            # create the entry to work with
            data = next(self._get_next_entry)
            data['project'] = proj_name
            data['owner'] = login
            created_id = self._request_and_assert('create', 'admin:a', data)

            # user is owner but has no role in target project
            data = {'id': created_id, 'project': proj_2_name}
            resp = self._do_request('update', '{}:a'.format(login), data)
            self.assertEqual(resp.status_code, 403)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(
                body['message'],
                "User has no UPDATE permission for the specified project"
            )

            # user has role in current project but not in target project
            # prepare the environment first
            user_role_obj = models.UserRole(
                user=login,
                role=role_name,
                project=proj_name,
            )
            self.db.session.add(user_role_obj)
            self.db.session.commit()
            data = {'id': created_id, 'owner': 'admin'}
            resp = self._request_and_assert('update', 'admin:a', data)
            # now perform action and verify result
            data = {'id': created_id, 'project': proj_2_name}
            resp = self._do_request('update', '{}:a'.format(login), data)
            self.assertEqual(resp.status_code, 403)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(
                body['message'],
                "User has no UPDATE permission for the specified project"
            )

            # user has role in both projects
            user_role_2_obj = models.UserRole(
                user=login,
                role=role_name,
                project=proj_2_name
            )
            self.db.session.add(user_role_2_obj)
            self.db.session.commit()
            data = {'id': created_id, 'project': proj_2_name}
            self._request_and_assert('update', '{}:a'.format(login), data)

            # user is owner and has role only in target project
            # prepare the environment first
            self.db.session.delete(user_role_2_obj)
            self.db.session.commit()
            data = {'id': created_id, 'owner': login}
            resp = self._request_and_assert('update', 'admin:a', data)
            # now perform action and verify result
            data = {'id': created_id, 'project': proj_name}
            self._request_and_assert('update', '{}:a'.format(login), data)

            # clean up
            self.RESOURCE_MODEL.query.filter_by(id=created_id).delete()
            self.db.session.delete(user_role_obj)
            self.db.session.commit()

        # clean up
        for obj in clean_objs:
            self.db.session.delete(obj)
        self.db.session.commit()
    # _test_update_project()

    def _test_update_valid_fields(
            self, login_add, logins_update, update_fields):
        """
        Exercise  the update of existing objects when correct format and
        writable fields are specified.
        Ffor resourcemixins, exercise different combinations of owner/updater
        to test both when user is owner of item or has a role in the item's
        project.

        Args:
            login_add (str): user login used to create items
            logins_update (list): logins allowed to performed update or entries
                                  (owner, updater) if it's a resourcemixin
            update_fields (dict): mapping of fields with values to update
        """
        is_resource = issubclass(self.RESOURCE_MODEL, ResourceMixin)

        for login_update in logins_update:
            # create the entry to work with
            entry = self._create_many_entries(login_add, 1)[0][0]

            item = self.RESOURCE_MODEL.query.filter_by(
                id=entry['id']
            ).one()
            # resourcemixin type: set the correct owner
            if is_resource:
                login_owner, login_update = login_update
                item.owner = login_owner
                self.db.session.add(item)
                self.db.session.commit()

            # id is not updated but passed as part of the url
            update_fields['id'] = entry['id']
            self._request_and_assert(
                'update', '{}:a'.format(login_update), update_fields)

            # remove entry to avoid conflict with next one
            self.db.session.delete(item)
            self.db.session.commit()
    # _test_update_valid_fields()

    def _test_add_update_assoc_error(self, login, wrong_fields):
        """
        Try creation and edit while setting a FK field to a value that has no
        entry in the associated table.
        """
        # create a map of descriptions found in the schema for each field
        desc_by_field = {}
        for entry in wrong_fields:
            field = entry[0]
            # api resource defined with description for field: use it
            # the logic is similar to what the ItemNotFoundError exception does
            if (hasattr(self.RESOURCE_API, 'Schema')
                    and hasattr(self.RESOURCE_API.Schema, field)):
                schema_field = getattr(self.RESOURCE_API.Schema, field)
                desc = schema_field.description
            else:
                desc = field
            desc_by_field[field] = desc

        data = next(self._get_next_entry)

        # apply wrong values for creation
        for entry in wrong_fields:
            field = entry[0]
            value = entry[1]
            work_data = data.copy()
            work_data[field] = value
            resp = self._do_request(
                'create', '{}:a'.format(login), work_data)

            # validate that an association error occurred
            self.assertEqual(resp.status_code, 422)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(
                body['message'],
                "No associated item found with value '{}' for field "
                "'{}'".format(
                    value, desc_by_field[field])
            )

            # regex for error message provided: check it
            if len(entry) > 2:
                body = json.loads(resp.get_data(as_text=True))
                self.assertRegex(body['message'], entry[2])

        # for update, create an item with good values first
        item = self._create_many_entries(login, 1)[0][0]
        # apply wrong values
        for entry in wrong_fields:
            field = entry[0]
            value = entry[1]
            work_data = {'id': item['id']}
            work_data[field] = value
            resp = self._do_request(
                'update', '{}:a'.format(login), work_data)

            # validate that an association error occurred
            self.assertEqual(resp.status_code, 422)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(
                body['message'],
                "No associated item found with value '{}' for field "
                "'{}'".format(
                    value, desc_by_field[field])
            )

            # regex for error message provided: check it
            if len(entry) > 2:
                body = json.loads(resp.get_data(as_text=True))
                self.assertRegex(body['message'], entry[2])

    #  _test_add_update_assoc_error()

    def _test_add_update_conflict(self, login, unique_field):
        """
        Try addition and update of an item's unique field to another one that
        already exists.

        Args:
            login (str): user login to create items
            unique_field (str): name of field containing unique value
        """
        # create items to work with
        entries = self._create_many_entries(login, 2)[0]

        # try to add with same values
        add_entry = entries[0].copy()
        for pop_field in ('modifier', 'modified', 'id'):
            add_entry.pop(pop_field, None)
        resp = self._do_request(
            'create', '{}:a'.format(login), add_entry)
        # validate a conflict
        # TODO: validate return message when running under postgres
        self.assertEqual(resp.status_code, 409)

        # try an update
        updated_item = {
            'id': entries[0]['id'],
            unique_field: entries[1][unique_field],
        }
        resp = self._do_request(
            'update', '{}:a'.format(login), updated_item)
        # validate a conflict
        # TODO: validate return message when running under postgres
        self.assertEqual(resp.status_code, 409)
    # _test_update_conflict()

    def _test_update_no_role(self, login_add, logins_update, update_fields):
        """
        Try to update with users without an appropriate role to do so.

        Args:
            login_add (str): user login used to create items
            logins_update (list): logins allowed to performed update
            update_fields (dict): mapping of fields with values to update
        """
        # create the entry to work with
        entries, _ = self._create_many_entries(login_add, 1)
        # id is not updated but passed as part of the url
        update_fields['id'] = entries[0]['id']

        for login_update in logins_update:
            resp = self._do_request(
                'update', '{}:a'.format(login_update), update_fields)

            # validate the response received, should be forbidden
            self.assertEqual(resp.status_code, 403,
                             resp.get_data(as_text=True))

    # _test_update_no_role()

# TestSecureResource
