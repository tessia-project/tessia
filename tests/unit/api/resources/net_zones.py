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
Unit test for net_zones resource module
"""

#
# IMPORTS
#
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia_engine.api.resources.net_zones import NetZoneResource
from tessia_engine.db import models

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestNetZone(TestSecureResource):
    """
    Validates the NetZone resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/net-zones'
    # model associated with this resource
    RESOURCE_MODEL = models.NetZone
    # api object associated with the resource
    RESOURCE_API = NetZoneResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'project': cls._db_entries['Project'][0]['name'],
                'desc': '- Zone with some *markdown*',
                'name': 'new-zone {}'.format(index)
            }
            index += 1
            yield data
    # _entry_gen()

    def test_add_all_fields_many_roles(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying all possible fields.
        """
        logins = [
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com'
        ]

        self._test_add_all_fields_many_roles(logins)
    # test_add_all_fields_many_roles()

    def test_add_all_fields_no_role(self):
        """
        Exercise the scenario where a normal user without permissions tries to
        create an item and fails.
        """
        logins = [
            'user_restricted@domain.com',
        ]

        self._test_add_all_fields_no_role(logins)
    # test_add_all_fields_no_role()

    def test_add_mandatory_fields(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying only the mandatory fields.
        """
        # the fields to be omitted and their expected values on response
        pop_fields = [
            ('desc', None),
            ('project', self._db_entries['Project'][0]['name']),
        ]
        self._test_add_mandatory_fields('user_hw_admin@domain.com', pop_fields)
    # test_add_mandatory_fields()

    def test_add_missing_field(self):
        """
        Test if api correctly reports error when a mandatory field is missing
        during creation.
        """
        pop_fields = ['name']
        self._test_add_missing_field('user_hw_admin@domain.com', pop_fields)
    # test_add_missing_field()

    def test_add_mandatory_fields_as_admin(self):
        """
        Exercise the scenario where using the admin user to create an item
        makes project a mandatory field.
        """
        self._test_add_mandatory_fields_as_admin('user_admin@domain.com')
    # test_add_mandatory_fields_as_admin()

    def test_add_update_conflict(self):
        """
        Test two scenarios:
        1- add an item with a name that already exists
        2- update an item to a name that already exists
        """
        self._test_add_update_conflict('user_hw_admin@domain.com', 'name')
    # test_update_conflict()

    def test_add_update_wrong_field(self):
        """
        Test if api correctly reports error when invalid values are used for
        a field during creation and update.
        """
        # specify fields with wrong types
        wrong_data = [
            ('name', 5),
            ('desc', False),
        ]
        self._test_add_update_wrong_field(
            'user_hw_admin@domain.com', wrong_data)
    # test_add_update_wrong_field()

    def test_del_many_roles(self):
        """
        Exercise to remove entries with different roles
        """
        combos = [
            ('user_hw_admin@domain.com', 'user_hw_admin@domain.com'),
            ('user_hw_admin@domain.com', 'user_admin@domain.com'),
            ('user_admin@domain.com', 'user_admin@domain.com'),
            ('user_admin@domain.com', 'user_hw_admin@domain.com'),
        ]
        self._test_del_many_roles(combos)
    # test_del_many_roles()

    def test_del_has_dependent(self):
        """
        Try to delete an item which has a subnet associated with it.
        """
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]

        dep_subnet = models.Subnet(
            name="some_subnet",
            zone=entry['name'],
            address="192.168.0.0/24",
            modifier="user_hw_admin@domain.com",
            desc="",
            vlan=1801,
            project=self._db_entries['Project'][0]['name'],
            gateway=None,
            dns_1=None,
            dns_2=None,
            owner="user_hw_admin@domain.com"
        )
        self._test_del_has_dependent(
            'user_hw_admin@domain.com', entry['id'], dep_subnet)
    # test_del_has_dependent()

    def test_del_invalid_id(self):
        """
        Test if api correctly handles the case when trying to delete an
        invalid id
        """
        self._test_del_invalid_id()
    # test_del_invalid_id()

    def test_del_no_role(self):
        """
        Try to remove an entry without permissions
        """
        combos = [
            ('user_admin@domain.com', 'user_user@domain.com'),
            ('user_admin@domain.com', 'user_privileged@domain.com'),
            ('user_admin@domain.com', 'user_project_admin@domain.com'),
            ('user_admin@domain.com', 'user_restricted@domain.com'),
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

        self._test_list_and_read('user_hw_admin@domain.com', logins)
    # test_list_and_read()

    def test_list_and_read_restricted_no_role(self):
        """
        List entries with a restricted user without role in any project
        """
        self._test_list_and_read_restricted_no_role(
            'user_hw_admin@domain.com', 'user_restricted@domain.com')
    # test_list_and_read_restricted_no_role()

    def test_list_and_read_restricted_with_role(self):
        """
        List entries with a restricted user who has a role in a project
        """
        self._test_list_and_read_restricted_with_role(
            'user_hw_admin@domain.com', 'user_restricted@domain.com')
    # test_list_and_read_restricted_with_role()

    def test_list_filtered(self):
        """
        Test basic filtering capabilities
        """
        filter_values = {
            'owner': 'user_user@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'name': 'some_name_for_filter',
            'desc': 'some_desc_for_filter',
        }
        self._test_list_filtered('user_hw_admin@domain.com', filter_values)
    # test_list_filtered()

    def test_update_valid_fields(self):
        """
        Exercise the update of existing objects when correct format and
        writable fields are specified.
        """
        update_fields = {
            'name': 'some_name',
            'owner': 'user_user@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'desc': 'some_desc',
        }

        # combinations owner/updater
        combos = [
            # combinations to exercise the use of the UPDATE permission in the
            # role
            ('user_hw_admin@domain.com', 'user_admin@domain.com'),
            ('user_admin@domain.com', 'user_hw_admin@domain.com'),
            # combinations to exercise updating an item owned by the user
            ('user_restricted@domain.com', 'user_restricted@domain.com'),
            ('user_user@domain.com', 'user_user@domain.com'),
            ('user_privileged@domain.com', 'user_privileged@domain.com'),
            ('user_project_admin@domain.com', 'user_project_admin@domain.com'),
        ]

        self._test_update_valid_fields(
            'user_hw_admin@domain.com', combos, update_fields)
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
            'user_privileged@domain.com',
            'user_user@domain.com',
            'user_project_admin@domain.com'
        ]
        self._test_update_no_role(
            'user_hw_admin@domain.com', logins, update_fields)
    # test_update_no_role()
# TestNetZone
