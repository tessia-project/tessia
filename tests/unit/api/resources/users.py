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
Unit test for users resource module
"""

#
# IMPORTS
#
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia.server.api.resources.users import UserResource
from tessia.server.db import models

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestUser(TestSecureResource):
    """
    Validates the User resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/users'
    # model associated with this resource
    RESOURCE_MODEL = models.User
    # api object associated with the resource
    RESOURCE_API = UserResource

    @staticmethod
    def _entry_gen():
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'login': 'user{}@domain.com'.format(index),
                'name': 'USER {}'.format(index),
                'title': 'User {} title'.format(index),
                'restricted': False,
                'admin': False,
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

    def test_add_mandatory_fields(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying only the mandatory fields.
        """
        self._test_add_mandatory_fields('user_admin@domain.com', [])
    # test_add_mandatory_fields()

    def test_add_update_conflict(self):
        """
        Test two scenarios:
        1- add an item with a login that already exists
        2- update an item to a login that already exists
        """
        self._test_add_update_conflict('user_admin@domain.com', 'login')
    # test_add_update_conflict()

    def test_add_update_wrong_field(self):
        """
        Test if api correctly reports error when invalid values are used for
        a field during creation.
        """
        # specify fields with wrong types
        wrong_data = [
            ('name', ''),
            ('name', ' '),
            ('name', ' name'),
            ('name', 'name with * symbol'),
            ('name', 5),
            ('name', True),
            ('name', None),
            ('login', False),
            ('login', 5),
            ('login', None),
            ('title', False),
            ('title', 5),
            ('restricted', None),
            ('restricted', 5),
            ('restricted', 'something_wrong'),
            ('admin', None),
            ('admin', 5),
            ('admin', 'something_wrong'),
        ]
        self._test_add_update_wrong_field(
            'user_admin@domain.com', wrong_data)
    # test_add_update_wrong_field()

    def test_add_missing_field(self):
        """
        Test if api correctly reports error when a mandatory field is missing
        during creation.
        """
        pop_fields = ['login', 'name', 'admin', 'restricted']
        self._test_add_missing_field('user_admin@domain.com', pop_fields)
    # test_add_missing_field()

    def test_del_many_roles(self):
        """
        Exercise to remove entries with different roles. For this type of
        resource only admins can do it.
        """
        combos = [
            ('user_admin@domain.com', 'user_admin@domain.com'),
        ]
        self._test_del_many_roles(combos)
    # test_del_many_roles()

    def test_del_no_role(self):
        """
        Try to remove an entry without permissions
        """
        combos = [
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
            'user_admin@domain.com', 'user_restricted@domain.com')
    # test_list_and_read_restricted_no_role()

    def test_list_filtered(self):
        """
        Test basic filtering capabilities
        """
        filter_values = {
            'name': 'some_name_for_filter',
            'login': 'some_login_for_filter',
            'title': 'some_title_for_filter',
            'admin': True,
            'restricted': True,
        }
        self._test_list_filtered('user_admin@domain.com', filter_values)
    # test_list_filtered()

    def test_update_valid_fields(self):
        """
        Exercise the update of existing objects when correct format and
        writable fields are specified.
        """
        update_fields = {
            'name': 'some_name',
            'login': 'some_login',
            'title': 'some_login',
            'restricted': True,
            'admin': True,
        }
        valid_roles = ['user_admin@domain.com']

        self._test_update_valid_fields(
            'user_admin@domain.com', valid_roles, update_fields)
    # test_update_valid_fields()

    def test_update_no_role(self):
        """
        Try to update with a user without an appropriate role to do so.
        """
        update_fields = {
            'name': 'this_should_not_work',
        }
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com'
        ]
        self._test_update_no_role(
            'user_admin@domain.com', logins, update_fields)
    # test_update_no_role()
# TestUser
