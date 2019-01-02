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
Unit test for systems resource module
"""

#
# IMPORTS
#
from tessia.server.api.resources.systems import SystemResource
from tessia.server.api.resources.systems import MSG_BAD_COMBO
from tessia.server.db import models
from tests.unit.api.resources.secure_resource import TestSecureResource

import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestSystems(TestSecureResource):
    """
    Validates the Systems resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/systems'
    # model associated with this resource
    RESOURCE_MODEL = models.System
    # api resource
    RESOURCE_API = SystemResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'project': cls._db_entries['Project'][0]['name'],
                'desc': '- System with some *markdown*',
                'name': 'System {}'.format(index),
                'hostname': 'system{}.domain.com'.format(index),
                'hypervisor': 'cpc0',
                'model': 'ZGENERIC',
                'type': 'LPAR',
                'state': 'AVAILABLE',
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
            ('hypervisor', None),
            ('model', 'ZGENERIC'),
            ('state', 'AVAILABLE')
        ]
        self._test_add_mandatory_fields('user_user@domain.com', pop_fields)
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
        pop_fields = ['name', 'type']
        self._test_add_missing_field('user_user@domain.com', pop_fields)
    # test_add_missing_field()

    def test_add_update_conflict(self):
        """
        Test two scenarios:
        1- add an item with a system name that already exists
        2- update an item to a system name that already exists
        """
        self._test_add_update_conflict('user_user@domain.com', 'name')
    # test_update_conflict()

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
            ('name', True),
            ('name', None),
            ('hostname', 5),
            ('hostname', True),
            ('model', 5),
            ('model', True),
            ('state', 5),
            ('type', 5),
            ('type', None),
            ('hypervisor', 5),
            ('hypervisor', True),
            ('desc', False),
            ('project', 5),
            ('project', False),
            ('owner', False),
            # read-only fields
            ('modified', 'something'),
            ('modifier', 'something'),
        ]
        self._test_add_update_wrong_field(
            'user_user@domain.com', wrong_data)

        # test special cases when guest type does not match hypervisor's
        def validate_resp(resp, msg):
            """Helper validator"""
            self.assertEqual(resp.status_code, 422)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(msg, body['message'])
        # validate_resp()

        create_data = next(self._get_next_entry)
        orig_hyp = create_data['hypervisor']
        update_data = self._create_many_entries(
            'user_admin@domain.com', 1)[0][0]
        update_data = {
            'id': update_data['id']
        }

        for action, data in (
                ('create', create_data), ('update', update_data),):
            # 1- invalid hypervisor
            data['hypervisor'] = 'something_wrong'
            resp = self._do_request(action, 'user_admin@domain.com:a', data)
            msg = (
                "No associated item found with value 'something_wrong' "
                "for field '{}'".format(
                    self.RESOURCE_API.Schema.hypervisor.description)
            )
            validate_resp(resp, msg)

            # 2- invalid type
            data['hypervisor'] = orig_hyp
            data['type'] = 'something_wrong'
            msg = (
                "No associated item found with value 'something_wrong' "
                "for field '{}'".format(
                    self.RESOURCE_API.Schema.type.description)
            )
            resp = self._do_request(action, 'user_admin@domain.com:a', data)
            validate_resp(resp, msg)

            # 3- invalid combination (KVM guest of CPC)
            data['type'] = 'KVM'
            data['hypervisor'] = 'cpc0'
            resp = self._do_request(action, 'user_admin@domain.com:a', data)
            validate_resp(resp, MSG_BAD_COMBO)

        # 4- valid combination, check that model is auto set to hypervisor's
        hyp_model = self.RESOURCE_MODEL.query.filter_by(
            name='cpc0').one().model
        create_data.pop('model')
        create_data['type'] = 'LPAR'
        create_data['hypervisor'] = 'cpc0'
        resp = self._do_request(
            'create', 'user_admin@domain.com:a', create_data)
        create_data['model'] = hyp_model
        self._assert_created(resp, create_data)
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
            ('user_user@domain.com', 'user_user@domain.com'),
            ('user_user@domain.com', 'user_project_admin@domain.com'),
            ('user_privileged@domain.com', 'user_privileged@domain.com'),
            ('user_privileged@domain.com', 'user_project_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_project_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_hw_admin@domain.com'),
        ]
        self._test_del_many_roles(combos)
    # test_del_many_roles()

    def test_del_has_dependent(self):
        """
        Try to delete an item which has a system profile associated with it.
        """
        entry = self._create_many_entries(
            'user_admin@domain.com', 1)[0][0]

        hyp = self.RESOURCE_MODEL.query.filter_by(
            name=entry['hypervisor']).one()
        self._test_del_has_dependent(
            'user_admin@domain.com', hyp.id, None)
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
            'user_user@domain.com', 'user_restricted@domain.com')
    # test_list_and_read_restricted_no_role()

    def test_list_and_read_restricted_with_role(self):
        """
        List entries with a restricted user who has a role in a project
        """
        self._test_list_and_read_restricted_with_role(
            'user_user@domain.com', 'user_restricted@domain.com')
    # test_list_and_read_restricted_with_role()

    def test_list_filtered(self):
        """
        Test basic filtering capabilities
        """
        # part_table and specs are not searchable so we don't add them
        filter_values = {
            'owner': 'user_project_admin@domain.com',
            'modifier': 'user_project_admin@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'name': 'some_name_for_filter',
            'hostname': 'some_hostname_for_filter',
            'hypervisor': 'cpc0',
            'model': 'ZGENERIC',
            'type': 'KVM',
            'state': 'LOCKED',
        }
        self._test_list_filtered('user_user@domain.com', filter_values)
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
        entry = self._create_many_entries(
            'user_user@domain.com', 1)[0][0]

        update_fields = {
            'owner': 'user_project_admin@domain.com',
            'name': 'some_name',
            'hostname': 'some_hostname',
            'hypervisor': entry['name'],
            'model': 'ZEC12_H20',
            'type': 'KVM',
            'state': 'LOCKED',
        }

        # combinations owner/updater
        combos = [
            # combinations to exercise the use of the UPDATE permission in the
            # role
            ('user_hw_admin@domain.com', 'user_admin@domain.com'),
            ('user_admin@domain.com', 'user_hw_admin@domain.com'),
            ('user_user@domain.com', 'user_privileged@domain.com'),
            ('user_user@domain.com', 'user_project_admin@domain.com'),
            ('user_user@domain.com', 'user_hw_admin@domain.com'),
            ('user_user@domain.com', 'user_admin@domain.com'),
            ('user_privileged@domain.com', 'user_project_admin@domain.com'),
            ('user_privileged@domain.com', 'user_hw_admin@domain.com'),
            ('user_privileged@domain.com', 'user_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_privileged@domain.com'),
            ('user_project_admin@domain.com', 'user_hw_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_admin@domain.com'),
            # combinations to exercise updating an item owned by the user
            ('user_restricted@domain.com', 'user_restricted@domain.com'),
            ('user_user@domain.com', 'user_user@domain.com'),
        ]
        self._test_update_valid_fields(
            'user_hw_admin@domain.com', combos, update_fields)

        # perform a simple update of type without changing hypervisor to
        # reach specific if clause in resource api code
        update_fields = {
            'type': 'LPAR'
        }
        self._test_update_valid_fields(
            'user_hw_admin@domain.com',
            [('user_user@domain.com', 'user_user@domain.com')],
            update_fields)

    # test_update_valid_fields()

    def test_add_update_assoc_error(self):
        """
        Try creation and edit while setting a FK field to a value that has no
        entry in the associated table.
        """
        wrong_fields = [
            ('project', 'some_project'),
            ('owner', 'some_owner'),
            ('hypervisor', 'some_hypervisor'),
            ('state', 'some_state'),
            ('type', 'some_type'),
            ('model', 'some_model'),
        ]
        self._test_add_update_assoc_error(
            'user_project_admin@domain.com', wrong_fields)
    # test_add_update_assoc_error()

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
        ]
        self._test_update_no_role(
            'user_hw_admin@domain.com', logins, update_fields)
    # test_update_no_role()

# TestSystem
