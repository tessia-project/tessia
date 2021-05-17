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
from base64 import b64encode
from flask import g as flask_global
from tessia.server.api.resources.system_profiles import CPU_MEM_ERROR_MSG
from tessia.server.api.resources.system_profiles import MARKER_STRIPPED_SECRET
from tessia.server.api.resources.system_profiles import SystemProfileResource
from tessia.server.db import models
from tests.unit.api.resources.secure_resource import TestSecureResource

import json
import time

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
    # target lpar for creating profiles
    _target_lpar = 'lpar0'

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'name': 'Profile name {}'.format(index),
                'system': cls._target_lpar,
                'memory': 1024,
                'cpu': 2,
                'default': False,
                'parameters': None,
                'credentials': {
                    'admin-user': 'root', 'admin-password': 'mypasswd'},
                'operating_system': 'rhel7.2'
            }
            index += 1
            yield data
    # _entry_gen()

    def _req_att(self, user_cred, url, data, exp_body=None):
        auth = 'basic {}'.format(
            b64encode(bytes(user_cred, 'ascii')).decode('ascii'))
        resp = self.app.post(
            url,
            headers={
                'Authorization': auth, 'Content-type': 'application/json'},
            data=json.dumps(data)
        )
        if exp_body:
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(exp_body, body)

        return resp
    # _req_att()

    def _req_att_disk(self, disk_id, prof_id, user_cred, validate=True):
        """
        Perform an attach volume request
        """
        # attach a disk
        url = '{}/{}/storage_volumes'.format(self.RESOURCE_URL, prof_id)
        disk_data = {'unique_id': disk_id}
        if validate:
            exp_body = {'profile_id': prof_id, 'volume_id': disk_id}
        else:
            exp_body = None
        return self._req_att(user_cred, url, disk_data, exp_body)
    # _req_att_disk()

    def _req_att_iface(self, iface_id, prof_id, user_cred, validate=True):
        """
        Perform an attach network interface request
        """
        url = '{}/{}/system_ifaces'.format(self.RESOURCE_URL, prof_id)
        iface_data = {'id': iface_id}
        if validate:
            exp_body = {'profile_id': prof_id, 'iface_id': iface_id}
        else:
            exp_body = None
        return self._req_att(user_cred, url, iface_data, exp_body)
    # _req_att_iface()

    def _req_det(self, user_cred, url, validate=True):
        """
        Perform a detach request
        """
        # detach a disk
        auth = 'basic {}'.format(
            b64encode(bytes(user_cred, 'ascii')).decode('ascii'))
        resp = self.app.delete(
            url,
            headers={
                'Authorization': auth, 'Content-type': 'application/json'},
        )
        if validate:
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(True, body)

        return resp
    # _req_det()

    def _req_det_disk(self, disk_id, prof_id, user_cred, validate=True):
        """
        Perform a detach volume request
        """
        url = '{}/{}/storage_volumes/{}'.format(
            self.RESOURCE_URL, prof_id, disk_id)
        return self._req_det(user_cred, url, validate)
    # _req_det_disk()

    def _req_det_iface(self, iface_id, prof_id, user_cred, validate=True):
        """
        Perform a detach network interface request
        """
        # detach a disk
        url = '{}/{}/system_ifaces/{}'.format(
            self.RESOURCE_URL, prof_id, iface_id)
        return self._req_det(user_cred, url, validate)
    # _req_det_iface()

    def _update_cred(self, target_id, req_cred, user_login):
        """
        Update credentials field and validate merged content
        """
        target_entry = self.RESOURCE_MODEL.query.filter_by(
            id=target_id).one()
        cur_cred = target_entry.credentials

        data = {'id': target_id, 'credentials': req_cred}
        resp = self._do_request('update', user_login, data)
        # validate the response code
        self.assertEqual(200, resp.status_code, resp.data)
        # validate that the merged credentials contains the new values
        merged_cred = {}
        merged_cred.update(cur_cred)
        for key, value in data['credentials'].items():
            # None means unset value so we skip this key
            if value is None:
                try:
                    merged_cred.pop(key)
                except KeyError:
                    pass
                continue
            merged_cred[key] = value
        updated_entry = self.RESOURCE_MODEL.query.filter_by(
            id=target_id).one()
        self.assertEqual(updated_entry.credentials, merged_cred)
    # _update_cred()

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

    def test_add_cpc_multiple_disks(self):
        """
        Test attachment of multiple disks to a CPC profile
        """
        user_login = 'user_user@domain.com'

        # create a new CPC system
        system_obj = models.System(
            name="cpc_y",
            state="AVAILABLE",
            modifier=user_login,
            type="cpc",
            hostname="hmc_y.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner=user_login,
        )
        self.db.session.add(system_obj)
        self.db.session.commit()
        # attributes must be stored before the object expires in the session
        system_id = system_obj.id
        system_name = system_obj.name

        # create disks to attach to profile
        st_server_obj = models.StorageServer(
            name='Storage server for CPC test',
            model='ds8k',
            type='DASD-FCP',
            owner=user_login,
            modifier=user_login,
            project=self._db_entries['Project'][0]['name'],
            desc='some description'
        )
        self.db.session.add(st_server_obj)
        self.db.session.commit()
        st_server_id = st_server_obj.id

        disk_ids = []
        for disk_id in ('1111', '2222', '3333'):
            disk_obj = models.StorageVolume(
                server_id=st_server_obj.id,
                volume_id=disk_id,
                type='DASD',
                size=10000,
                part_table={},
                system_attributes={},
                owner=user_login,
                modifier=user_login,
                project=self._db_entries['Project'][0]['name'],
                desc='some description'
            )
            self.db.session.add(disk_obj)
            self.db.session.commit()
            disk_ids.append(disk_obj.id)

        # create profile
        data = next(self._get_next_entry)
        data['system'] = system_name
        # first profile will be set as default
        data['default'] = True
        user_cred = '{}:a'.format(user_login)
        prof_id = self._request_and_assert('create', user_cred, data)

        # attach a disk
        self._req_att_disk(disk_ids[0], prof_id, user_cred)

        # try to attach a second disk - should fail
        resp = self._req_att_disk(
            disk_ids[1], prof_id, user_cred, validate=False)
        one_disk_msg = 'A CPC profile can have only one volume associated'
        self._validate_resp(resp, one_disk_msg, 422)

        # try to add another profile - should work
        data = next(self._get_next_entry)
        data['system'] = system_name
        prof_another_id = self._request_and_assert('create', user_cred, data)

        # attach a disk
        self._req_att_disk(disk_ids[1], prof_another_id, user_cred)

        # try to attach a second disk - should fail
        resp = self._req_att_disk(
            disk_ids[2], prof_another_id, user_cred, validate=False)
        self._validate_resp(resp, one_disk_msg, 422)

        # clean up (and also test detach)
        self._req_det_disk(disk_ids[0], prof_id, user_cred)
        self._req_det_disk(disk_ids[1], prof_another_id, user_cred)
        models.SystemProfile.query.filter_by(id=prof_id).delete()
        models.SystemProfile.query.filter_by(id=prof_another_id).delete()
        for disk_id in disk_ids:
            models.StorageVolume.query.filter_by(id=disk_id).delete()
        models.StorageServer.query.filter_by(id=st_server_id).delete()
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
        pop_fields = ['system', 'cpu', 'memory', 'default', 'credentials']
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

    def test_add_update_credentials(self):
        """
        Test scenarios concerning add/update of admin credentials
        """
        user_login = '{}:a'.format('user_user@domain.com')

        # try to create profile without admin credentials
        data = next(self._get_next_entry)
        data['default'] = True
        data['credentials'] = {}
        resp = self._do_request('create', user_login, data)
        no_user_msg = 'Credentials must contain OS admin username'
        self._validate_resp(resp, no_user_msg, 422)
        data['credentials'] = {'admin-user': 'username'}
        resp = self._do_request('create', user_login, data)
        no_passwd_msg = 'Credentials must contain OS admin password'
        self._validate_resp(resp, no_passwd_msg, 422)

        # now create successfully
        data['credentials']['admin-password'] = 'password'
        prof_id = self._request_and_assert('create', user_login, data)

        # update only user
        self._update_cred(prof_id, {'admin-user': 'username2'}, user_login)
        # update only passwd
        self._update_cred(prof_id, {'admin-password': 'password2'}, user_login)
        # update both
        self._update_cred(
            prof_id,
            {'admin-user': 'username3', 'admin-password': 'password3'},
            user_login
        )
    # test_add_update_credentials()

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
    # test_add_update_conflict()

    def test_add_update_parameters(self):
        """
        Test scenarios concerning add/update of the parameters field
        """
        user_login = 'user_user@domain.com'

        # create a new CPC system
        system_obj = models.System(
            name="cpc_y",
            state="AVAILABLE",
            modifier=user_login,
            type="cpc",
            hostname="hmc_y.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner=user_login,
        )
        self.db.session.add(system_obj)
        self.db.session.commit()
        system_id = system_obj.id
        system_name = system_obj.name

        test_liveimg = {
            'liveimg-insfile-url': 'ftp://user:pass@server._com/dir/image.ins'
        }
        test_kargs = {'linux-kargs-target': 'nosmt=true selinux=0 ro'}

        # create profile for CPC
        data = next(self._get_next_entry)
        data['system'] = system_name
        user_cred = '{}:a'.format(user_login)

        # try to create profile with custom kargs for CPC - fails
        error_msg = 'Field "parameters" is not in valid format'
        data['parameters'] = {'linux-kargs-target': 'selinux=0'}
        resp = self._do_request('create', user_cred, data)
        self._validate_resp(resp, error_msg, 400)

        # create profile with liveimg url - works
        test_liveimg = {
            'liveimg-insfile-url': 'ftp://user:pass@server._com/dir/image.ins'
        }
        data['parameters'] = test_liveimg
        data['default'] = True
        prof_id = self._request_and_assert('create', user_cred, data)
        # remove liveimg url
        update_data = {'id': prof_id, 'parameters': None}
        self._request_and_assert('update', user_cred, update_data)

        # try to update with custom kargs - fails
        update_data = {'id': prof_id, 'parameters': test_kargs}
        resp = self._do_request('update', user_cred, update_data)
        self._validate_resp(resp, error_msg, 400)

        # add liveimg url again (update)
        update_data = {'id': prof_id, 'parameters': test_liveimg}
        self._request_and_assert('update', user_cred, update_data)

        # clean up
        models.SystemProfile.query.filter_by(id=prof_id).delete()
        models.System.query.filter_by(id=system_id).delete()
        self.db.session.commit()

        # create profile for non CPC
        data = next(self._get_next_entry)
        data['parameters'] = test_liveimg
        # try to create profile with liveimg url for non CPC - fails
        resp = self._do_request('create', user_cred, data)
        self._validate_resp(resp, error_msg, 400)

        # create profile with kargs - works
        data['parameters'] = test_kargs
        data['default'] = True
        prof_id = self._request_and_assert('create', user_cred, data)
        # remove kargs
        update_data = {'id': prof_id, 'parameters': None}
        self._request_and_assert('update', user_cred, update_data)

        # try to update profile with liveimg url - fails
        update_data = {'id': prof_id, 'parameters': test_liveimg}
        resp = self._do_request('update', user_cred, update_data)
        self._validate_resp(resp, error_msg, 400)

        # add kargs again (update)
        update_data = {'id': prof_id, 'parameters': test_kargs}
        self._request_and_assert('update', user_cred, update_data)

    # test_add_update_parameters()

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
            ('parameters', {}),
            ('credentials', 5),
            ('credentials', 'something_wrong'),
            ('credentials', {'wrong_key': 'something_wrong'}),
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

    def test_add_update_list_read_zvm(self):
        """
        Test creation/update/list/read of profiles for a zVM guest
        """
        # store the start time for later comparison with datetime fields
        time_range = [int(time.time() - 5)]

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
        # first profile being created is set to default, set here so that
        # validation later works
        data['default'] = True
        user_login = '{}:a'.format('user_user@domain.com')

        # try to create profile without zvm password, causes error
        resp = self._do_request('create', user_login, data)
        zvm_msg = 'For zVM guests the zVM password must be specified'
        self._validate_resp(resp, zvm_msg, 422)

        # add missing info and create profile correctly
        data['credentials']['admin-user'] = 'username'
        data['credentials']['admin-password'] = 'password'
        data['credentials']['zvm-password'] = 'vmpass'
        prof_id = self._request_and_assert('create', user_login, data)
        # add the end time for later comparison with datetime fields
        time_range.append(int(time.time() + 5))

        # update zvm password
        self._update_cred(prof_id, {'zvm-password': 'vmpass2'}, user_login)
        # add logonby password
        self._update_cred(prof_id, {'zvm-logonby': 'vmadmin'}, user_login)
        # update both
        self._update_cred(
            prof_id,
            {'zvm-password': 'vmpass3', 'zvm-logonby': 'vmadmin2'},
            user_login
        )
        # update admin username
        self._update_cred(
            prof_id,
            {'admin-user': 'username2'},
            user_login
        )
        # update admin password
        self._update_cred(
            prof_id,
            {'admin-password': 'password2'},
            user_login
        )
        # update admin credentials
        self._update_cred(
            prof_id,
            {'admin-user': 'username3', 'admin-password': 'password3'},
            user_login
        )
        # update all
        self._update_cred(
            prof_id,
            {
                'admin-user': 'username4', 'admin-password': 'password4',
                'zvm-password': 'vmpass4', 'zvm-logonby': 'vmadmin3'
            },
            user_login
        )
        # unset logonby
        self._update_cred(prof_id, {'zvm-logonby': None}, user_login)
        # set logonby again
        self._update_cred(prof_id, {'zvm-logonby': 'vmadmin5'}, user_login)

        # create another profile including logonby
        data_2 = next(self._get_next_entry)
        data_2['system'] = system_name
        data_2['credentials']['admin-user'] = 'username'
        data_2['credentials']['admin-password'] = 'password'
        data_2['credentials']['zvm-password'] = 'vmpass'
        data_2['credentials']['zvm-logonby'] = 'vmadmin'
        prof_id_2 = self._request_and_assert('create', user_login, data_2)
        # update zvm password
        self._update_cred(prof_id_2, {'zvm-password': 'vmpass2'}, user_login)
        # update logonby password
        self._update_cred(prof_id_2, {'zvm-logonby': 'vmadmin2'}, user_login)
        # update both
        self._update_cred(
            prof_id_2,
            {'zvm-password': 'vmpass3', 'zvm-logonby': 'vmadmin3'},
            user_login
        )
        # update all
        self._update_cred(
            prof_id_2,
            {
                'admin-user': 'username2', 'admin-password': 'password2',
                'zvm-password': 'vmpass4', 'zvm-logonby': 'vmadmin3'
            },
            user_login
        )
        # unset logonby
        self._update_cred(prof_id_2, {'zvm-logonby': None}, user_login)

        # test listing to make sure credentials' secrets are stripped
        # prepare expected response
        data['default'] = True
        data['credentials']['admin-user'] = 'username4'
        data['credentials']['admin-password'] = MARKER_STRIPPED_SECRET
        data['credentials']['zvm-password'] = MARKER_STRIPPED_SECRET
        data['credentials']['zvm-logonby'] = 'vmadmin5'
        data_2['credentials']['admin-user'] = 'username2'
        data_2['credentials']['admin-password'] = MARKER_STRIPPED_SECRET
        data_2['credentials']['zvm-password'] = MARKER_STRIPPED_SECRET
        data_2['credentials'].pop('zvm-logonby')
        # validate list
        params = 'where={}'.format(json.dumps({'system': system_name}))
        resp = self._do_request(
            'list', '{}:a'.format(user_login), params)
        self._assert_listed_or_read(resp, [data, data_2], time_range)
        # validate read
        resp = self._do_request(
            'get', '{}:a'.format(user_login), prof_id)
        self._assert_listed_or_read(
            resp, [data], time_range, read=True)

        # clean up
        self.RESOURCE_MODEL.query.filter_by(id=prof_id).delete()
        self.RESOURCE_MODEL.query.filter_by(id=prof_id_2).delete()
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
        data['credentials']['admin-user'] = 'username'
        data['credentials']['admin-password'] = 'password'
        data['credentials']['zvm-password'] = 'vmpass'
        resp = self._do_request('create', user_login, data)
        zvm_msg = 'zVM credentials should be provided for zVM guests only'
        self._validate_resp(resp, zvm_msg, 422)

        # try to create profile with zvm logonby, causes error
        data['credentials'].pop('zvm-password')
        data['credentials']['zvm-logonby'] = 'vmadmin'
        resp = self._do_request('create', user_login, data)
        zvm_msg = 'zVM credentials should be provided for zVM guests only'
        self._validate_resp(resp, zvm_msg, 422)

        # remove zvm info and create profile correctly
        data['credentials'].pop('zvm-logonby')
        resp = self._do_request('create', user_login, data)
        created_id = int(resp.get_data(as_text=True))

        # try to add zvm password to existing profile, causes error
        data['id'] = created_id
        data['credentials']['zvm-password'] = 'vmpass'
        resp = self._do_request('update', user_login, data)
        self._validate_resp(resp, zvm_msg, 422)

        # try to add zvm logonby to existing profile, causes error
        data['credentials'].pop('zvm-password')
        data['credentials']['zvm-logonby'] = 'vmadmin'
        resp = self._do_request('update', user_login, data)
        self._validate_resp(resp, zvm_msg, 422)

        # clean up
        created_entry = self.RESOURCE_MODEL.query.filter_by(
            id=created_id).one()
        self.db.session.delete(created_entry)
        self.db.session.commit()
    # test_add_update_zvm()

    def test_attach_detach_disk(self):
        """
        Exercise different scenarios of attaching/detaching disks
        """
        # prepare the target profile
        data = next(self._get_next_entry)
        prof_id = self._request_and_assert('create', 'admin:a', data)

        # restore original system owner on test end/failure to avoid causing
        # problems with other tests
        sys_obj = models.System.query.filter_by(
            name=self._target_lpar).one()
        orig_sys_owner = sys_obj.owner
        def restore_owner():
            """Helper cleanup"""
            # reset flask user to admin
            self._do_request('list', 'admin:a')

            sys_obj = models.System.query.filter_by(
                name=self._target_lpar).one()
            sys_obj.owner = orig_sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()
        self.addCleanup(restore_owner)

        # create target disk
        disk_name = '1111_test_attach_detach_disk'
        disk_obj = models.StorageVolume(
            server='DSK8_x_0',
            system=self._target_lpar,
            volume_id=disk_name,
            type='DASD',
            size=10000,
            part_table=None,
            system_attributes={},
            owner='admin',
            modifier='admin',
            project=self._db_entries['Project'][0]['name'],
            desc='some description'
        )
        self.db.session.add(disk_obj)
        self.db.session.commit()
        disk_id = disk_obj.id

        def assert_actions(login, disk_owner, sys_owner, assign,
                           error_msg=None, http_code=403):
            """
            Helper to prepare environment and validate attach/detach actions
            """
            # set system ownership
            # reset flask user to admin
            self._do_request('list', 'user_hw_admin@domain.com:a')

            sys_obj = models.System.query.filter_by(
                name=self._target_lpar).one()
            sys_obj.owner = sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()

            # disk assignment to system
            disk_obj = models.StorageVolume.query.filter_by(
                volume_id=disk_name).one()
            if assign:
                disk_obj.system = sys_obj.name
            else:
                disk_obj.system = None
            # disk ownership
            disk_obj.owner = disk_owner
            self.db.session.add(disk_obj)
            self.db.session.commit()

            # removing existing disk associations first
            models.StorageVolumeProfileAssociation.query.filter_by(
                volume_id=disk_id, profile_id=prof_id).delete()
            self.db.session.commit()

            args = [disk_id, prof_id, '{}:a'.format(login)]
            # no error msg expected: expect a 200 response
            if not error_msg:
                self._req_att_disk(*args)
                self._req_det_disk(*args)

                # disk was not assigned to system: validate that it is now
                if not assign:
                    disk_obj = models.StorageVolume.query.filter_by(
                        volume_id=disk_name).one()
                    self.assertEqual(
                        disk_obj.system, self._target_lpar,
                        'Disk was not assigned to system after attach')
                return

            resp = self._req_att_disk(*args, validate=False)
            self._validate_resp(resp, error_msg, http_code)

            # prepare association for detach
            assoc_obj = models.StorageVolumeProfileAssociation(
                volume_id=disk_id, profile_id=prof_id)
            self.db.session.add(assoc_obj)
            self.db.session.commit()
            # try detach
            resp = self._req_det_disk(*args, validate=False)
            self._validate_resp(resp, error_msg, http_code)
        # assert_actions()

        # logins with no update role
        logins_no_role = ('user_user@domain.com', 'user_restricted@domain.com')
        for login in logins_no_role:
            # attach disk assigned to system, user has no permission to system
            # nor disk (fails)
            if login == 'user_restricted@domain.com':
                msg = ("No associated item found with value "
                       "'25' for field 'profile_id'")
                http_code = 422
            else:
                msg = 'User has no UPDATE permission for the specified system'
                http_code = 403
            assert_actions(login, 'admin', 'admin', assign=True, error_msg=msg,
                           http_code=http_code)

            # attach disk assigned to system, user is owner of system but
            # no permission to disk (works)
            assert_actions(login, 'admin', login, assign=True)

            # attach disk assigned to system, user is owner of system and
            # disk (works)
            assert_actions(login, login, login, assign=True)

            # attach disk unassigned to system, user is owner of system but
            # no permission to disk (fails)
            if login == 'user_restricted@domain.com':
                msg = ("No associated item found with value "
                       "'6' for field 'volume_id'")
                http_code = 422
            else:
                msg = 'User has no UPDATE permission for the specified volume'
                http_code = 403
            assert_actions(login, 'admin', login, assign=False, error_msg=msg,
                           http_code=http_code)

        # logins with an update-system role but no update-disk
        logins_sys_no_disk = (
            'user_privileged@domain.com', 'user_project_admin@domain.com')
        for login in logins_sys_no_disk:
            # attach disk assigned to system, user has permission to system but
            # not to disk (works)
            assert_actions(login, 'admin', 'admin', assign=True)

            # attach disk assigned to system, user has permission to system and
            # is owner of disk (works)
            assert_actions(login, login, 'admin', assign=True)

            # attach disk unassigned to system, user has permission to system
            # but not to disk (fails)
            msg = 'User has no UPDATE permission for the specified volume'
            assert_actions(login, 'admin', 'admin', assign=False,
                           error_msg=msg)

            # attach disk unassigned to system, user has permission to system
            # and is owner of disk (works)
            assert_actions(login, login, 'admin', assign=False)

        logins_with_both_roles = (
            'user_hw_admin@domain.com', 'user_admin@domain.com')
        for login in logins_with_both_roles:
            # attach disk assigned to system, user has permission to system and
            # disk (works)
            assert_actions(login, 'admin', 'admin', assign=True)

            # attach disk unassigned system, user has permission to system and
            # disk (works)
            assert_actions(login, 'admin', 'admin', assign=False)

        # test the case where the disk is already assigned to another system
        sys_2_obj = models.System(
            name="lpar test_attach_detach_disk",
            state="AVAILABLE",
            modifier='admin',
            type="LPAR",
            hostname="lpar.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner='admin',
        )
        self.db.session.add(sys_2_obj)
        self.db.session.commit()
        for login in (logins_no_role + logins_sys_no_disk +
                      logins_with_both_roles):
            # set ownerships
            # reset flask user to admin
            self._do_request('list', 'admin:a')
            sys_obj = models.System.query.filter_by(
                name=self._target_lpar).one()
            sys_obj.owner = login
            self.db.session.add(sys_obj)
            sys_2_obj.owner = login
            self.db.session.add(sys_2_obj)
            disk_obj = models.StorageVolume.query.filter_by(
                volume_id=disk_name).one()
            disk_obj.owner = login
            disk_obj.system = sys_2_obj.name
            self.db.session.add(disk_obj)
            self.db.session.commit()

            resp = self._req_att_disk(
                disk_id, prof_id, '{}:a'.format(login), validate=False)
            msg = 'The volume is already assigned to system {}'.format(
                sys_2_obj.name)
            self._validate_resp(resp, msg, 409)

        # test the case where the disk is already attached to the profile
        # reset flask user to admin
        self._do_request('list', 'admin:a')
        disk_obj = models.StorageVolume.query.filter_by(
            volume_id=disk_name).one()
        disk_obj.system = sys_obj.name
        self.db.session.add(disk_obj)
        self.db.session.commit()
        self._req_att_disk(disk_id, prof_id, 'admin:a')
        resp = self._req_att_disk(
            disk_id, prof_id, 'admin:a', validate=False)
        self._validate_resp(
            resp, 'The volume specified is already attached to the profile',
            409)
        # test trying to detach when it is not attached
        self._req_det_disk(disk_id, prof_id, 'admin:a')
        resp = self._req_det_disk(
            disk_id, prof_id, 'admin:a', validate=False)
        self._validate_resp(
            resp, 'The volume specified is not attached to the profile', 404)

        # clean up
        self.db.session.delete(sys_2_obj)
        self.db.session.delete(disk_obj)
        self.db.session.commit()
    # test_attach_detach_disk()

    def test_attach_detach_iface(self):
        """
        Exercise different scenarios of attaching/detaching interfaces
        """
        # prepare the target profile
        data = next(self._get_next_entry)
        prof_id = self._request_and_assert('create', 'admin:a', data)

        # restore original system owner on test end/failure to avoid causing
        # problems with other tests
        sys_obj = models.System.query.filter_by(
            name=self._target_lpar).one()
        orig_sys_owner = sys_obj.owner
        def restore_owner():
            """Helper cleanup"""
            # reset flask user to admin
            self._do_request('list', 'admin:a')

            sys_obj = models.System.query.filter_by(
                name=self._target_lpar).one()
            sys_obj.owner = orig_sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()
        self.addCleanup(restore_owner)

        # create target interface
        iface_obj = models.SystemIface(
            name='iface_test_attach_detach_iface',
            osname='eth0',
            system=self._target_lpar,
            type='OSA',
            ip_address=None,
            mac_address='00:11:22:33:44:55',
            attributes={'ccwgroup': '0.0.f101,0.0.f102,0.0.f103',
                        'layer2': True},
            desc='Description iface'
        )
        self.db.session.add(iface_obj)
        self.db.session.commit()
        iface_id = iface_obj.id

        def assert_actions(login, sys_owner, error_msg=None, http_code=403):
            """
            Helper to prepare environment and validate attach/detach actions
            """
            # set system ownership
            # reset flask user to admin
            self._do_request('list', 'admin:a')
            sys_obj = models.System.query.filter_by(
                name=self._target_lpar).one()
            sys_obj.owner = sys_owner
            self.db.session.add(sys_obj)
            self.db.session.commit()

            # removing existing iface associations first
            models.SystemIfaceProfileAssociation.query.filter_by(
                iface_id=iface_id, profile_id=prof_id).delete()

            args = [iface_id, prof_id, '{}:a'.format(login)]
            if not error_msg:
                self._req_att_iface(*args)
                self._req_det_iface(*args)
                return

            resp = self._req_att_iface(*args, validate=False)
            self._validate_resp(resp, error_msg, http_code)

            # prepare association for detach
            assoc_obj = models.SystemIfaceProfileAssociation(
                iface_id=iface_id, profile_id=prof_id)
            self.db.session.add(assoc_obj)
            self.db.session.commit()
            # try detach
            resp = self._req_det_iface(*args, validate=False)
            self._validate_resp(resp, error_msg, http_code)
        # assert_actions()

        # logins with no update role
        logins_no_role = ('user_user@domain.com', 'user_restricted@domain.com')
        for login in logins_no_role:
            # attach iface, user has no permission to system (fails)
            if login == 'user_restricted@domain.com':
                msg = ("No associated item found with value "
                       "'26' for field 'profile_id'")
                http_code = 422
            else:
                msg = 'User has no UPDATE permission for the specified system'
                http_code = 403
            assert_actions(login, 'admin', error_msg=msg, http_code=http_code)

            # attach iface assigned to system, user is owner of system (works)
            assert_actions(login, login)

        # logins with an update-system role
        logins_sys_role = (
            'user_privileged@domain.com', 'user_project_admin@domain.com',
            'user_hw_admin@domain.com', 'user_admin@domain.com')
        for login in logins_sys_role:
            # attach iface, user has permission to system (works)
            assert_actions(login, 'admin')

            # attach disk assigned to system, user is owner of system (works)
            assert_actions(login, login)

        # test the case where the iface does not belong to same system as
        # profile
        sys_2_obj = models.System(
            name="lpar test_attach_detach_iface",
            state="AVAILABLE",
            modifier='admin',
            type="LPAR",
            hostname="lpar.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner='admin',
        )
        self.db.session.add(sys_2_obj)
        self.db.session.commit()
        iface_2_obj = models.SystemIface(
            name='iface_2_test_attach_detach_iface',
            osname='eth0',
            system=sys_2_obj.name,
            type='OSA',
            ip_address=None,
            mac_address='00:11:22:33:44:55',
            attributes={'ccwgroup': '0.0.f101,0.0.f102,0.0.f103',
                        'layer2': True},
            desc='Description iface'
        )
        self.db.session.add(iface_2_obj)
        self.db.session.commit()
        resp = self._req_att_iface(
            iface_2_obj.id, prof_id, 'admin:a', validate=False)
        msg = 'Profile and network interface belong to different systems'
        self._validate_resp(resp, msg, 409)

        # test the case where the iface is already attached to the profile
        self._req_att_iface(iface_id, prof_id, 'admin:a')
        resp = self._req_att_iface(
            iface_id, prof_id, 'admin:a', validate=False)
        self._validate_resp(
            resp,
            'The network interface specified is already attached to the '
            'profile', 409)
        # test trying to detach when it is not attached
        self._req_det_iface(iface_id, prof_id, 'admin:a')
        resp = self._req_det_iface(
            iface_id, prof_id, 'admin:a', validate=False)
        self._validate_resp(
            resp,
            'The network interface specified is not attached to the profile',
            404)

        # clean up
        self.db.session.delete(iface_2_obj)
        self.db.session.delete(sys_2_obj)
        self.db.session.delete(iface_obj)
        self.db.session.commit()
    # test_attach_detach_iface()

    def test_del_default_profile_multi_profiles(self):
        """
        Try to delete a default profile while others exist
        """
        user_login = '{}:a'.format('user_user@domain.com')

        # reset flask user to user
        self._do_request('list', user_login)

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
        # keep in mind that profiles use permissions from systems and for
        # deleting it's the UPDATE_SYSTEM permission that counts
        combos = [
            ('user_user@domain.com', 'user_user@domain.com'),
            ('user_user@domain.com', 'user_privileged@domain.com'),
            ('user_user@domain.com', 'user_project_admin@domain.com'),
            ('user_user@domain.com', 'user_admin@domain.com'),
            ('user_user@domain.com', 'user_hw_admin@domain.com'),
            ('user_privileged@domain.com', 'user_privileged@domain.com'),
            ('user_privileged@domain.com', 'user_project_admin@domain.com'),
            ('user_privileged@domain.com', 'user_admin@domain.com'),
            ('user_privileged@domain.com', 'user_hw_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_privileged@domain.com'),
            ('user_project_admin@domain.com', 'user_project_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_hw_admin@domain.com'),
            ('user_project_admin@domain.com', 'user_admin@domain.com'),
            ('user_admin@domain.com', 'user_privileged@domain.com'),
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
        # profiles use permissions from systems so when deleting it's the
        # system's owner and project that count for permission validation,
        # therefore we change the owner here so that user_user won't have
        # permission to update the system

        # reset flask user to admin
        self._do_request('list', 'user_admin@domain.com:a')

        system_obj = models.System.query.filter_by(
            name=self._target_lpar).one()
        orig_owner = system_obj.owner
        system_obj.owner = 'user_privileged@domain.com'
        self.db.session.add(system_obj)
        self.db.session.commit()

        try:
            combos = [
                ('user_privileged@domain.com', 'user_user@domain.com'),
                ('user_project_admin@domain.com', 'user_user@domain.com'),
                ('user_hw_admin@domain.com', 'user_user@domain.com'),
                ('user_admin@domain.com', 'user_user@domain.com'),
            ]
            self._test_del_no_role(combos)
            # restricted users have no read access
            combos = [
                ('user_privileged@domain.com', 'user_restricted@domain.com'),
                ('user_project_admin@domain.com',
                 'user_restricted@domain.com'),
                ('user_hw_admin@domain.com', 'user_restricted@domain.com'),
                ('user_admin@domain.com', 'user_restricted@domain.com'),
            ]
            self._test_del_no_role(combos, http_code=404)
        # restore system's owner
        finally:
            # reset flask user to admin
            self._do_request('list', 'user_admin@domain.com:a')

            system_obj = models.System.query.filter_by(
                name=self._target_lpar).one()
            system_obj.owner = orig_owner
            self.db.session.add(system_obj)
            self.db.session.commit()
    # test_del_no_role()

    def test_list_and_read(self):
        """
        Verify if listing and reading permissions are correctly handled
        """
        login_add = 'user_user@domain.com'
        logins_list = [
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]

        # store the existing entries and add them to the new ones for
        # later validation
        resp = self._do_request(
            'list', '{}:a'.format(login_add), None)
        entries = json.loads(resp.get_data(as_text=True))
        # adjust id field to make the http response look like the same as the
        # dict from the _create_many_entries return
        for entry in entries:
            entry['id'] = entry.pop('$uri').split('/')[-1]

        # create some more entries to work with
        new_entries, time_range = self._create_many_entries(login_add, 5)
        # add the expected marker for secrets
        for entry in new_entries:
            if not entry.get('credentials'):
                continue
            if entry['credentials'].get('admin-password'):
                entry['credentials']['admin-password'] = MARKER_STRIPPED_SECRET
        entries += new_entries

        # retrieve list
        for login in logins_list:
            resp = self._do_request('list', '{}:a'.format(login), None)
            self._assert_listed_or_read(resp, entries, time_range)

        # perform a read
        for login in logins_list:
            resp = self._do_request(
                'get', '{}:a'.format(login), entries[0]['id'])
            self._assert_listed_or_read(
                resp, [entries[0]], time_range, read=True)

    # test_list_and_read()

    def test_list_and_read_hidden_credentials(self):
        """
        Make sure users without role in a project can't see systems'
        credentials.
        """
        login_add = 'user_user@domain.com'
        login_list = 'user_no_role@domain.com'

        user_obj = models.User(
            name='User with no role',
            login=login_list,
            admin=False,
            restricted=False,
            title='User title'
        )
        self.db.session.add(user_obj)
        self.db.session.commit()

        # store the existing entries and add them to the new ones for
        # later validation
        resp = self._do_request(
            'list', '{}:a'.format(login_add), None)
        entries = json.loads(resp.get_data(as_text=True))
        self.assertGreater(len(entries), 0)

        # retrieve list
        resp = self._do_request('list', '{}:a'.format(login_list), None)

        # no roles - no list
        self._assert_listed_or_read(resp, [], None)
    # test_list_and_read_hidden_credentials()

    def test_list_and_read_restricted_no_role(self):
        """
        List entries with a restricted user without role in any project
        """
        login_list = 'user_no_role_restricted@domain.com'

        user_obj = models.User(
            name='User with no role',
            login=login_list,
            admin=False,
            restricted=True,
            title='User title'
        )
        self.db.session.add(user_obj)
        self.db.session.commit()

        self._test_list_and_read_restricted_no_role(
            'user_user@domain.com', login_list,
            allowed=False, http_code=404)
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

    def test_kvm_create_update_cpu_memory(self):
        """
        Test if api correctly reports error when invalid cpu and memory are
        used for KVM guest.
        """
        user_login = 'user_user@domain.com'

        # create a new KVM system
        system_obj = models.System(
            name="kvm_guest",
            state="AVAILABLE",
            modifier=user_login,
            type="KVM",
            hostname="hmc_y.domain.com",
            project=self._project_name,
            model="ZEC12_H20",
            owner=user_login,
        )
        self.db.session.add(system_obj)
        self.db.session.commit()
        # attributes must be stored before the object expires
        system_id = system_obj.id
        system_name = system_obj.name

        # generate a new profile entry
        data = next(self._get_next_entry)
        data['system'] = system_name
        # first profile being created is set to default, set here so that
        # validation later works
        data['default'] = True
        user_login = '{}:a'.format('user_user@domain.com')

        # try to create profile with wrong number of cpus
        data['cpu'] = 0
        data['memory'] = 1024
        resp = self._do_request('create', user_login, data)
        self._validate_resp(resp, CPU_MEM_ERROR_MSG, 422)

        # try to create profile with wrong memory size
        data['cpu'] = 7
        data['memory'] = 0
        self._validate_resp(resp, CPU_MEM_ERROR_MSG, 422)

        # try create with correct cpu and memory numbers
        data['cpu'] = 7
        data['memory'] = 1024
        prof_id = self._request_and_assert('create', user_login, data)

        # try update wrong for KVM guest cpu number
        update_data = {'id': prof_id, 'cpu': 0}
        resp = self._do_request('update', user_login, update_data)
        self._validate_resp(resp, CPU_MEM_ERROR_MSG, 422)

        # try update with wrong for KVM guest memory number
        update_data = {'id': prof_id, 'memory': 0}
        resp = self._do_request('update', user_login, update_data)
        self._validate_resp(resp, CPU_MEM_ERROR_MSG, 422)

        # try update with correct for KVM guest and memory number
        update_data = {'id': prof_id, 'cpu': 5, 'memory': 2048}
        self._request_and_assert('update', user_login, update_data)

        # clean up
        self.RESOURCE_MODEL.query.filter_by(id=prof_id).delete()
        models.System.query.filter_by(id=system_id).delete()
        self.db.session.commit()
    # test_kvm_create_update_cpu_memory()

    # TODO: add tests with gateway parameter (cannot be tested for creation as
    # a netiface must be attached first)
    # TODO: add tests with hypervisor_profile (need to improve handling of
    # indirect value hyp_name/hyp_profile_name first)
    # TODO: add tests with same hyp_profile name
# TestSystemProfile
