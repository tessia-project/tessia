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
Unit test for ip_addresses resource module
"""

#
# IMPORTS
#
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia.server.api.resources.ip_addresses import IpAddressResource
from tessia.server.db import models

import ipaddress
import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestIpAddress(TestSecureResource):
    """
    Validates the IpAddress resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/ip-addresses'
    # model associated with this resource
    RESOURCE_MODEL = models.IpAddress
    # api object associated with the resource
    RESOURCE_API = IpAddressResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        # the ip must match the 'cpc0 shared' entry pre-populated by DbUnit
        network_obj = ipaddress.ip_network('10.1.0.0/16')
        # starts at 5 because sample entry uses previous ips
        index = 5
        while True:
            data = {
                'project': cls._db_entries['Project'][0]['name'],
                'desc': '- Ip address with some *markdown*',
                'address': str(network_obj[index]),
                'subnet': 'cpc0 shared',
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
            ('desc', None),
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
        pop_fields = ['address', 'subnet']
        self._test_add_missing_field('user_hw_admin@domain.com', pop_fields)
    # test_add_missing_field()

    def test_add_update_conflict(self):
        """
        Test two scenarios:
        1- add an item with an address/subnet combination that already exists
        2- update an item to a combination that already exists
        """
        self._test_add_update_conflict('user_hw_admin@domain.com', 'address')
    # test_update_conflict()

    def test_add_update_wrong_field(self):
        """
        Test if api correctly reports error when invalid values are used for
        a field during creation and update.
        """
        error_re = "^The value '{}={}' is invalid: .*$"
        # specify fields with wrong types
        wrong_data = [
            (
                'address',
                'something wrong',
                error_re.format('address', 'something wrong'),
            ),
            (
                'address',
                '192.256.0.1',
                error_re.format('address', '192.256.0.1'),
            ),
            ('desc', False),
            ('desc', 5),
            ('project', 5),
            ('project', True),
            ('owner', False),
            ('owner', 5),
            ('subnet', 5),
            ('subnet', None),
            ('subnet', True),
            # read-only field
            ('system', 'something'),
        ]
        self._test_add_update_wrong_field(
            'user_hw_admin@domain.com', wrong_data)

        # test special cases where address is valid but not within subnet's
        # address range
        data = next(self._get_next_entry)

        def validate_resp(resp, address):
            """Helper validator"""
            self.assertEqual(resp.status_code, 400)
            msg = (
                "The value 'address={}' is invalid: ip not within "
                "subnet address range".format(address)
            )
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(msg, body['message'])
        # validate_resp()

        # exercise a creation
        data['address'] = '192.168.1.5'
        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        validate_resp(resp, data['address'])

        # exercise update, create an item with good values first
        item = self._create_many_entries('user_hw_admin@domain.com', 1)[0][0]

        # 1- only update the address, subnet doesn't change
        update_fields = {
            'id': item['id'],
            'address': '192.168.1.5',
        }
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, update_fields['address'])

        # 2- update both, create a target subnet first
        subnet = models.Subnet(
            address='172.10.0.0/24',
            gateway=None,
            dns_1=None,
            dns_2=None,
            vlan=None,
            zone='cpc0',
            name='some_subnet',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
            desc='some description'
        )
        self.db.session.add(subnet)
        self.db.session.commit()
        # set the update data
        update_fields['subnet'] = subnet.name
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, update_fields['address'])

        # 3- only update the subnet, address doesn't change
        update_fields.pop('address')
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, item['address'])

        # clean up subnet entry
        self.db.session.delete(subnet)
        self.db.session.commit()
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
        # a subnet has to be created first so that association works
        subnet = models.Subnet(
            address='10.1.0.0/24',
            gateway=None,
            dns_1=None,
            dns_2=None,
            vlan=None,
            zone='cpc0',
            name='some_subnet_for_filter',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
            desc='some description'
        )
        self.db.session.add(subnet)
        self.db.session.commit()

        filter_values = {
            'owner': 'user_user@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            # use a high address to avoid conflict with previous entries
            'address': '10.1.0.255',
            'subnet': subnet.name
        }
        self._test_list_filtered('user_hw_admin@domain.com', filter_values)

        self.db.session.delete(subnet)
        self.db.session.commit()
    # test_list_filtered()

    def test_update_valid_fields(self):
        """
        Exercise the update of existing objects when correct format and
        writable fields are specified.
        """
        # a subnet has to be created first so that association works
        subnet = models.Subnet(
            address='172.10.0.0/24',
            gateway=None,
            dns_1=None,
            dns_2=None,
            vlan=None,
            zone='cpc0',
            name='some_subnet_for_filter',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
            desc='some description'
        )
        self.db.session.add(subnet)
        self.db.session.commit()

        update_fields = {
            'address': '172.10.0.1',
            'owner': 'user_user@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'desc': 'some_desc',
            'subnet': subnet.name
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

        self.db.session.delete(subnet)
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
            ('subnet', 'some_subnet'),
        ]
        self._test_add_update_assoc_error(
            'user_hw_admin@domain.com', wrong_fields)
    # test_add_update_assoc_error()

    def test_update_no_role(self):
        """
        Try to update with a user without an appropriate role to do so.
        """
        update_fields = {
            'address': '10.1.0.255',
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

# TestIpAddress
