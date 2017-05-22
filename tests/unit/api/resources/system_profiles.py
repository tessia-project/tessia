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
            }
            index += 1
            yield data
    # _entry_gen()

    def test_add_update_profile_without_hypervisor(self):
        """
        Test if api correctly reports error when a mandatory hypervisor is
        missing during creation and updating.
        """
        system_obj = models.System(
            name="system without hypervisor",
            state="AVAILABLE",
            modifier="user_x_0@domain.com",
            type="cpc",
            hostname="cpc-0.domain.com",
            project="Department x",
            model="ZEC12_H20",
            owner="user_x_0@domain.com",
        )

        def validate_resp(resp, msg, status_code):
            """Helper validator"""
            self.assertEqual(resp.status_code, status_code)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(msg, body['message'])
        # validate_resp()

        # add profile without target system
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        resp = self._do_request(
            'create', 'user_admin@domain.com:a', data)
        msg = ("No associated item found with value "
               "'system without hypervisor' for field 'System'")
        validate_resp(resp, msg, 422)

        self.db.session.add(system_obj)
        self.db.session.commit()

        # add hypervisor profile without target hypervisor
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        data['hypervisor_profile'] = 'default cpc0'
        resp = self._do_request(
            'create', 'user_admin@domain.com:a', data)
        msg = "System has no hypervisor, you need to define one first"
        validate_resp(resp, msg, 400)

        # update hypervisor profile without target hypervisor
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        created_id = self._request_and_assert(
            'create', '{}:a'.format('user_admin@domain.com:a'), data)
        data['id'] = created_id
        data['hypervisor_profile'] = 'default cpc0'
        resp = self._do_request(
            'update', 'user_admin@domain.com:a', data)
        msg = "System has no hypervisor, you need to define one first"
        validate_resp(resp, msg, 400)

        # delete hypervisor profile
        self._do_request(
            'delete', 'user_admin@domain.com:a', created_id)

        self.db.session.delete(system_obj)
        self.db.session.commit()
    # test_add_update_profile_without_hypervisor()

    def test_add_update_profile_with_wrong_hypervisor(self):
        """
        Test if api correctly handles wrong hypervisor_profile
        during creation and updating.
        """
        system_obj = models.System(
            name="system with another hypervisor",
            state="AVAILABLE",
            modifier="user_x_0@domain.com",
            type="cpc",
            hostname="cpc-0.domain.com",
            project="Department x",
            model="ZEC12_H20",
            owner="user_x_0@domain.com",
            hypervisor="cpc0"
        )

        self.db.session.add(system_obj)
        self.db.session.commit()

        # add and update hypervisor profile with wrong hypervisor
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        wrong_data = [
            ('hypervisor_profile', 'wrong_hypervisor'),
        ]
        self._test_add_update_assoc_error(
            'user_admin@domain.com:a', wrong_data)

        self.db.session.delete(system_obj)
        self.db.session.commit()
    # test_add_update_profile_with_wrong_hypervisor()

    def test_add_update_profile_with_hypervisor(self):
        """
        Test if api correctly handles correct hypervisor_profile
        during creation and updating.
        """
        system_obj = models.System(
            name="system with hypervisor",
            state="AVAILABLE",
            modifier="user_x_0@domain.com",
            type="cpc",
            hostname="cpc-0.domain.com",
            project="Department x",
            model="ZEC12_H20",
            owner="user_x_0@domain.com",
            hypervisor="cpc0"
        )

        self.db.session.add(system_obj)
        self.db.session.commit()

        # create hypervisor profile with correct hypervisor
        data = next(self._get_next_entry)
        data['system'] = system_obj.name
        data['default'] = False
        data['hypervisor_profile'] = 'default cpc0'
        resp = self._do_request(
            'create', 'user_admin@domain.com:a', data)
        self.assertEqual(resp.status_code, 200)
        created_id = int(resp.get_data(as_text=True))

        # update hypervisor profile with correct hypervisor
        data['id'] = created_id
        data['default'] = True
        resp = self._do_request(
            'update', 'user_admin@domain.com:a', data)
        self.assertEqual(resp.status_code, 200)

        # delete hypervisor profile
        self._do_request(
            'delete', 'user_admin@domain.com:a', created_id)

        self.db.session.delete(system_obj)
        self.db.session.commit()
    # test_add_update_profile_with_hypervisor()

# TestSystemProfile
