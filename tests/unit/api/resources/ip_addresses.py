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
import time

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

    def _assert_failed_req(self, resp, http_code, msg=None):
        """
        Help assert that a given request failed with the specified http code
        and the specified message.

        Args:
            resp (Response): flask response object
            http_code (int): HTTP error code expected
            msg (str): expected message in response
        """
        self.assertEqual(resp.status_code, http_code)
        body = json.loads(resp.get_data(as_text=True))
        if msg:
            self.assertEqual(msg, body['message'])
    # _assert_failed_req()

    def test_add_all_fields_many_roles(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying all possible fields.
        """
        logins = ['user_hw_admin@domain.com', 'user_admin@domain.com']

        # create ip without system, user has permission to ip
        self._test_add_all_fields_many_roles(logins)

        system = models.System(
            name='New system',
            hostname='new_system.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='admin',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(system)
        self.db.session.commit()
        # create ip with system, user has permission to both
        ip_new = next(self._get_next_entry)
        ip_new['system'] = 'New system'
        created_id = self._request_and_assert(
            'create', '{}:a'.format('user_hw_admin@domain.com'), ip_new)

        # clean up
        self.db.session.query(self.RESOURCE_MODEL).filter_by(
            id=created_id).delete()
        self.db.session.delete(system)
        self.db.session.commit()
    # test_add_all_fields_many_roles()

    def test_add_all_fields_no_role(self):
        """
        Exercise the scenario where a normal user without permissions tries to
        create an item and fails.
        """
        logins = [
            ('user_user@domain.com', 403),
            ('user_privileged@domain.com', 403),
            ('user_project_admin@domain.com', 403),
            ('user_restricted@domain.com', 422),
        ]

        # create ip without system, user has no permission to ip
        # note that restricted has no access to subnet
        self._test_add_all_fields_no_role([login[0] for login in logins[:-1]])
        self._test_add_all_fields_no_role([logins[-1][0]],
                                          http_code=logins[-1][1])

        sys_name = 'New system for test_add_all_fields_no_role'
        system = models.System(
            name=sys_name,
            hostname='new_system.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='admin',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(system)
        self.db.session.commit()
        # create ip with system, user has permission to system but not to ip
        for login, http_code in logins:
            system.owner = login
            self.db.session.add(system)
            self.db.session.commit()
            data = next(self._get_next_entry)
            data['owner'] = login
            data['system'] = sys_name
            resp = self._do_request('create', '{}:a'.format(login), data)
            # validate the response received, should be forbidden
            expected_response = {
                403: 'User has no CREATE permission for the '
                     'specified project',
                422: "No associated item found with value 'cpc0 shared' for "
                     "field 'Part of subnet'"
            }
            self._assert_failed_req(
                resp, http_code,
                expected_response[http_code]
            )
            # try without specifying project
            data['project'] = None
            expected_response = {
                403: 'No CREATE permission found for the user in any project',
                422: "No associated item found with value 'cpc0 shared' for "
                     "field 'Part of subnet'"
            }
            resp = self._do_request('create', '{}:a'.format(login), data)
            self._assert_failed_req(
                resp, http_code,
                expected_response[http_code]
            )

        # create ip with system, user has permission to ip but not to system
        system.owner = 'user_admin@domain.com'
        system.project = self._db_entries['Project'][1]['name']
        self.db.session.add(system)
        self.db.session.commit()
        for login, http_code in logins + [('user_hw_admin@domain.com', 403)]:
            data = next(self._get_next_entry)
            data['owner'] = login
            data['system'] = sys_name
            resp = self._do_request('create', '{}:a'.format(login), data)
            # validate the response received, should be forbidden
            expected_response = {
                403: 'User has no UPDATE permission for the specified system',
                422: "No associated item found with value 'cpc0 shared' for "
                     "field 'Part of subnet'"
            }
            self._assert_failed_req(resp, http_code,
                                    expected_response[http_code])
            # try without specifying project
            data['project'] = None
            self._assert_failed_req(resp, http_code,
                                    expected_response[http_code])

        self.db.session.delete(system)
        self.db.session.commit()
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

    def test_add_update_assoc_error(self):
        """
        Try creation and edit while setting a FK field to a value that has no
        entry in the associated table.
        """
        wrong_fields = [
            ('project', 'some_project'),
            ('owner', 'some_owner'),
            ('system', 'some_wrong_system'),
        ]
        self._test_add_update_assoc_error(
            'user_hw_admin@domain.com', wrong_fields)

        # special case: subnet can only be specified for create, not update
        data = next(self._get_next_entry)
        data['subnet'] = 'some wrong subnet'
        resp = self._do_request('create', 'user_hw_admin@domain.com:a', data)
        error_msg = ("No associated item found with value '{subnet}' for "
                     "field 'Part of subnet'".format(**data))
        self._assert_failed_req(resp, 422, error_msg)
    # test_add_update_assoc_error()

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
            ('system', False),
            ('system', {'invalid': 'something'}),
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

        # update the address
        update_fields = {
            'id': item['id'],
            'address': '192.168.1.5',
        }
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, update_fields['address'])

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
        user_res = 'user_restricted@domain.com'

        # ips without system, restricted user without role in project
        self._test_list_and_read_restricted_no_role(
            'user_hw_admin@domain.com', user_res, http_code=404)

        # list/read ips with system, restricted user has no role in system's
        # project
        sys_name = 'New system for test_list_and_read_restricted_no_role'
        sys_obj = models.System(
            name=sys_name,
            hostname='new_system.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='admin',
            modifier='admin',
            # IMPORTANT: project where user has no role
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(sys_obj)
        self.db.session.commit()

        # create the entries with system assigned
        time_range = [int(time.time() - 5)]
        entries = []
        for _ in range(0, 5):
            data = next(self._get_next_entry)
            data['project'] = self._db_entries['Project'][0]['name']
            data['system'] = sys_name
            entries.append(
                self._request_and_assert('create', 'admin:a', data))

        # retrieve list - should be empty
        resp = self._do_request('list', '{}:a'.format(user_res), None)
        self._assert_listed_or_read(resp, [], time_range)

        # perform a read - expected a 404 'not found'
        for entry_id in entries:
            resp = self._do_request('get', '{}:a'.format(user_res), entry_id)
            self.assertEqual(resp.status_code, 404)
            # clean up
            self.db.session.query(self.RESOURCE_MODEL).filter_by(
                id=entry_id).delete()
            self.db.session.commit()

        self.db.session.delete(sys_obj)
        self.db.session.commit()
    # test_list_and_read_restricted_no_role()

    def test_list_and_read_restricted_with_role(self):
        """
        List entries with a restricted user who has a role in a project
        """
        user_res = 'user_restricted@domain.com'
        time_range = [int(time.time() - 5)]

        # ips without system, restricted user has role in project
        self._test_list_and_read_restricted_with_role(
            'user_hw_admin@domain.com', 'user_restricted@domain.com')

        # store the existing entries and add them to the new ones for
        # later validation
        resp = self._do_request(
            'list', 'admin:a',
            'where={}'.format(json.dumps(
                {'project': self._db_entries['Project'][0]['name']}))
        )
        entries = json.loads(resp.get_data(as_text=True))
        # adjust id field to make the http response look like the same as the
        # dict from the _create_many_entries return
        for entry in entries:
            entry['id'] = entry.pop('$uri').split('/')[-1]

        # list/read ips with system, restricted user has role in system's
        # project
        sys_name = 'New system for test_list_and_read_restricted_with_role'
        sys_obj = models.System(
            name=sys_name,
            hostname='new_system.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(sys_obj)
        # add the role for the restricted user
        role = models.UserRole(
            project=self._db_entries['Project'][0]['name'],
            user=user_res,
            role="USER"
        )
        self.db.session.add(role)
        self.db.session.commit()

        # create the entries with system assigned
        for _ in range(0, 5):
            data = next(self._get_next_entry)
            data['project'] = self._db_entries['Project'][0]['name']
            data['system'] = sys_name
            created_id = self._request_and_assert('create', 'admin:a', data)
            data['id'] = created_id
            entries.append(data)
        time_range.append(int(time.time() + 5))

        # retrieve list
        resp = self._do_request('list', '{}:a'.format(user_res), None)
        self._assert_listed_or_read(resp, entries, time_range)

        # perform a read
        for entry in entries:
            resp = self._do_request(
                'get', '{}:a'.format(user_res), entry['id'])
            self._assert_listed_or_read(
                resp, [entry], time_range, read=True)
            # clean up
            self.db.session.query(self.RESOURCE_MODEL).filter_by(
                id=entry['id']).delete()
            self.db.session.commit()

        self.db.session.delete(sys_obj)
        self.db.session.commit()
    # test_list_and_read_restricted_with_role()

    def test_list_filtered(self):
        """
        Test basic filtering capabilities
        """
        # set requester for next queries
        self._do_request('list', '{}:a'.format('user_hw_admin@domain.com'))

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

    def test_update_has_role(self):
        """
        Exercise update scenarios involving different permission combinations
        """
        sys_name = 'New system for test_update_has_role'
        sys_obj = models.System(
            name=sys_name,
            hostname='new_system.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(sys_obj)
        iface_obj = models.SystemIface(
            name='iface_test_update_has_role',
            osname='eth0',
            system=sys_name,
            type='OSA',
            ip_address=None,
            mac_address='00:11:22:33:44:55',
            attributes={'ccwgroup': '0.0.f101,0.0.f102,0.0.f103',
                        'layer2': True},
            desc='Description iface'
        )
        self.db.session.add(iface_obj)
        sys_name_2 = 'New system for test_update_has_role 2'
        sys_obj_2 = models.System(
            name=sys_name_2,
            hostname='new_system_2.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(sys_obj_2)
        self.db.session.commit()
        iface_id = iface_obj.id

        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]
        for login in logins:
            orig_data = next(self._get_next_entry)
            orig_data['owner'] = login
            ip_id = self._request_and_assert(
                'create', '{}:a'.format('user_hw_admin@domain.com'), orig_data)
            # exercise case where user is system owner
            if login in ('user_restricted@domain.com', 'user_user@domain.com'):
                sys_obj.owner = login
            # exercise case where user has permission through a role
            else:
                sys_obj.owner = 'admin'
            sys_obj.project = self._db_entries['Project'][0]['name']
            self.db.session.add(sys_obj)
            self.db.session.commit()

            # update ip assign system, user has permission to both ip and
            # system
            data = {'id': ip_id, 'system': sys_name}
            self._request_and_assert('update', '{}:a'.format(login), data)
            self.assertEqual(
                self.RESOURCE_MODEL.query.filter_by(id=ip_id).one().system,
                sys_name, 'System was not assigned to ip')

            # update ip re-assign to same system, iface associations are
            # preserved
            # first associate to an interface
            iface_obj = models.SystemIface.query.filter_by(id=iface_id).one()
            iface_obj.ip_address = '{subnet}/{address}'.format(**orig_data)
            self.db.session.add(iface_obj)
            self.db.session.commit()
            # perform request
            data = {'id': ip_id, 'system': sys_name}
            self._request_and_assert('update', '{}:a'.format(login), data)
            self.assertEqual(
                self.RESOURCE_MODEL.query.filter_by(id=ip_id).one().system,
                sys_name, 'System was withdrawn from ip')
            # validate that interface association was preserved
            self.assertEqual(
                len(models.SystemIface.query.filter_by(
                    id=iface_id, ip_address_id=ip_id).all()),
                1, 'Association was not preserved'
            )

            # update ip withdraw system, user has permission to ip and
            # system
            data = {'id': ip_id, 'system': None}
            self._request_and_assert('update', '{}:a'.format(login), data)
            self.assertEqual(
                self.RESOURCE_MODEL.query.filter_by(id=ip_id).one().system,
                None, 'System was not withdrawn')
            # validate that interface association was removed
            self.assertEqual(
                models.SystemIface.query.filter_by(
                    id=iface_id).one().ip_address,
                None, 'Association to interface was not removed'
            )

            # update ip (no system update), user has permission to ip but
            # not to system
            # first, prepare the ip's permissions
            data = {'id': ip_id,
                    'project': self._db_entries['Project'][0]['name']}
            # exercise case where user has permission through a role
            if login in ('user_hw_admin@domain.com', 'user_admin@domain.com'):
                data['owner'] = 'admin'
            # exercise case where user is owner of ip
            else:
                data['owner'] = login
            self._request_and_assert('update', 'admin:a', data)
            # prepare system's permissions
            sys_obj.owner = 'admin'
            sys_obj.project = self._db_entries['Project'][1]['name']
            self.db.session.add(sys_obj)
            self.db.session.commit()
            # perform request
            data = {'id': ip_id, 'desc': 'some description'}
            self._request_and_assert('update', '{}:a'.format(login), data)

            # update ip change system, user has permission to all
            # prepare ip's permissions
            if login not in ('user_hw_admin@domain.com',
                             'user_admin@domain.com'):
                data = {'id': ip_id, 'owner': login}
            # exercise case where user has permission through a role
            else:
                data = {'id': ip_id, 'owner': 'admin'}
            self._request_and_assert('update', 'admin:a', data)
            # prepare systems' permissions
            if login in ('user_restricted@domain.com', 'user_user@domain.com'):
                sys_obj.owner = login
                sys_obj_2.owner = login
            # exercise case where user has permission through a role
            else:
                sys_obj.owner = 'admin'
                sys_obj_2.owner = 'admin'
            sys_obj.project = self._db_entries['Project'][0]['name']
            self.db.session.add(sys_obj)
            self.db.session.add(sys_obj_2)
            self.db.session.commit()
            # perform request
            data = {'id': ip_id, 'system': sys_name_2}
            self._request_and_assert('update', '{}:a'.format(login), data)
            self.assertEqual(
                self.RESOURCE_MODEL.query.filter_by(id=ip_id).one().system,
                sys_name_2, 'New system was not assigned to IP')

            # clean up
            self.RESOURCE_MODEL.query.filter_by(id=ip_id).delete()
            self.db.session.commit()

        # clean up
        self.db.session.delete(iface_obj)
        self.db.session.delete(sys_obj)
        self.db.session.delete(sys_obj_2)
        self.db.session.commit()
    # test_update_has_role()

    def test_update_no_role(self):
        """
        Try to update an ip without an appropriate role to do so.
        """
        hw_admin = 'user_hw_admin@domain.com'
        update_fields = {
            'address': next(self._get_next_entry)['address'],
            'owner': 'user_user@domain.com',
            'desc': 'some_desc',
        }
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com'
        ]
        # update ip without system, user has no permission to ip
        self._test_update_no_role(hw_admin, logins, update_fields)

        sys_name = 'New system for test_update_no_role'
        sys_obj = models.System(
            name=sys_name,
            hostname='new_system.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='admin',
            modifier=hw_admin,
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(sys_obj)
        sys_name_2 = 'New system for test_update_no_role 2'
        sys_obj_2 = models.System(
            name=sys_name_2,
            hostname='new_system.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][1]['name'],
        )
        self.db.session.add(sys_obj_2)
        self.db.session.commit()

        def assert_update(error_msg, update_user, ip_owner, sys_cur,
                          sys_target, http_code=403):
            """
            Helper function to validate update action is forbidden

            Args:
                update_user (str): login performing the update action
                ip_owner (str): set this login as owner of the ip
                sys_cur (str): name and owner of the current system
                sys_target (str): name and owner of target system
                error_msg (str): expected error message
                http_code (int): expected HTTP status code
            """
            data = next(self._get_next_entry)
            data['owner'] = ip_owner
            if sys_cur:
                data['system'] = sys_cur['name']
                sys_obj = models.System.query.filter_by(
                    name=sys_cur['name']).one_or_none()
                if sys_obj is None:
                    return
                sys_obj.owner = sys_cur['owner']
                self.db.session.add(sys_obj)
                self.db.session.commit()
            ip_id = self._request_and_assert('create', 'admin:a', data)

            if sys_target:
                sys_obj = models.System.query.filter_by(
                    name=sys_target['name']).one()
                sys_obj.owner = sys_target['owner']
                self.db.session.add(sys_obj)
                self.db.session.commit()
                sys_tgt_name = sys_target['name']
            else:
                sys_tgt_name = None

            data = {'id': ip_id, 'system': sys_tgt_name}
            resp = self._do_request('update', '{}:a'.format(update_user), data)
            # validate the response received, should be forbidden
            self._assert_failed_req(resp, http_code, error_msg)
            # clean up
            self.db.session.query(self.RESOURCE_MODEL).filter_by(
                id=ip_id).delete()
        # assert_update()

        for login in logins:
            # update ip assign system, user has permission to system but
            # not to ip
            msg = 'User has no UPDATE permission for the specified resource'
            assert_update(msg, login, hw_admin,
                          None, {'name': sys_name, 'owner': login})

            # update ip withdraw system, user has permission to system but
            # not to ip
            assert_update(msg, login, hw_admin,
                          {'name': sys_name, 'owner': login}, None)

            # update ip change system, user has permission to ip and
            # target system but not to current system
            msg = ('User has no UPDATE permission for the system '
                   'currently holding the IP address')
            assert_update(msg, login, login,
                          {'name': sys_name_2, 'owner': 'admin'},
                          {'name': sys_name, 'owner': login})

            # update ip change system, user has permission to ip and
            # current system but not to target system
            http_code = 403
            if login == 'user_restricted@domain.com':
                msg = ("No associated item found with value 'New system for "
                       "test_update_no_role 2' for field 'Assigned to system'")
                http_code = 422
            else:
                msg = 'User has no UPDATE permission for the specified system'
            assert_update(msg, login, login,
                          {'name': sys_name, 'owner': login},
                          {'name': sys_name_2, 'owner': 'admin'},
                          http_code=http_code)

        for login in ('user_restricted@domain.com', 'user_user@domain.com'):
            # update ip assign system, user has permission to ip but not
            # to system
            msg = 'User has no UPDATE permission for the specified system'
            assert_update(msg, login, login,
                          None, {'name': sys_name, 'owner': hw_admin})

            # update ip assign system, user has no permission to ip nor
            # system
            msg = 'User has no UPDATE permission for the specified system'
            assert_update(msg, login, hw_admin,
                          None, {'name': sys_name, 'owner': hw_admin})

            # update ip withdraw system, user has permission to ip but
            # not to assigned system
            msg = ('User has no UPDATE permission for the system currently '
                   'holding the IP address')
            assert_update(msg, login, login,
                          {'name': sys_name, 'owner': hw_admin}, None)

            # update ip withdraw system, user has no permission to ip nor
            # system
            msg = ('User has no UPDATE permission for the system currently '
                   'holding the IP address')
            assert_update(msg, login, hw_admin,
                          {'name': sys_name, 'owner': hw_admin}, None)

        # clean up
        self.db.session.delete(sys_obj)
        self.db.session.delete(sys_obj_2)
        self.db.session.commit()
    # test_update_no_role()

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
        # fields 'project' and 'system' are tested separately due to special
        # permission handling
        update_fields = {
            'address': next(self._get_next_entry)['address'],
            'owner': 'user_user@domain.com',
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

    def test_update_subnet(self):
        """
        Try to update the subnet of an existing IP
        """
        data = next(self._get_next_entry)
        ip_id = self._request_and_assert('create', 'admin:a', data)
        data = {'id': ip_id, 'subnet': 'some subnet'}

        resp = self._do_request('update', 'user_hw_admin@domain.com:a', data)
        # validate the response received, should be 422 'unprocessable entity'
        error_msg = 'IP addresses cannot change their subnet'
        self._assert_failed_req(resp, 422, error_msg)
    # test_update_subnet()
# TestIpAddress
