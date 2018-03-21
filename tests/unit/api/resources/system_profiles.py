# Copyright 2017 IBM Corp.
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
Unit test for system_profiles resource module
"""

#
# IMPORTS
#
from tessia.server.api.resources.system_profiles import SystemProfileResource
from tessia.server.db import models
from tests.unit.api.resources.secure_resource import TestSecureResource

import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestSystemProfile(TestSecureResource):
    """
    Validates the SystemProfile resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/system-profiles'
    # model associated with this resource
    RESOURCE_MODEL = models.SystemProfile
    # api object associated with the resource
    RESOURCE_API = SystemProfileResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'name': 'Profile name {}'.format(index),
                'system': "lpar0",
                'memory': 1024,
                'cpu': 2,
                'default': False,
                'parameters': {},
                'credentials': {},
                'operating_system': 'rhel7.2'
            }
            index += 1
            yield data
    # _entry_gen()

    def _validate_resp(self, resp, msg, status_code):
        """
        Helper validator
        """
        self.assertEqual(resp.status_code, status_code)
        body = json.loads(resp.get_data(as_text=True))
        self.assertEqual(msg, body['message'])
    # _validate_resp()

    @classmethod
    def setUpClass(cls):
        """
        Update systems to the same project of the test users.
        """
        super(TestSystemProfile, cls).setUpClass()

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

    def test_add_cpc_multiple_profiles(self):
        """
        Test creation of multiple profiles for a CPC system
        """
        # create a new CPC system
        system_obj = models.System(
            name="cpc_y",
            state="AVAILABLE",
            modifier="user_user@domain.com",
            type="cpc",
            hostname="hmc_y.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner="user_user@domain.com",
        )
        self.db.session.add(system_obj)
        self.db.session.commit()
        # attributes must be stored before the object expires
        system_id = system_obj.id
        system_name = system_obj.name

        # create profile
        data = next(self._get_next_entry)
        data['system'] = system_name
        user_login = '{}:a'.format('user_user@domain.com')
        resp = self._do_request('create', user_login, data)
        created_id = int(resp.get_data(as_text=True))

        # validate the created object
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()

        # try to add another
        data = next(self._get_next_entry)
        data['system'] = system_name
        resp = self._do_request('create', user_login, data)
        msg = 'A CPC system can only have one system profile'
        self._validate_resp(resp, msg, 422)

        # clean up
        self.db.session.delete(created_entry)
        models.System.query.filter_by(id=system_id).delete()
        self.db.session.commit()
    # test_add_cpc_multiple_profiles()

    def test_add_invalid_system_name(self):
        """
        Exercise creating a profile with an invalid system name
        """
        user_login = '{}:a'.format('user_user@domain.com')
        # create profile
        data = next(self._get_next_entry)
        data['system'] = 'do_not_exist'
        resp = self._do_request('create', user_login, data)
        msg = ("No associated item found with value '{}' for field 'System'"
               .format(data['system']))
        self._validate_resp(resp, msg, 422)
    # test_add_invalid_system_name()

    def test_add_mandatory_fields(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying only the mandatory fields.
        """
        # the fields to be omitted and their expected values on response
        pop_fields = [('parameters', None)]
        pop_fields = [('operating_system', None)]
        self._test_add_mandatory_fields('user_user@domain.com', pop_fields)
    # test_add_mandatory_fields()

    def test_add_missing_field(self):
        """
        Test if api correctly reports error when a mandatory field is missing
        during creation.
        """
        pop_fields = ['system', 'cpu', 'memory', 'default']
        self._test_add_missing_field('user_user@domain.com', pop_fields)
    # test_add_missing_field()

    def test_add_set_default(self):
        """
        Test the case where the first profile created is set automatically as
        default.
        """
        # create a new system
        system_obj = models.System(
            name="lpar_y",
            state="AVAILABLE",
            modifier="user_user@domain.com",
            type="lpar",
            hostname="lpar-y.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner="user_user@domain.com",
        )
        self.db.session.add(system_obj)
        self.db.session.commit()
        # id must be stored before the object expires
        system_id = system_obj.id

        # create profile
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        # explicitly set as False
        data['default'] = False
        user_login = '{}:a'.format('user_user@domain.com')
        resp = self._do_request('create', user_login, data)
        created_id = int(resp.get_data(as_text=True))

        # validate the created object
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()

        for key, value in data.items():
            if key == 'default':
                value = True
            self.assertEqual(
                getattr(created_entry, key), value,
                '{} is not {}'.format(key, value))

        # clean up
        self.db.session.delete(created_entry)
        models.System.query.filter_by(id=system_id).delete()
        self.db.session.commit()
    # test_add_set_default()

    def test_add_update_default(self):
        """
        Test add and update scenarios concerning the default flag:
        - new profile created as default unsets the existing default profile
        - existing profile cannot unset default flag
        - updating a profile as default unsets previous default one
        """
        user_login = '{}:a'.format('user_user@domain.com')
        # store reference to current default
        data = next(self._get_next_entry)
        sys_obj = models.System.query.filter_by(name=data['system']).one()
        orig_id = self.RESOURCE_MODEL.query.filter_by(
            system_id=sys_obj.id, default=True).one().id

        # create a new one as default
        data['default'] = True
        created_id = self._request_and_assert(
            'create', '{}:a'.format('user_user@domain.com'), data)

        # confirm existing is not default anymore
        orig_default = self.RESOURCE_MODEL.query.filter_by(id=orig_id).one()
        self.assertEqual(orig_default.default, False)

        # try to unset default flag
        update_data = {'id': created_id, 'default': False}
        resp = self._do_request('update', user_login, update_data)
        msg = ('A profile cannot unset its default flag, instead '
               'another must be set as default in its place')
        self._validate_resp(resp, msg, 422)

        # set original profile as default again and confirm new was unset
        update_data = {'id': orig_id, 'default': True}
        self._request_and_assert('update', user_login, update_data)
        new_profile = self.RESOURCE_MODEL.query.filter_by(id=created_id).one()
        self.assertEqual(new_profile.default, False)

        # clean up
        self.RESOURCE_MODEL.query.filter_by(id=created_id).delete()
        orig_default = self.RESOURCE_MODEL.query.filter_by(id=orig_id).one()
        orig_default.default = True
        self.db.session.add(orig_default)
        self.db.session.commit()
    # test_add_new_default()

    def test_add_update_assoc_error(self):
        """
        Try creation and edit while setting a FK field to a value that has no
        entry in the associated table.
        """
        wrong_fields = [
            ('gateway', 'some_gateway'),
            ('operating_system', 'wrong-os'),
        ]
        self._test_add_update_assoc_error(
            'user_user@domain.com', wrong_fields)
    # test_add_update_assoc_error()

    def test_add_update_conflict(self):
        """
        Test two scenarios:
        1- add a profile with a name that already exists
        2- update a profile to a name that already exists
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
            ('name', False),
            ('name', None),
            ('operating_system', 5),
            ('operating_system', True),
            ('system', 5),
            ('system', True),
            ('hypervisor_profile', 5),
            ('hypervisor_profile', True),
            ('parameters', 5),
            ('parameters', 'something'),
            ('parameters', True),
            ('credentials', 5),
            ('credentials', 'something_wrong'),
            ('credentials', True),
            ('gateway', 5),
            ('gateway', True),
            ('cpu', 'some_cpu'),
            ('cpu', True),
            ('memory', 'some_memory'),
            ('memory', True),
            # read-only fields
            ('storage_volumes', 'something'),
            ('system_ifaces', 'something'),
        ]
        self._test_add_update_wrong_field(
            'user_user@domain.com', wrong_data)

    def test_add_update_profile_without_hypervisor(self):
        """
        Test if api correctly reports error when a system without
        hypervisor exists and we attempt to create a profile for such system
        while specifying a hypervisor profile.
        """
        system_obj = models.System(
            name="lpar_no_hypervisor",
            state="AVAILABLE",
            modifier="user_user@domain.com",
            type="lpar",
            hostname="lpar_no_hyp.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner="user_user@domain.com",
        )

        self.db.session.add(system_obj)
        self.db.session.commit()

        # add profile while specifying a hypervisor profile
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        data['hypervisor_profile'] = 'default cpc0'
        resp = self._do_request(
            'create', 'user_user@domain.com:a', data)
        msg = "System has no hypervisor, you need to define one first"
        self._validate_resp(resp, msg, 400)

        # update profile while specifying a hypervisor profile
        data = next(self._get_next_entry)
        # set as True otherwise _request_and_assert will fail since this is the
        # first profile and will be automatically set to true
        data['default'] = True
        data['system'] = system_obj.name
        created_id = self._request_and_assert(
            'create', '{}:a'.format('user_user@domain.com:a'), data)
        data['id'] = created_id
        data['hypervisor_profile'] = 'default cpc0'
        resp = self._do_request(
            'update', 'user_user@domain.com:a', data)
        msg = "System has no hypervisor, you need to define one first"
        self._validate_resp(resp, msg, 400)

        # delete profile
        self._request_and_assert(
            'delete', 'user_user@domain.com:a', created_id)

        self.db.session.delete(system_obj)
        self.db.session.commit()
    # test_add_update_profile_without_hypervisor()

    def test_add_update_zvm(self):
        """
        Test creation and update of profiles for a zVM guest
        """
        # create a new zvm system
        system_obj = models.System(
            name="vmguest01",
            state="AVAILABLE",
            modifier="user_user@domain.com",
            type="zvm",
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

        # generate a new profile entry
        data = next(self._get_next_entry)
        data['system'] = system_name
        user_login = '{}:a'.format('user_user@domain.com')

        # try to create profile without zvm password, causes error
        resp = self._do_request('create', user_login, data)
        zvm_msg = 'For zVM guests the zVM password must be specified'
        self._validate_resp(resp, zvm_msg, 422)

        # add missing info and create profile correctly
        data['credentials']['user'] = 'username'
        data['credentials']['passwd'] = 'password'
        data['credentials']['host_zvm'] = {
            'passwd': 'vmpass',
            'byuser': 'vmadmin'
        }
        resp = self._do_request('create', user_login, data)
        created_id = int(resp.get_data(as_text=True))

        # try to remove zvm password from credentials, causes error
        data['id'] = created_id
        data['credentials'].pop('host_zvm')
        resp = self._do_request('update', user_login, data)
        self._validate_resp(resp, zvm_msg, 422)

        # clean up
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()
        self.db.session.delete(created_entry)
        models.System.query.filter_by(id=system_id).delete()
        self.db.session.commit()
    # test_add_update_zvm()

    def test_add_update_error_no_zvm(self):
        """
        Verify that the API blocks usage of zVM parameters for non zVM guest
        systems.
        """
        # generate a new profile entry
        data = next(self._get_next_entry)
        user_login = '{}:a'.format('user_user@domain.com')

        # try to create profile with zvm password, causes error
        data['credentials']['user'] = 'username'
        data['credentials']['passwd'] = 'password'
        data['credentials']['host_zvm'] = {
            'passwd': 'vmpass',
            'byuser': 'vmadmin'
        }
        resp = self._do_request('create', user_login, data)
        zvm_msg = 'zVM credentials should be provided for zVM guests only'
        self._validate_resp(resp, zvm_msg, 422)

        # remove zvm info and create profile correctly
        data['credentials'].pop('host_zvm')
        resp = self._do_request('create', user_login, data)
        created_id = int(resp.get_data(as_text=True))

        # try to add zvm password to existing profile, causes error
        data['id'] = created_id
        data['credentials']['host_zvm'] = {'passwd': 'vmpass'}
        resp = self._do_request('update', user_login, data)
        self._validate_resp(resp, zvm_msg, 422)

        # clean up
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()
        self.db.session.delete(created_entry)
        self.db.session.commit()
    # test_add_update_zvm()

    def test_del_default_profile_multi_profiles(self):
        """
        Try to delete a default profile while others exist
        """
        user_login = '{}:a'.format('user_user@domain.com')

        # retrieve the id of the pre-existing default profile
        data = next(self._get_next_entry)
        sys_obj = models.System.query.filter_by(name=data['system']).one()
        def_profile_id = self.RESOURCE_MODEL.query.filter_by(
            system_id=sys_obj.id, default=True).one().id

        # create another profile
        data['default'] = False
        created_id = self._request_and_assert('create', user_login, data)

        # try to delete the default profile
        resp = self._do_request('delete', user_login, def_profile_id)
        msg = ('A default profile cannot be removed while other '
               'profiles for the same system exist. Set another as '
               'the default first and then retry the operation.')
        # confirm it's not allowed
        self._validate_resp(resp, msg, 422)

        # remove the non default one, should work
        self._request_and_assert('delete', user_login, created_id)
    # test_del_default_profile_multi_profiles()

    def test_del_default_profile_single_profile(self):
        """
        Try to delete a default profile when it's the single one for
        the system
        """
        # create a new system
        system_obj = models.System(
            name="lpar_x",
            state="AVAILABLE",
            modifier="user_user@domain.com",
            type="lpar",
            hostname="lpar-x.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner="user_user@domain.com",
        )
        self.db.session.add(system_obj)
        self.db.session.commit()

        # create profile
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        data['default'] = True
        user_login = '{}:a'.format('user_user@domain.com')
        created_id = self._request_and_assert('create', user_login, data)

        # now delete and confirm it worked
        self._request_and_assert('delete', user_login, created_id)

        # clean up
        self.db.session.delete(system_obj)
        self.db.session.commit()
    # test_del_default_profile_single_profile()

    def test_del_many_roles(self):
        """
        Exercise to remove entries with different roles
        """
        # keep in mind that profiles use permissions from systems - which means
        # the first field (login add) refers to the profile creation but when
        # deleting it's the system's owner and project that count for
        # permission validation
        combos = [
            ('user_user@domain.com', 'user_user@domain.com'),
            ('user_user@domain.com', 'user_project_admin@domain.com'),
            ('user_user@domain.com', 'user_admin@domain.com'),
            ('user_user@domain.com', 'user_hw_admin@domain.com'),
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

    def test_update_assoc_system(self):
        """
        Try to change the system associated to a profile.
        """
        user_login = '{}:a'.format('user_user@domain.com')
        # create profile
        data = next(self._get_next_entry)
        created_id = self._request_and_assert('create', user_login, data)

        # try to change system
        update_data = {'id': created_id, 'system': 'cpc0'}
        resp = self._do_request('update', user_login, update_data)
        msg = 'Profiles cannot change their associated system'
        self._validate_resp(resp, msg, 422)

        # clean up
        self.RESOURCE_MODEL.query.filter_by(id=created_id).delete()
        self.db.session.commit()
    # test_update_assoc_system()

    # TODO: add tests with gateway parameter (cannot be tested for creation as
    # a netiface must be attached first)
    # TODO: add tests with hypervisor_profile (need to improve handling of
    # indirect value hyp_name/hyp_profile_name first)
    # TODO: add tests for attach/detach of volumes/network interfaces
    # (including negative test of multiple disks to a cpc)
    # TODO: add tests with same hyp_profile name
# TestSystemProfile
