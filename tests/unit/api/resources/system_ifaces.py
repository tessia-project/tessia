
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
Unit test for system_ifaces resource module
"""

#
# IMPORTS
#
from tessia.server.api.resources.system_ifaces import SystemIfaceResource
from tessia.server.db import models
from tests.unit.api.resources.secure_resource import TestSecureResource

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
                'ip_address': 'cpc0 shared/10.1.0.4',
                'mac_address': '00:11:22:33:44:55',
                'attributes': {'ccwgroup': '0.0.f101,0.0.f102,0.0.f103',
                               'layer2': True},
                'desc': 'Description iface {}'.format(index),
            }
            index += 1
            yield data
    # _entry_gen()

    @classmethod
    def setUpClass(cls):
        """
        Update systems to the same project of the test users.
        """
        super(TestSystemIface, cls).setUpClass()

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
    # setUpClass()

    def _validate_resp(self, resp, msg, status_code):
        """
        Helper validator
        """
        self.assertEqual(resp.status_code, status_code)
        body = json.loads(resp.get_data(as_text=True))
        self.assertEqual(msg, body['message'])
    # _validate_resp()

    def test_add_all_fields(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying all possible fields.
        """
        logins = [
            # TODO: fix user_user having access to system iface of other user
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com'
        ]

        self._test_add_all_fields_many_roles(logins)
    # test_add_all_fields_many_roles()

    def test_add_mandatory_fields(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying only the mandatory fields.
        """
        # the fields to be omitted and their expected values on response
        pop_fields = [('ip_address', None)]
        pop_fields = [('osname', None)]
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
            # try without subnet
            ('ip_address', '192.168.5.10'),
            ('type', 'wrong-type'),
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
            ('ip_address', 5),
            ('ip_address', False),
            ('osname', ''),
            ('osname', ' '),
            ('osname', 'name_with_*_symbol'),
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
            ('system', 5),
            ('system', None),
            ('system', True),
            ('attributes', 5),
            ('attributes', 'something'),
            ('attributes', True),
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

    def test_del_many_roles(self):
        """
        Exercise to remove entries with different roles
        """
        # keep in mind that ifaces use permissions from systems - which means
        # the first field (login add) refers to the profile creation but when
        # deleting it's the system's owner and project that count for
        # permission validation
        combos = [
            ('user_user@domain.com', 'user_user@domain.com'),
            ('user_user@domain.com', 'user_project_admin@domain.com'),
            ('user_user@domain.com', 'user_hw_admin@domain.com'),
            ('user_user@domain.com', 'user_admin@domain.com'),
            ('user_privileged@domain.com', 'user_project_admin@domain.com'),
            ('user_privileged@domain.com', 'user_admin@domain.com'),
            ('user_privileged@domain.com', 'user_hw_admin@domain.com'),
            ('user_privileged@domain.com', 'user_project_admin@domain.com'),
            ('user_privileged@domain.com', 'user_admin@domain.com'),
            ('user_privileged@domain.com', 'user_hw_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_project_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_hw_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_admin@domain.com'),
            ('user_hw_admin@domain.com', 'user_project_admin@domain.com'),
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
            # privileged can add and update but not delete
            ('user_user@domain.com', 'user_privileged@domain.com'),
            ('user_project_admin@domain.com', 'user_privileged@domain.com'),
            ('user_project_admin@domain.com', 'user_restricted@domain.com'),
            ('user_hw_admin@domain.com', 'user_privileged@domain.com'),
            ('user_hw_admin@domain.com', 'user_restricted@domain.com'),
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

        self._test_list_and_read('user_user@domain.com', logins)
    # test_list_and_read()

    def test_list_and_read_restricted_no_role(self):
        """
        List entries with a restricted user without role in any project
        """
        self._test_list_and_read_restricted_no_role(
            'user_user@domain.com', 'user_restricted@domain.com')
    # test_list_and_read_restricted_no_role()

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
        user_cred = '{}:a'.format('user_user@domain.com')

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

    def test_update_assoc_system(self):
        """
        Try to change the system associated to an iface.
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

        # clean up
        self.RESOURCE_MODEL.query.filter_by(id=created_id).delete()
        self.db.session.commit()
    # test_update_assoc_system()

    # TODO: test listing as restricted user with role
# TestSystemIface
