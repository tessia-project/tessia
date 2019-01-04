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
Unit test for the user_roles resource module
"""

#
# IMPORTS
#
from tessia.server.api.resources.user_roles import UserRoleResource
from tessia.server.db import models
from tests.unit.api.resources.secure_resource import TestSecureResource

import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestUserRole(TestSecureResource):
    """
    Validates the UserRole resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/user-roles'
    # model associated with this resource
    RESOURCE_MODEL = models.UserRole
    # api object associated with the resource
    RESOURCE_API = UserRoleResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            cls.db.session.add(models.User(
                login='user{}@domain.com'.format(index),
                name='USER {}'.format(index),
                title='User {} title'.format(index),
                restricted=False,
                admin=False))
            cls.db.session.commit()

            data = {
                'user': 'user{}@domain.com'.format(index),
                'project': cls._db_entries['Project'][0]['name'],
                'role': 'USER',
            }
            index += 1
            yield data
    # _entry_gen()

    def test_add_all_fields_many_roles(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying all possible fields.
        """
        # since it is not a ResourceMixin only admins have access to it
        logins = ['user_admin@domain.com']

        self._test_add_all_fields_many_roles(logins)
    # test_add_all_fields_many_roles()

    def test_add_all_fields_no_role(self):
        """
        Exercise the scenario where a user without an appropriate role tries to
        create an item and fails.
        """
        # all non admin users are not permitted to create items here
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com'
        ]
        self._test_add_all_fields_no_role(logins)
    # test_add_all_fields_no_role()

    def test_add_conflict(self):
        """
        Try to create a duplicated entry
        """
        login = 'user_admin@domain.com'
        # create items to work with
        entries = self._create_many_entries(login, 1)[0]

        # try to add with same values
        add_entry = entries[0].copy()
        add_entry.pop('id', None)
        resp = self._do_request(
            'create', '{}:a'.format(login), add_entry)
        # validate a conflict
        self.assertEqual(resp.status_code, 409)
        body = json.loads(resp.get_data(as_text=True))
        self.assertEqual(
            'An item with the provided value(s) already exists',
            body['message'])
    # test_add_conflict()

    def test_add_wrong_field(self):
        """
        Test if api correctly reports error when invalid values are used for
        a field during creation.
        """
        login = 'user_admin@domain.com'
        # specify fields with wrong types
        wrong_data = [
            ('user', '', 422),
            ('user', 'wrong_user', 422),
            ('user', 5, 400),
            ('user', True, 400),
            ('user', None, 400),
            ('project', '', 422),
            ('project', 'wrong_project', 422),
            ('project', False, 400),
            ('project', 5, 400),
            ('project', None, 400),
            ('role', '', 422),
            ('role', 'wrong_role', 422),
            ('role', False, 400),
            ('role', 5, 400),
            ('role', None, 400),
        ]
        data = next(self._get_next_entry)

        # apply wrong values for creation
        for entry in wrong_data:
            field = entry[0]
            value = entry[1]
            work_data = data.copy()
            work_data[field] = value
            resp = self._do_request(
                'create', '{}:a'.format(login), work_data)

            # validate the response received
            self.assertEqual(
                resp.status_code,
                entry[2], "'field={}','value={}'".format(field, value))
    # test_add_wrong_field()

    def test_add_missing_field(self):
        """
        Test if api correctly reports error when a mandatory field is missing
        during creation.
        """
        pop_fields = ['user', 'project', 'role']
        self._test_add_missing_field('user_admin@domain.com', pop_fields)
    # test_add_missing_field()

    def test_del_many_roles(self):
        """
        Exercise to remove entries with different roles. Only admins can do it.
        """
        combos = [
            ('user_admin@domain.com', 'user_admin@domain.com'),
        ]
        self._test_del_many_roles(combos)
    # test_del_many_roles()

    def test_del_no_role(self):
        """
        Try to remove an entry without permissions (only admins can do it).
        """
        combos = [
            ('user_admin@domain.com', 'user_restricted@domain.com'),
            ('user_admin@domain.com', 'user_user@domain.com'),
            ('user_admin@domain.com', 'user_privileged@domain.com'),
            ('user_admin@domain.com', 'user_project_admin@domain.com'),
            ('user_admin@domain.com', 'user_restricted@domain.com'),
            ('user_admin@domain.com', 'user_hw_admin@domain.com'),
        ]
        self._test_del_no_role(combos)
    # test_del_no_role()

    def test_list_and_read(self):
        """
        Verify if listing and reading permissions are correctly handled
        """
        logins = [
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]

        self._test_list_and_read('user_admin@domain.com', logins)
    # test_list_and_read()

    def test_list_and_read_restricted_no_role(self):
        """
        List entries with a restricted user without role in any project
        """
        self._test_list_and_read_restricted_no_role(
            'user_admin@domain.com', 'user_restricted@domain.com',
            allowed=False, http_code=404)
    # test_list_and_read_restricted_no_role()

    def test_list_and_read_restricted_with_role(self):
        """
        List entries with a restricted user who has a role in a project.
        """
        login_add = 'user_admin@domain.com'
        login_rest = 'user_restricted@domain.com'

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
        # add the created role to the expected list
        entries.append({
            'id': role.id, 'user': role.user,
            'project': role.project, 'role': role.role})

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

    # test_list_and_read_restricted_with_role()

    def test_list_filtered(self):
        """
        Test basic filtering capabilities
        """
        self.db.session.add(models.User(
            login='user_list_filtered@domain.com',
            name='USER LIST FILTERED',
            title='User list filtered title',
            restricted=False,
            admin=False))
        self.db.session.commit()

        filter_values = {
            'user': 'user_list_filtered@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'role': 'USER_PRIVILEGED',
        }
        self._test_list_filtered('user_admin@domain.com', filter_values)
    # test_list_filtered()

    def test_update_forbidden(self):
        """
        All update attempts should be forbidden
        """
        update_fields = {
            'user': 'some_user',
            'project': 'some_project',
            'role': 'some_role',
        }
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]
        self._test_update_no_role(
            'user_admin@domain.com', logins, update_fields)
    # test_update_forbidden()
# TestUserRole
