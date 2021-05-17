# Copyright 2018, 2019 IBM Corp.
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
Unit test for system_ifaces resource module
"""

#
# IMPORTS
#
from flask import g as flask_global
from tessia.server.api.resources.system_ifaces import SystemIfaceResource
from tessia.server.db import models
from tests.unit.api.resources.secure_resource import TestSecureResource

import ipaddress
import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestSystemIface(TestSecureResource):
    """
    Validates the SystemIface resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/system-ifaces'
    # model associated with this resource
    RESOURCE_MODEL = models.SystemIface
    # api object associated with the resource
    RESOURCE_API = SystemIfaceResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'name': 'Interface name {}'.format(index),
                'osname': 'eth0',
                'system': 'lpar0',
                'type': 'OSA',
                'mac_address': '00:11:22:33:44:55',
                'attributes': {'ccwgroup': '0.0.f101,0.0.f102,0.0.f103',
                               'layer2': True},
                'desc': 'Description iface {}'.format(index),
            }
            index += 1
            yield data
    # _entry_gen()

    @classmethod
    def _ip_gen(cls):
        network_obj = ipaddress.ip_network('10.1.0.0/16')
        index = 5
        while True:
            yield network_obj[index]
            index += 1
    # _ip_gen()

    @classmethod
    def setUpClass(cls):
        """
        Update systems to the same project of the test users.
        """
        super(TestSystemIface, cls).setUpClass()

        # set requester for next queries
        # pylint: disable=assigning-non-slot
        flask_global.auth_user = models.User.query.filter(
            models.User.login == 'user_hw_admin@domain.com'
        ).one()

        # fetch which project to use from the test user and store this info for
        # use also by the testcases
        cls._project_name = models.UserRole.query.join(
            'project_rel'
        ).join(
            'user_rel'
        ).filter(
            models.UserRole.user == 'user_user@domain.com'
        ).one().project

        for system_obj in models.System.query.all():
            system_obj.project = cls._project_name
            system_obj.owner = 'user_user@domain.com'
            cls.db.session.add(system_obj)
        cls.db.session.commit()

        # define the generator for new ips
        cls._get_next_ip = cls._ip_gen()
        cls._subnet_name = 'cpc0 shared'
    # setUpClass()

    def _validate_resp(self, resp, msg, status_code):
        """
        Helper validator
        """
        self.assertEqual(resp.status_code, status_code)
        body = json.loads(resp.get_data(as_text=True))
        self.assertEqual(msg, body['message'])
    # _validate_resp()

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

        # create iface without ip, user has permission to system
        self._test_add_all_fields_many_roles(logins)

        ip_addr = str(next(self._get_next_ip))
        ip_obj = models.IpAddress(
            address=ip_addr,
            subnet=self._subnet_name,
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(ip_obj)
        self.db.session.commit()
        def cleanup_helper():
            """Helper to remove IP on test end/failure"""
            self.db.session.delete(ip_obj)
            self.db.session.commit()
        self.addCleanup(cleanup_helper)

        for login in logins:
            # logins with update-ip permission
            if login in ('user_hw_admin@domain.com', 'user_admin@domain.com'):
                ip_owner = 'admin'
            # logins without permission, must be owner of the ip
            else:
                ip_owner = login
            # create iface with ip, user has permission to both
            ip_obj.owner = ip_owner
            self.db.session.add(ip_obj)
            self.db.session.commit()
            iface_new = next(self._get_next_entry)
            iface_new['ip_address'] = '{}/{}'.format(
                self._subnet_name, ip_addr)
            created_id = self._request_and_assert(
                'create', '{}:a'.format(login), iface_new)

            # clean up
            ip_obj.owner = 'admin'
            self.db.session.add(ip_obj)
            self.db.session.commit()
            self.db.session.query(self.RESOURCE_MODEL).filter_by(
                id=created_id).delete()
    # test_add_all_fields_many_roles()

    def test_add_all_fields_no_role(self):
        """
        Exercise the scenario where a normal user without permissions tries to
        create an item and fails.
        """
        # create iface without ip, user has no permission to system
        self._test_add_all_fields_no_role(['user_restricted@domain.com'],
                                          http_code=422)

        # set requester for next queries
        self._do_request('list', '{}:a'.format('user_hw_admin@domain.com'))

        ip_addr = str(next(self._get_next_ip))
        ip_obj = models.IpAddress(
            address=ip_addr,
            subnet=self._subnet_name,
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(ip_obj)
        self.db.session.commit()
        def cleanup_helper():
            """Helper to remove IP on test end/failure"""
            self.db.session.delete(ip_obj)
            self.db.session.commit()
        self.addCleanup(cleanup_helper)

        sys_name = next(self._get_next_entry)['system']
        sys_obj = models.System.query.filter_by(name=sys_name).one()
        orig_sys_owner = sys_obj.owner
        def restore_owner():
            """Helper to restore system owner on test end/failure"""
            # set requester for next query
            self._do_request('list', '{}:a'.format('user_hw_admin@domain.com'))
            sys_obj = models.System.query.filter_by(name=sys_name).one()
            sys_obj.owner = orig_sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()
        # restore_owner()
        self.addCleanup(restore_owner)

        def assert_fail(error_msg, login, sys_owner, ip_owner, http_code=403):
            """Helper to prepare and validate action"""
            data = next(self._get_next_entry)
            sys_name = data['system']

            # prepare ip ownership
            ip_obj = models.IpAddress.query.filter_by(
                address=ip_addr, subnet=self._subnet_name).one()
            ip_obj.owner = ip_owner
            self.db.session.add(ip_obj)
            # set system owner which gets used by iface for permission
            # verification
            self._do_request('list', '{}:a'.format('user_hw_admin@domain.com'))
            sys_obj = models.System.query.filter_by(name=sys_name).one()
            orig_sys_owner = sys_obj.owner
            sys_obj.owner = sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()

            data['ip_address'] = '{}/{}'.format(self._subnet_name, ip_addr)
            resp = self._do_request('create', '{}:a'.format(login), data)
            # validate the response received, should be forbidden
            self._validate_resp(resp, error_msg, http_code)

            # cleanup
            # set requester for following queries
            self._do_request('list', '{}:a'.format('user_hw_admin@domain.com'))
            ip_obj.owner = 'admin'
            self.db.session.add(ip_obj)
            # restore system owner
            sys_obj = models.System.query.filter_by(name=sys_name).one()
            sys_obj.owner = orig_sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()
        # assert_fail()

        def assert_assigned(login, sys_owner, ip_owner):
            """
            Helper to validate the case when ip is assigned to another system
            """
            another_system = 'cpc0'
            ip_obj = models.IpAddress.query.filter_by(
                address=ip_addr, subnet=self._subnet_name).one()
            ip_obj.system = another_system
            self.db.session.add(ip_obj)
            self.db.session.commit()
            msg = ('The IP address is already assigned to system <{}>, remove '
                   'the association first'.format(another_system))
            assert_fail(msg, login, sys_owner, ip_owner, http_code=409)

            # cleanup
            ip_obj = models.IpAddress.query.filter_by(
                address=ip_addr, subnet=self._subnet_name).one()
            ip_obj.system = None
            self.db.session.add(ip_obj)
            self.db.session.commit()
        # assert_assigned()

        # logins without update-system and update-ip permission
        logins = [
            ('user_restricted@domain.com', 422),
            ('user_user@domain.com', 403)
        ]
        for login, http_code in logins:
            # create iface with ip, user has permission to ip but not to system
            if http_code == 422:
                msg = ("No associated item found with value "
                       "'lpar0' for field 'System'")
            else:
                msg = 'User has no UPDATE permission for the specified system'
            assert_fail(msg, login, 'admin', login, http_code=http_code)

            # create iface with ip, user has no permission to system nor ip
            assert_fail(msg, login, 'admin', 'admin', http_code=http_code)

            # create iface with ip, user has permission to system but not ip
            if http_code == 422:
                msg = ("No associated item found with value "
                       "'cpc0 shared/10.1.0.6' for field 'IP address'")
            else:
                msg = ("User has no UPDATE permission for "
                       "the specified IP address")
            assert_fail(msg, login, login, 'admin', http_code=http_code)

            # create iface with ip, user has permission to system but ip is
            # already assigned to another system
            assert_assigned(login, login, login)

        # logins without update-ip permission
        logins = [
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
        ]
        for login in logins:
            # create iface with ip, user has permission to system but not ip
            msg = 'User has no UPDATE permission for the specified IP address'
            assert_fail(msg, login, 'admin', 'admin')

            # create iface with ip, user has permission to system but ip is
            # already assigned to another system
            assert_assigned(login, 'admin', login)

        # logins with all permissions
        logins = [
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]
        for login in logins:
            # create iface with ip, user has permission to system but ip is
            # already assigned to another system
            assert_assigned(login, 'admin', 'admin')
    # test_add_all_fields_no_role()

    def test_add_mandatory_fields(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying only the mandatory fields.
        """
        # the fields to be omitted and their expected values on response
        pop_fields = [('desc', None)]
        self._test_add_mandatory_fields(
            'user_privileged@domain.com', pop_fields)
    # test_add_mandatory_fields()

    def test_add_missing_field(self):
        """
        Test if api correctly reports error when a mandatory field is missing
        during creation.
        """
        pop_fields = ['name', 'system', 'attributes', 'type']
        self._test_add_missing_field('user_privileged@domain.com', pop_fields)
    # test_add_missing_field()

    def test_add_update_assoc_error(self):
        """
        Try creation and edit while setting a FK field to a value that has no
        entry in the associated table.
        """
        # system is test separately because error message is different
        wrong_fields = [
            ('ip_address', 'wrong-subnet/192.168.5.10'),
        ]
        self._test_add_update_assoc_error(
            'user_privileged@domain.com', wrong_fields)
    # test_add_update_assoc_error()

    def test_add_update_conflict(self):
        """
        Add an iface with a name that already exists.
        """
        self._test_add_update_conflict('user_privileged@domain.com', 'name')
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
            ('name', 5),
            ('name', False),
            ('name', None),
            ('ip_address', 'wrong-subnet/wrong-ip'),
            # try without subnet
            ('ip_address', '192.168.5.10'),
            ('ip_address', 5),
            ('ip_address', False),
            ('osname', ''),
            ('osname', ' '),
            ('osname', 'name_with_*_symbol'),
            ('osname', 'name_with_more_than_15_chars'),
            ('osname', 5),
            ('osname', False),
            ('osname', None),
            ('mac_address', 'wrong'),
            ('mac_address', ''),
            ('mac_address', False),
            ('mac_address', 'xx:xx:xx:xx:xx:xx'),
            ('mac_address', 5),
            ('type', False),
            ('type', 5),
            # type as string is tested separately
            ('system', 5),
            ('system', None),
            ('system', True),
            ('attributes', 5),
            ('attributes', 'something'),
            ('attributes', True),
            # set macvtap attributes which don't match the interface type osa
            ('attributes', {'libvirt': 'xxxx'},
             'Field "attributes" is not valid under any JSON schema'),
            # read-only fields
            ('profiles', 'something'),
        ]
        self._test_add_update_wrong_field(
            'user_privileged@domain.com', wrong_data)

    def test_add_wrong_system(self):
        """
        Try to add an iface to a system that does not exist.
        """
        user_login = '{}:a'.format('user_privileged@domain.com')
        # create iface
        data = next(self._get_next_entry)
        data['system'] = 'does-not-exist'
        resp = self._do_request('create', user_login, data)
        msg = ("No associated item found with value '{}' for field "
               "'System'".format(data['system']))
        self._validate_resp(resp, msg, 422)
    # test_add_wrong_system()

    def test_add_wrong_type(self):
        """
        Try to add an iface to a system that does not exist.
        """
        user_login = '{}:a'.format('user_privileged@domain.com')
        # create iface
        data = next(self._get_next_entry)
        data['type'] = 'wrong-type'
        resp = self._do_request('create', user_login, data)
        msg = "Invalid interface type {}".format(data['type'])
        self._validate_resp(resp, msg, 400)
    # test_add_wrong_type()

    def test_del_many_roles(self):
        """
        Exercise to remove entries with different roles
        """
        # keep in mind that ifaces check for UPDATE permission to system
        combos = [
            ('user_user@domain.com', 'user_user@domain.com'),
            ('user_user@domain.com', 'user_privileged@domain.com'),
            ('user_user@domain.com', 'user_project_admin@domain.com'),
            ('user_user@domain.com', 'user_hw_admin@domain.com'),
            ('user_user@domain.com', 'user_admin@domain.com'),
            ('user_privileged@domain.com', 'user_project_admin@domain.com'),
            ('user_privileged@domain.com', 'user_admin@domain.com'),
            ('user_privileged@domain.com', 'user_hw_admin@domain.com'),
            ('user_privileged@domain.com', 'user_project_admin@domain.com'),
            ('user_privileged@domain.com', 'user_admin@domain.com'),
            ('user_privileged@domain.com', 'user_hw_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_privileged@domain.com'),
            ('user_project_admin@domain.com', 'user_project_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_hw_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_admin@domain.com'),
            ('user_hw_admin@domain.com', 'user_privileged@domain.com'),
            ('user_hw_admin@domain.com', 'user_project_admin@domain.com'),
            ('user_hw_admin@domain.com', 'user_hw_admin@domain.com'),
            ('user_hw_admin@domain.com', 'user_admin@domain.com'),
            ('user_admin@domain.com', 'user_privileged@domain.com'),
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
            # privileged can add and update but not delete
            ('user_project_admin@domain.com', 'user_restricted@domain.com'),
            ('user_hw_admin@domain.com', 'user_restricted@domain.com'),
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

        self._test_list_and_read('user_user@domain.com', logins)
    # test_list_and_read()

    def test_list_and_read_restricted_no_role(self):
        """
        List entries with a restricted user without role in any project
        """
        self._test_list_and_read_restricted_no_role(
            'user_user@domain.com', 'user_restricted@domain.com',
            allowed=False, http_code=404)
    # test_list_and_read_restricted_no_role()

    def test_list_and_read_restricted_with_role(self):
        """
        List entries with a restricted user who has a role in a project.
        """
        user_rest = 'user_restricted@domain.com'
        # collect the existing entries and add them to the new ones for
        # later validation
        entries = []

        # reset flask user to admin
        self._do_request('list', 'admin:a')
        systems = models.System.query.join(
            'project_rel'
        ).filter(
            models.System.project == self._db_entries['Project'][0]['name']
        ).all()
        for sys_name in [system.name for system in systems]:
            resp = self._do_request(
                'list', 'admin:a',
                'where={}'.format(json.dumps({'system': sys_name}))
            )
            entries.extend(json.loads(resp.get_data(as_text=True)))
        # adjust id field to make the http response look like the same as the
        # dict from the _create_many_entries return
        for entry in entries:
            entry['id'] = entry.pop('$uri').split('/')[-1]

        # create new entries to work with and merge all of them
        entries.extend(self._create_many_entries('admin', 5)[0])

        # add the role for the restricted user
        role = models.UserRole(
            project=self._db_entries['Project'][0]['name'],
            user=user_rest,
            role="USER_RESTRICTED"
        )
        self.db.session.add(role)
        self.db.session.commit()
        def cleanup_helper():
            """Helper to remove role on test end/failure"""
            self.db.session.delete(role)
            self.db.session.commit()
        self.addCleanup(cleanup_helper)

        # retrieve list
        resp = self._do_request('list', '{}:a'.format(user_rest))
        self._assert_listed_or_read(resp, entries, 0)

        # perform a read
        resp = self._do_request(
            'get', '{}:a'.format(user_rest), entries[0]['id'])
        self._assert_listed_or_read(
            resp, [entries[0]], 0, read=True)
    # test_list_and_read_restricted_with_role()

    def test_hsi_zvm(self):
        """
        Test creation/update of Hipersockets on zVM guests
        """
        user_login = 'user_user@domain.com'
        # create a new zvm system
        system_obj = models.System(
            name="vmguest01",
            state="AVAILABLE",
            modifier=user_login,
            type="zvm",
            hostname="vmguest01.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner=user_login
        )
        self.db.session.add(system_obj)
        self.db.session.commit()
        # attributes must be stored before the object expires
        system_id = system_obj.id
        system_name = system_obj.name

        # generate a new iface entry
        data = next(self._get_next_entry)
        data['system'] = system_name
        data['type'] = 'HSI'

        # layer2 on, mac defined - allowed
        user_cred = '{}:a'.format('user_user@domain.com')
        created_id = self._request_and_assert('create', user_cred, data)

        # update layer2 to off, mac gets removed
        new_attr = data['attributes'].copy()
        new_attr['layer2'] = False
        update_data = {'id': created_id, 'attributes': new_attr}
        resp = self._do_request('update', user_cred, update_data)
        # include mac in verification
        update_data['mac_address'] = None
        self._assert_updated(resp, update_data)

        # try to define mac when layer2 is off - causes error
        update_data = {'id': created_id, 'mac_address': '00:11:22:33:44:55'}
        error_msg = 'When layer2 is off no MAC address should be defined'
        resp = self._do_request('update', user_cred, update_data)
        self._validate_resp(resp, error_msg, 422)

        # clean up
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()
        self.db.session.delete(created_entry)

        # layer2 off, mac specified - not allowed
        data = next(self._get_next_entry)
        data['system'] = system_name
        data['type'] = 'HSI'
        data['attributes']['layer2'] = False
        error_msg = 'When layer2 is off no MAC address should be defined'
        resp = self._do_request('create', user_cred, data)
        self._validate_resp(resp, error_msg, 422)

        # layer2 off, no mac - success
        data['mac_address'] = None
        created_id = self._request_and_assert('create', user_cred, data)

        # clean up
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()
        self.db.session.delete(created_entry)
        models.System.query.filter_by(id=system_id).delete()
        self.db.session.commit()
    # test_hsi_zvm()

    def test_mac_non_osa(self):
        """
        Test creation/update of non OSA cards - mac is always required
        """
        system_obj = models.System(
            name="kvmguest01",
            state="AVAILABLE",
            modifier="user_user@domain.com",
            type="kvm",
            hostname="vmguest01.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner="user_user@domain.com",
        )
        self.db.session.add(system_obj)
        self.db.session.commit()
        # attributes must be stored before the object expires
        system_id = system_obj.id
        system_name = system_obj.name

        data = {
            'name': 'A non OSA card',
            'osname': 'en0',
            'system': system_name,
            'type': 'MACVTAP',
            'mac_address': None,
            'attributes': {'hostiface': 'enccwf500'},
            'desc': 'Description',
        }
        user_cred = '{}:a'.format('user_user@domain.com')
        # try to create iface without mac, causes error
        error_msg = 'A MAC address must be defined'
        resp = self._do_request('create', user_cred, data)
        self._validate_resp(resp, error_msg, 422)

        # add mac, success
        data['mac_address'] = '00:11:22:33:44:55'
        created_id = self._request_and_assert('create', user_cred, data)

         # try to remove mac - causes error
        update_data = {'id': created_id, 'mac_address': None}
        resp = self._do_request('update', user_cred, update_data)
        self._validate_resp(resp, error_msg, 422)

        # clean up
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()
        self.db.session.delete(created_entry)
        models.System.query.filter_by(id=system_id).delete()
        self.db.session.commit()
    # test_mac_non_osa()

    def test_mac_osa_lpar(self):
        """
        Test creation/update of OSA cards on LPARs
        """
        # layer2 on, mac defined - allowed
        user_cred = '{}:a'.format('user_user@domain.com')
        data = next(self._get_next_entry)
        created_id = self._request_and_assert('create', user_cred, data)

        # update layer2 to off, mac gets removed
        new_attr = data['attributes'].copy()
        new_attr['layer2'] = False
        update_data = {'id': created_id, 'attributes': new_attr}
        resp = self._do_request('update', user_cred, update_data)
        # include mac in verification
        update_data['mac_address'] = None
        self._assert_updated(resp, update_data)

        # try to define mac when layer2 is off - causes error
        update_data = {'id': created_id, 'mac_address': '00:11:22:33:44:55'}
        error_msg = 'When layer2 is off no MAC address should be defined'
        resp = self._do_request('update', user_cred, update_data)
        self._validate_resp(resp, error_msg, 422)

        # layer2 off, mac specified - not allowed
        data = next(self._get_next_entry)
        data['attributes']['layer2'] = False
        error_msg = 'When layer2 is off no MAC address should be defined'
        resp = self._do_request('create', user_cred, data)
        self._validate_resp(resp, error_msg, 422)

        # layer2 off, no mac - success
        data['mac_address'] = None
        created_id = self._request_and_assert('create', user_cred, data)

    # test_mac_osa_lpar()

    def test_mac_osa_zvm(self):
        """
        Test creation/update of OSA cards on zVM guests
        """
        user_login = 'user_user@domain.com'
        # create a new zvm system
        system_obj = models.System(
            name="vmguest01",
            state="AVAILABLE",
            modifier=user_login,
            type="zvm",
            hostname="vmguest01.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner=user_login
        )
        self.db.session.add(system_obj)
        self.db.session.commit()
        # attributes must be stored before the object expires
        system_id = system_obj.id
        system_name = system_obj.name

        # generate a new iface entry
        data = next(self._get_next_entry)
        data['system'] = system_name

        # layer2 on, mac defined - allowed
        user_cred = '{}:a'.format('user_user@domain.com')
        created_id = self._request_and_assert('create', user_cred, data)

        # update layer2 to off, mac gets removed
        new_attr = data['attributes'].copy()
        new_attr['layer2'] = False
        update_data = {'id': created_id, 'attributes': new_attr}
        resp = self._do_request('update', user_cred, update_data)
        # include mac in verification
        update_data['mac_address'] = None
        self._assert_updated(resp, update_data)

        # try to define mac when layer2 is off - causes error
        update_data = {'id': created_id, 'mac_address': '00:11:22:33:44:55'}
        error_msg = 'When layer2 is off no MAC address should be defined'
        resp = self._do_request('update', user_cred, update_data)
        self._validate_resp(resp, error_msg, 422)

        # clean up
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()
        self.db.session.delete(created_entry)
        models.System.query.filter_by(id=system_id).delete()
        self.db.session.commit()

        # layer2 off, mac specified - not allowed
        data = next(self._get_next_entry)
        data['attributes']['layer2'] = False
        error_msg = 'When layer2 is off no MAC address should be defined'
        resp = self._do_request('create', user_cred, data)
        self._validate_resp(resp, error_msg, 422)

        # layer2 off, no mac - success
        data['mac_address'] = None
        created_id = self._request_and_assert('create', user_cred, data)

        # clean up
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()
        self.db.session.delete(created_entry)
        models.System.query.filter_by(id=system_id).delete()
        self.db.session.commit()
    # test_mac_osa_zvm()

    def test_update_has_role(self):
        """
        Exercise update scenarios involving different permission combinations
        """
        ip_addr = str(next(self._get_next_ip))
        ip_obj = models.IpAddress(
            address=ip_addr,
            subnet=self._subnet_name,
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(ip_obj)
        ip_addr_2 = str(next(self._get_next_ip))
        ip_obj_2 = models.IpAddress(
            address=ip_addr_2,
            subnet=self._subnet_name,
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(ip_obj_2)
        self.db.session.commit()

        # restore original system owner on test end/failure to avoid causing
        # problems with other tests
        data = next(self._get_next_entry)
        sys_obj = models.System.query.filter_by(name=data['system']).one()
        orig_sys_owner = sys_obj.owner
        def restore_owner():
            """Helper cleanup"""
            sys_obj = models.System.query.filter_by(name=data['system']).one()
            sys_obj.owner = orig_sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()
        self.addCleanup(restore_owner)

        def assert_update(update_user, sys_owner, ip_cur, ip_target):
            """
            Helper function to validate update action

            Args:
                update_user (str): login performing the update action
                sys_owner (str): set this login as owner of the system
                ip_cur (str): name and owner of the current ip address
                ip_target (str): name and owner of target ip address
            """
            data = next(self._get_next_entry)
            # set system owner which gets used by iface for permission
            # verification
            sys_obj = models.System.query.filter_by(name=data['system']).one()
            sys_obj.owner = sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()

            # reset flask user to admin
            self._do_request('list', 'admin:a')

            if ip_cur:
                data['ip_address'] = '{}/{}'.format(
                    self._subnet_name, ip_cur['address'])
                ip_obj = models.IpAddress.query.filter_by(
                    address=ip_cur['address'], subnet=self._subnet_name).one()
                ip_obj.owner = ip_cur['owner']
                # assign ip to a system
                if ip_cur['assign']:
                    ip_obj.system = data['system']
                else:
                    ip_obj.system = None
                self.db.session.add(ip_obj)
                self.db.session.commit()
            iface_id = self._request_and_assert('create', 'admin:a', data)

            if ip_target:
                ip_obj = models.IpAddress.query.filter_by(
                    address=ip_target['address'], subnet=self._subnet_name
                ).one()
                ip_obj.owner = ip_target['owner']
                # assign ip to a system
                if ip_target['assign']:
                    ip_obj.system = data['system']
                else:
                    ip_obj.system = None
                self.db.session.add(ip_obj)
                self.db.session.commit()
                ip_tgt_name = '{}/{}'.format(
                    self._subnet_name, ip_target['address'])
            else:
                ip_tgt_name = None

            # perform request and validate
            data = {'id': iface_id, 'ip_address': ip_tgt_name}
            self._request_and_assert(
                'update', '{}:a'.format(update_user), data)
            self.assertEqual(
                self.RESOURCE_MODEL.query.filter_by(
                    id=iface_id).one().ip_address,
                data['ip_address'], 'IP address field update failed')

            # clean up
            self.db.session.query(self.RESOURCE_MODEL).filter_by(
                id=iface_id).delete()
            if ip_cur:
                ip_obj = models.IpAddress.query.filter_by(
                    address=ip_cur['address'], subnet=self._subnet_name).one()
                ip_obj.system_id = None
                self.db.session.add(ip_obj)
            if ip_target:
                ip_obj = models.IpAddress.query.filter_by(
                    address=ip_target['address'], subnet=self._subnet_name
                ).one()
                ip_obj.system_id = None
                self.db.session.add(ip_obj)
            self.db.session.commit()
        # assert_update()

        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]
        for login in logins:
            # update iface set ip, user has permission to both system and ip
            # exercise case where user is owner of system
            if login in ('user_restricted@domain.com', 'user_user@domain.com'):
                sys_owner = login
            # exercise case where user has permission via a role
            else:
                sys_owner = 'admin'
            # exercise case where user is owner of ip
            if login not in ('user_hw_admin@domain.com',
                             'user_admin@domain.com'):
                ip_owner = login
            # exercise case where user has permission via a role
            else:
                ip_owner = 'admin'
            assert_update(
                login, sys_owner,
                None,
                {'address': ip_addr, 'owner': ip_owner, 'assign': False},
            )

            # update iface set ip assigned to system, user has permission to
            # system but not to ip
            assert_update(
                login, sys_owner,
                None,
                {'address': ip_addr, 'owner': 'admin', 'assign': True},
            )

            # update iface withdraw ip, user has permission to system and ip
            assert_update(
                login, sys_owner,
                {'address': ip_addr, 'owner': ip_owner, 'assign': False},
                None,
            )

            # update iface withdraw ip assigned to system, user has
            # permission to system but not to ip
            assert_update(
                login, sys_owner,
                {'address': ip_addr, 'owner': 'admin', 'assign': True},
                None,
            )

            # update iface change ip, user has permission to both
            # exercise case where user is owner
            if login not in ('user_hw_admin@domain.com',
                             'user_admin@domain.com'):
                ip_owner_2 = login
            # exercise case where user has permission via a role
            else:
                ip_owner_2 = 'admin'
            assert_update(
                login, sys_owner,
                {'address': ip_addr, 'owner': ip_owner, 'assign': False},
                {'address': ip_addr_2, 'owner': ip_owner_2, 'assign': False},
            )

            # update iface change ip assigned to system, user has permission
            # to system but not to ip
            assert_update(
                login, sys_owner,
                {'address': ip_addr, 'owner': ip_owner, 'assign': False},
                {'address': ip_addr_2, 'owner': ip_owner_2, 'assign': True},
            )

        # clean up
        self.db.session.delete(ip_obj)
        self.db.session.delete(ip_obj_2)
        self.db.session.commit()
    # test_update_has_role()

    def test_update_no_role(self):
        """
        Try to update an iface without an appropriate role to do so.
        """
        hw_admin = 'user_hw_admin@domain.com'
        # restore original system owner on test end/failure to avoid causing
        # problems with other tests
        data = next(self._get_next_entry)
        sys_name = data['system']
        sys_obj = models.System.query.filter_by(name=sys_name).one()
        orig_sys_owner = sys_obj.owner
        def restore_owner():
            """Helper cleanup"""
            # reset flask user to admin
            self._do_request('list', 'admin:a')

            sys_obj = models.System.query.filter_by(name=sys_name).one()
            sys_obj.owner = orig_sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()
        self.addCleanup(restore_owner)
        sys_obj.owner = hw_admin
        self.db.session.add(sys_obj)
        self.db.session.commit()

        # update iface without ip, user has no permission to system
        update_fields = {
            'name': 'some_name',
            'osname': 'ethX',
            'desc': 'some_desc',
            'mac_address': '99:11:22:33:44:55',
            'attributes': {'ccwgroup': '0.0.e101,0.0.e102,0.0.e103',
                           'layer2': True},
        }
        self._test_update_no_role(hw_admin, ['user_restricted@domain.com'],
                                  update_fields, http_code=404)
        self._test_update_no_role(hw_admin, ['user_user@domain.com'],
                                  update_fields)

        ip_addr = str(next(self._get_next_ip))
        ip_obj = models.IpAddress(
            address=ip_addr,
            subnet=self._subnet_name,
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(ip_obj)
        ip_addr_2 = str(next(self._get_next_ip))
        ip_obj_2 = models.IpAddress(
            address=ip_addr_2,
            subnet=self._subnet_name,
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][1]['name'],
        )
        self.db.session.add(ip_obj_2)
        self.db.session.commit()
        # keep track of ids for cleaning up at the end
        ip_obj_id = ip_obj.id
        ip_obj_id_2 = ip_obj_2.id

        def assert_update(error_msg, update_user, sys_owner, ip_cur,
                          ip_target, http_code=403):
            """
            Helper function to validate update action is forbidden

            Args:
                update_user (str): login performing the update action
                sys_owner (str): set this login as owner of the system
                ip_cur (str): name and owner of the current ip address
                ip_target (str): name and owner of target ip address
                error_msg (str): expected error message
                http_code (int): expected http error code, defaults to
                                 403 forbidden
            """
            data = next(self._get_next_entry)
            sys_name = data['system']
            # set system owner which gets used by iface for permission
            # verification
            sys_obj = models.System.query.filter_by(name=sys_name).one()
            orig_sys_owner = sys_obj.owner
            sys_obj.owner = sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()
            if ip_cur:
                data['ip_address'] = '{}/{}'.format(
                    self._subnet_name, ip_cur['address'])
                ip_obj = models.IpAddress.query.filter_by(
                    address=ip_cur['address'], subnet=self._subnet_name).one()
                ip_obj.owner = ip_cur['owner']
                if ip_cur.get('assign'):
                    ip_obj.system = ip_cur['assign']
                else:
                    ip_obj.system = None
                self.db.session.add(ip_obj)
                self.db.session.commit()
            iface_id = self._request_and_assert('create', 'admin:a', data)

            if ip_target:
                ip_obj = models.IpAddress.query.filter_by(
                    address=ip_target['address'], subnet=self._subnet_name
                ).one()
                ip_obj.owner = ip_target['owner']
                # assign ip to a system
                if ip_target.get('assign'):
                    ip_obj.system = ip_target['assign']
                else:
                    ip_obj.system = None
                self.db.session.add(ip_obj)
                self.db.session.commit()
                ip_tgt_name = '{}/{}'.format(
                    self._subnet_name, ip_target['address'])
            else:
                ip_tgt_name = None

            data = {'id': iface_id, 'ip_address': ip_tgt_name}
            resp = self._do_request('update', '{}:a'.format(update_user), data)
            # validate the response received
            if ip_tgt_name:
                error_msg = error_msg.replace('#IP#', ip_tgt_name)
            self._validate_resp(resp, error_msg, http_code)
            # clean up
            # reset flask user to admin
            self._do_request('list', 'admin:a')
            self.db.session.query(self.RESOURCE_MODEL).filter_by(
                id=iface_id).delete()
            if ip_cur:
                ip_obj = models.IpAddress.query.filter_by(
                    address=ip_cur['address'], subnet=self._subnet_name).one()
                ip_obj.system_id = None
                self.db.session.add(ip_obj)
            if ip_target:
                ip_obj = models.IpAddress.query.filter_by(
                    address=ip_target['address'], subnet=self._subnet_name
                ).one()
                ip_obj.system_id = None
                self.db.session.add(ip_obj)
            # restore system owner
            sys_obj = models.System.query.filter_by(name=sys_name).one()
            sys_obj.owner = orig_sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()
        # assert_update()

        # logins with update-system permission but no update-ip
        logins_system = (
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
        )
        for login in logins_system:
            # update iface assign ip, user has permission to system but not
            # to ip
            msg = 'User has no UPDATE permission for the specified IP address'
            assert_update(msg, login, hw_admin,
                          None, {'address': ip_addr, 'owner': hw_admin})

            # update iface change ip, user has permission to system and
            # current ip but not to target ip
            msg = 'User has no UPDATE permission for the specified IP address'
            assert_update(msg, login, hw_admin,
                          {'address': ip_addr, 'owner': login},
                          {'address': ip_addr_2, 'owner': hw_admin})

        # logins without update-system permission
        logins_no_system = (
            'user_restricted@domain.com',
            'user_user@domain.com'
        )
        for login in logins_no_system:
            msg = 'User has no UPDATE permission for the specified system'
            http_code = 403

            if login == 'user_restricted@domain.com':
                http_code = 404
                msg = 'Not Found'

            # update iface assign ip, user has permission to ip but
            # not to system
            assert_update(msg, login, hw_admin,
                          None, {'address': ip_addr, 'owner': login},
                          http_code=http_code)

            # update iface assign ip, user has no permission to system nor ip
            assert_update(msg, login, hw_admin,
                          None, {'address': ip_addr, 'owner': hw_admin},
                          http_code=http_code)

            # note: no test for update iface withdraw ip as this is allowed

            # update iface withdraw ip, user has no permission to system nor ip
            assert_update(msg, login, hw_admin,
                          {'address': ip_addr, 'owner': hw_admin}, None,
                          http_code=http_code)

            # update iface withdraw ip, user has permission to ip but
            # not to system
            assert_update(msg, login, hw_admin,
                          {'address': ip_addr, 'owner': login}, None,
                          http_code=http_code)

            # update iface assign ip, user has permission to system but not
            # to ip
            if login == 'user_restricted@domain.com':
                http_code = 422
                msg = ("No associated item found with value "
                       "'#IP#' for field 'IP address'")
            else:
                msg = ("User has no UPDATE permission for "
                       "the specified IP address")
            assert_update(msg, login, login,
                          None, {'address': ip_addr, 'owner': hw_admin},
                          http_code=http_code)

            # update iface change ip, user has permission to system and
            # current ip but not to target ip
            assert_update(msg, login, login,
                          {'address': ip_addr, 'owner': login},
                          {'address': ip_addr_2, 'owner': hw_admin},
                          http_code=http_code)

        another_system = 'cpc0'
        for login in (('user_hw_admin@domain.com', 'user_admin@domain.com') +
                      logins_system + logins_no_system):
            # update iface assign ip, user has permission to system and
            # ip but ip is already assigned to another system
            msg = ('The IP address is already assigned to system <{}>, remove '
                   'the association first'.format(another_system))
            assert_update(
                msg, login, login,
                None,
                {'address': ip_addr, 'owner': login, 'assign': another_system},
                http_code=409)

            # update iface change ip, user has permission to system and ip but
            # ip is already assigned to another system
            assert_update(msg, login, login,
                          {'address': ip_addr, 'owner': login},
                          {'address': ip_addr_2, 'owner': login,
                           'assign': another_system}, http_code=409)

        # clean up
        models.IpAddress.query.filter_by(id=ip_obj_id).delete()
        models.IpAddress.query.filter_by(id=ip_obj_id_2).delete()
        self.db.session.commit()
    # test_update_no_role()

    def test_update_prohibited(self):
        """
        Try to update prohibited fields
        """
        user_login = '{}:a'.format('user_privileged@domain.com')
        # create iface
        data = next(self._get_next_entry)
        created_id = self._request_and_assert('create', user_login, data)

        # try to change system
        update_data = {'id': created_id, 'system': 'cpc0'}
        resp = self._do_request('update', user_login, update_data)
        msg = 'Interfaces cannot change their associated system'
        self._validate_resp(resp, msg, 422)

        # try to change type
        update_data = {'id': created_id, 'type': 'macvtap'}
        resp = self._do_request('update', user_login, update_data)
        msg = 'Interfaces cannot change their type'
        self._validate_resp(resp, msg, 422)

        # clean up
        self.RESOURCE_MODEL.query.filter_by(id=created_id).delete()
        self.db.session.commit()
    # test_update_assoc_system()
# TestSystemIface
