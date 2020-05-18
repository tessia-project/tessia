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
Unit test for storage_servers resource module
"""

#
# IMPORTS
#
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia.server.api.resources.storage_servers import StorageServerResource
from tessia.server.db import models

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestStorageServer(TestSecureResource):
    """
    Validates the StorageServer resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/storage-servers'
    # model associated with this resource
    RESOURCE_MODEL = models.StorageServer
    # api object associated with the resource
    RESOURCE_API = StorageServerResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'project': cls._db_entries['Project'][0]['name'],
                'desc': '- Storage server with some *markdown*',
                'name': 'storage-server {}'.format(index),
                'hostname': 'server{}.domain.com'.format(index),
                'model': 'Storage server model {}'.format(index),
                'type': 'DASD-FCP',
                'fw_level': 'Firmware level',
            }
            index += 1
            yield data
    # _entry_gen()

    def test_add_all_fields_many_roles(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying all possible fields.
        """
        logins = ['user_hw_admin@domain.com', 'user_admin@domain.com']

        self._test_add_all_fields_many_roles(logins)
    # test_add_all_fields_many_roles()

    def test_add_all_fields_no_role(self):
        """
        Exercise the scenario where a normal user without permissions tries to
        create an item and fails.
        """
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
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
            ('hostname', None),
            ('fw_level', None),
            ('desc', None),
            ('project', self._db_entries['Project'][0]['name']),
        ]
        self._test_add_mandatory_fields('user_hw_admin@domain.com', pop_fields)
    # test_add_mandatory_fields()

    def test_add_mandatory_fields_as_admin(self):
        """
        Exercise the scenario where using the admin user to create an item
        makes project a mandatory field.
        """
        self._test_add_mandatory_fields_as_admin('user_admin@domain.com')
    # test_add_mandatory_fields_as_admin()

    def test_add_missing_field(self):
        """
        Test if api correctly reports error when a mandatory field is missing
        during creation.
        """
        pop_fields = ['name', 'model', 'type']
        self._test_add_missing_field('user_hw_admin@domain.com', pop_fields)
    # test_add_missing_field()

    def test_add_update_conflict(self):
        """
        Test two scenarios:
        1- add an item with a name that already exists
        2- update an item to a name that already exists
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
            ('name', ''),
            ('name', ' '),
            ('name', ' name'),
            ('name', 'name with * symbol'),
            ('name', 5),
            ('hostname', True),
            ('model', 5),
            ('fw_level', True),
            ('desc', 5),
            ('type', False),
            ('project', 5),
            ('owner', False),
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
        Try to delete an item which has a volume associated with it.
        """
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]

        # create the dependent object
        dep_volume = models.StorageVolume(
            volume_id='AAAA',
            server_id=entry['id'],
            system_id=None,
            type='DASD',
            pool_id=None,
            size=10000,
            part_table={},
            specs={},
            system_attributes={},
            modifier="user_hw_admin@domain.com",
            desc="",
            project=self._db_entries['Project'][0]['name'],
            owner="user_hw_admin@domain.com"
        )
        self._test_del_has_dependent(
            'user_hw_admin@domain.com', entry['id'], dep_volume)
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
        ]
        self._test_del_no_role(combos)

        # restricted user has no access to the item
        combos = [
            ('user_admin@domain.com', 'user_restricted@domain.com'),
        ]
        self._test_del_no_role(combos, http_code=404)
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
            'user_hw_admin@domain.com', 'user_restricted@domain.com',
            http_code=404)
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
        # a type has to be created first so that association works
        server_type = models.StorageServerType(
            name='some_type_for_filter',
            desc='some description'
        )
        self.db.session.add(server_type)
        self.db.session.commit()

        filter_values = {
            'owner': 'user_user@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'name': 'some_name_for_filter',
            'desc': 'some_desc_for_filter',
            'fw_level': 'some_fw_level_for_filter',
            'hostname': 'some_hostname_for_filter',
            'model': 'some_model_for_filter',
            'type': 'some_type_for_filter',
        }
        self._test_list_filtered('user_hw_admin@domain.com', filter_values)

        self.db.session.delete(server_type)
        self.db.session.commit()
    # test_list_filtered()

    def test_update_project(self):
        """
        Exercise the update of the item's project. For that operation a user
        requires permission on both projects.
        """
        self._test_update_project()
    # test_update_project()

    def test_update_valid_fields(self):
        """
        Exercise the update of existing objects when correct format and
        writable fields are specified.
        """
        # a type has to be created first so that association works
        server_type = models.StorageServerType(
            name='some_type',
            desc='some description'
        )
        self.db.session.add(server_type)
        self.db.session.commit()

        update_fields = {
            'name': 'some_name',
            'owner': 'user_user@domain.com',
            'desc': 'some_desc',
            'fw_level': 'some_fw_level',
            'hostname': 'some_hostname',
            'model': 'some_model',
            'type': 'some_type',
        }

        # combinations owner/updater
        combos = [
            # combinations to exercise the use of the UPDATE permission in the
            # role
            ('user_hw_admin@domain.com', 'user_admin@domain.com'),
            ('user_admin@domain.com', 'user_hw_admin@domain.com'),
        ]
        self._test_update_valid_fields(
            'user_hw_admin@domain.com', combos, update_fields)

        self.db.session.delete(server_type)
        self.db.session.commit()
    # test_update_valid_fields()

    def test_add_update_assoc_error(self):
        """
        Try creation and edit while setting a FK field to a value that has no
        entry in the associated table.
        """
        wrong_fields = [
            ('project', 'some_project'),
            ('owner', 'some_owner'),
            ('type', 'some_type'),
        ]
        self._test_add_update_assoc_error(
            'user_hw_admin@domain.com', wrong_fields)
    # test_add_update_assoc_error()

    def test_update_no_role(self):
        """
        Try to update with a user without an appropriate role to do so.
        """
        update_fields = {
            'name': 'this_should_not_work',
        }
        logins = [
            'user_privileged@domain.com',
            'user_user@domain.com',
            'user_project_admin@domain.com'
        ]
        self._test_update_no_role(
            'user_hw_admin@domain.com', logins, update_fields)

        # restricted has no read access to the item
        logins = [
            'user_restricted@domain.com',
        ]
        self._test_update_no_role(
            'user_hw_admin@domain.com', logins, update_fields, http_code=404)
    # test_update_no_role()
# TestStorageServer
