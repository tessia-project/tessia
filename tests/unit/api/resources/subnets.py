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
Unit test for subnets resource module
"""

#
# IMPORTS
#
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia_engine.api.resources.subnets import SubnetResource
from tessia_engine.db import models

import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestSubnet(TestSecureResource):
    """
    Validates the Subnet resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/subnets'
    # model associated with this resource
    RESOURCE_MODEL = models.Subnet
    # api object associated with the resource
    RESOURCE_API = SubnetResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'project': cls._db_entries['Project'][0]['name'],
                'name': 'subnet {}'.format(index),
                'desc': '- Subnet with some *markdown*',
                'address': '192.168.{}.0/24'.format(index),
                'gateway': '192.168.{}.1'.format(index),
                'dns_1': '10.0.0.5',
                'dns_2': '10.0.0.6',
                'vlan': 1050,
                'zone': 'cpc0',
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
            ('gateway', None),
            ('dns_1', None),
            ('dns_2', None),
            ('vlan', None),
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
        pop_fields = ['name', 'zone']
        self._test_add_missing_field('user_hw_admin@domain.com', pop_fields)
    # test_add_missing_field()

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
        error_re = "^The value '{}={}' is invalid: .*$"
        # specify fields with wrong types
        wrong_data = [
            ('name', 5),
            (
                'address',
                'something wrong',
                error_re.format('address', 'something wrong'),
            ),
            (
                'address',
                '192.168.1.0/23',
                error_re.format('address', '192.168.1.0/23'),
            ),
            (
                'address',
                '192.168.1.0/256.255.255.0',
                error_re.format('address', '192.168.1.0/256.255.255.0'),
            ),
            (
                'gateway',
                'something wrong',
                error_re.format('gateway', 'something wrong'),
            ),
            (
                'gateway',
                '192.256.0.1',
                error_re.format('gateway', '192.256.0.1'),
            ),
            (
                'dns_1',
                'something wrong',
                error_re.format('dns_1', 'something wrong'),
            ),
            (
                'dns_1',
                '192.255.0.-1',
                error_re.format('dns_1', '192.255.0.-1'),
            ),
            (
                'dns_2',
                'something wrong',
                error_re.format('dns_2', 'something wrong'),
            ),
            (
                'dns_2',
                '200.255.256.1',
                error_re.format('dns_2', '200.255.256.1'),
            ),
            ('vlan', -5),
            ('desc', False),
            ('project', 5),
            ('owner', False),
            ('zone', 5),
        ]
        self._test_add_update_wrong_field(
            'user_hw_admin@domain.com', wrong_data)

        # test special cases where both address and gateway are valid but
        # gateway is not within address range
        data = next(self._get_next_entry)
        data['address'] = '10.0.0.0/24'
        data['gateway'] = '10.0.1.1'

        def validate_resp(resp, item, data):
            """Helper validator for gateway not within in address range"""
            self.assertEqual(resp.status_code, 400) # pylint: disable=no-member
            if 'gateway' in data:
                msg = (
                    "The value 'gateway={}' is invalid: ip not within "
                    "subnet address range".format(data['gateway'])
                )
            else:
                msg = (
                    "The value 'address={}' is invalid: 'gateway={}' must "
                    "be updated too to match new address range".format(
                        data['address'], item['gateway'])
                )
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(msg, body['message'])
        # validate_resp()

        # exercise a creation
        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        validate_resp(resp, data, data)

        # exercise update, create an item with good values first
        item = self._create_many_entries('user_hw_admin@domain.com', 1)[0][0]

        # 1- only update the network address, gateway doesn't change
        update_fields = {
            'id': item['id'],
            'address': '10.0.0.0/24',
        }
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, item, update_fields)

        # 2- update both
        update_fields['gateway'] = '10.0.1.1'
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, item, update_fields)

        # 3- only update the gateway, network address doesn't change
        update_fields.pop('address')
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, item, update_fields)

        # 4- update both, gateway is None, this should work
        update_fields['address'] = '10.0.0.0/24'
        update_fields['gateway'] = None
        self._request_and_assert(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)

        # 5- update only gateway to None, this should work
        update_fields.pop('address')
        self._request_and_assert(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)

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
        # a netzone has to be created first so that association works
        net_zone = models.NetZone(
            name='some_zone_for_filter',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
            desc='some description'
        )
        self.db.session.add(net_zone)
        self.db.session.commit()

        filter_values = {
            'owner': 'user_user@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'name': 'some_name_for_filter',
            'desc': 'some_desc_for_filter',
            'address': '10.0.0.0/22',
            'gateway': '10.0.0.1',
            'dns_1': '10.0.0.2',
            'dns_2': '10.0.0.3',
            'vlan': 5000,
            'zone': net_zone.name
        }
        self._test_list_filtered('user_hw_admin@domain.com', filter_values)

        self.db.session.delete(net_zone)
        self.db.session.commit()
    # test_list_filtered()

    def test_update_valid_fields(self):
        """
        Exercise the update of existing objects when correct format and
        writable fields are specified.
        """
        # a type has to be created first so that association works
        net_zone = models.NetZone(
            name='some_zone_for_filter',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
            desc='some description'
        )
        self.db.session.add(net_zone)
        self.db.session.commit()

        update_fields = {
            'name': 'some_name',
            'owner': 'user_user@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'desc': 'some_desc',
            'address': '10.0.0.0/22',
            'gateway': '10.0.0.1',
            'dns_1': '10.0.0.2',
            'dns_2': '10.0.0.3',
            'vlan': 5000,
            'zone': net_zone.name
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

        self.db.session.delete(net_zone)
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
            ('zone', 'some_zone'),
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
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com'
        ]
        self._test_update_no_role(
            'user_hw_admin@domain.com', logins, update_fields)
    # test_update_no_role()

# TestSubnet
