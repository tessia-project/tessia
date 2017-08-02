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
from tessia_engine.api.resources.system_profiles import SystemProfileResource
from tessia_engine.db import models
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
                'default': True,
                'parameters': {},
                'credentials': {},
            }
            index += 1
            yield data
    # _entry_gen()

    @classmethod
    def setUpClass(cls):
        """
        Update systems to the same project of the test users.
        """
        super(TestSystemProfile, cls).setUpClass()

        # fetch which project to use from the test user
        project_name = models.UserRole.query.join(
            'project_rel'
        ).join(
            'user_rel'
        ).filter(
            models.UserRole.user == 'user_user@domain.com'
        ).one().project

        for system_obj in models.System.query.all():
            system_obj.project = project_name
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

    def test_add_mandatory_fields(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying only the mandatory fields.
        """
        # the fields to be omitted and their expected values on response
        pop_fields = [('parameters', None)]
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

    def test_add_update_assoc_error(self):
        """
        Try creation and edit while setting a FK field to a value that has no
        entry in the associated table.
        """
        wrong_fields = [
            ('gateway', 'some_gateway'),
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
            ('operating_system', 'something'),
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
        # fetch which project to use
        project_name = models.UserRole.query.join(
            'project_rel'
        ).join(
            'user_rel'
        ).filter(
            models.UserRole.user == 'user_user@domain.com'
        ).one().project

        system_obj = models.System(
            name="cpc_no_hypervisor",
            state="AVAILABLE",
            modifier="user_user@domain.com",
            type="cpc",
            hostname="cpc-0.domain.com",
            project=project_name,
            model="ZEC12_H20",
            owner="user_user@domain.com",
        )

        def validate_resp(resp, msg, status_code):
            """Helper validator"""
            self.assertEqual(resp.status_code, status_code)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(msg, body['message'])
        # validate_resp()

        self.db.session.add(system_obj)
        self.db.session.commit()

        # add profile while specifying a hypervisor profile
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        data['hypervisor_profile'] = 'default cpc0'
        resp = self._do_request(
            'create', 'user_user@domain.com:a', data)
        msg = "System has no hypervisor, you need to define one first"
        validate_resp(resp, msg, 400)

        # update profile while specifying a hypervisor profile
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        created_id = self._request_and_assert(
            'create', '{}:a'.format('user_user@domain.com:a'), data)
        data['id'] = created_id
        data['hypervisor_profile'] = 'default cpc0'
        resp = self._do_request(
            'update', 'user_user@domain.com:a', data)
        msg = "System has no hypervisor, you need to define one first"
        validate_resp(resp, msg, 400)

        # delete profile
        self._do_request(
            'delete', 'user_user@domain.com:a', created_id)

        self.db.session.delete(system_obj)
        self.db.session.commit()
    # test_add_update_profile_without_hypervisor()

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

    # TODO: add tests with gateway parameter (cannot be tested for creation as
    # a netiface must be attached first)
    # TODO: add tests with hypervisor_profile (need to improve handling of
    # indirect value hyp_name/hyp_profile_name first)
    # TODO: add tests for attach/detach of volumes/network interfaces
    # TODO: add tests with same hyp_profile name
# TestSystemProfile
