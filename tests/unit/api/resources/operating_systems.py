# Copyright 2018 IBM Corp.
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
Unit test for operating_systems resource module
"""

#
# IMPORTS
#
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia.server.api.resources.operating_systems import \
    OperatingSystemResource
from tessia.server.db import models

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestOperatingSystem(TestSecureResource):
    """
    Validates the SystemType resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/operating-systems'
    # model associated with this resource
    RESOURCE_MODEL = models.OperatingSystem
    # api object associated with the resource
    RESOURCE_API = OperatingSystemResource

    @staticmethod
    def _entry_gen():
        """
        Generator for producing new entries for database insertion.
        """
        index = 1
        while True:
            major = index * 2
            minor = index
            data = {
                'name': 'osid_{}.{}'.format(major, minor),
                'type': 'redhat',
                'major': major,
                'minor': minor,
                'pretty_name': 'OS Pretty name {}.{} LTS'.format(major, minor),
                'template': 'rhel7-default',
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
        self._test_add_mandatory_fields(
            'user_admin@domain.com', [('template', None),]
        )
    # test_add_mandatory_fields()

    def test_add_update_conflict(self):
        """
        Test two scenarios:
        1- add an item with a model that already exists
        2- update an item to a model that already exists
        """
        self._test_add_update_conflict('user_admin@domain.com', 'name')
    # test_add_update_conflict()

    def test_add_update_wrong_field(self):
        """
        Test if api correctly reports error when invalid values are used for
        a field during creation and update.
        """
        # specify fields with wrong types
        wrong_data = [
            ('name', 5),
            ('name', False),
            ('name', None),
            ('type', 'some_type'),
            ('type', False),
            ('type', 5),
            ('major', True),
            ('major', 'string'),
            ('minor', True),
            ('minor', 'string'),
            ('pretty_name', False),
            ('pretty_name', 5),
        ]
        self._test_add_update_wrong_field(
            'user_admin@domain.com', wrong_data)
    # test_add_update_wrong_field_format()

    def test_add_missing_field(self):
        """
        Test if api correctly reports error when a mandatory field is missing
        during creation.
        """
        pop_fields = ['name', 'type', 'major', 'minor', 'pretty_name']
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
            'type': 'suse',
            'major': 15,
            'minor': 7,
            'pretty_name': 'some_pretty_name_for_filter',
            'template': 'sles12-default',
        }
        self._test_list_filtered('user_admin@domain.com', filter_values)
    # test_list_filtered()

    def test_add_update_assoc_error(self):
        """
        Try creation and edit while setting a FK field to a value that has no
        entry in the associated table.
        """
        wrong_fields = [
            ('template', 'wrong_template'),
        ]
        self._test_add_update_assoc_error(
            'user_admin@domain.com', wrong_fields)
    # test_add_update_assoc_error()

    def test_update_valid_fields(self):
        """
        Exercise the update of existing objects when correct format and
        writable fields are specified.
        """
        update_fields = {
            'name': 'some_name_for_filter',
            'type': 'suse',
            'major': 10,
            'minor': 3,
            'pretty_name': 'some_pretty_name_for_filter',
            'template': 'sles12-default',
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
# TestOperatingSystem