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
Unit test for net_zones resource module
"""

#
# IMPORTS
#
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia_engine.db import models

import json
import time

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestNetZones(TestSecureResource):
    """
    Validates the NetZones resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/net-zones'
    # model associated with this resource
    RESOURCE_MODEL = models.NetZone

    def _create_many_entries(self, owner, qty=1):
        """
        Helper to conveniently create many entries in the database

        Args:
            owner (str): login of user owning items
            qty (int): number of entries to create

        Returns:
            tuple: (list_of_entries, [start_time, end_time])
        """
        # store the start time for later comparison with datetime fields
        time_range = [int(time.time() - 5)]
        # create the entries to work with
        entries = []
        for _ in range(0, qty):
            data = next(self._get_next_entry)
            created_id = self._request_and_assert(
                'create', '{}:a'.format(owner), data)
            data['id'] = created_id
            entries.append(data)
        # store the end time for later comparison with datetime fields
        time_range.append(int(time.time() + 5))

        return (entries, time_range)
    # _create_many_entries()

    @staticmethod
    def _entry_gen():
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'project': 'Netzone project',
                'desc': '- Zone with some *markdown*',
                'name': 'new-zone {}'.format(index)
            }
            index += 1
            yield data
    # _entry_gen()

    @classmethod
    def setUpClass(cls):
        """
        Called once before any test in this test class runs.
        Create the database with some users and roles and initialize the
        entry generator.
        """
        super().setUpClass()

        cls.users = {
            "User": [
                {
                    "name": "user_restricted",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": True,
                    "login": "user_restricted@domain.com"
                },
                {
                    "name": "user_user",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_user@domain.com"
                },
                {
                    "name": "user_project_admin",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_project_admin@domain.com"
                },
                {
                    "name": "hardware_admin",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_hw_admin@domain.com"
                },
                {
                    "name": "admin",
                    "admin": True,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_admin@domain.com"
                },
            ],
            "Project": [
                {
                    "name": "Netzone project",
                    "desc": "Netzone test",
                }
            ],
            "UserRole": [
                {
                    "project": "Netzone project",
                    "user": "user_user@domain.com",
                    "role": "User"
                },
                {
                    "project": "Netzone project",
                    "user": "user_project_admin@domain.com",
                    "role": "Project admin"
                },
                {
                    "project": "Netzone project",
                    "user": "user_hw_admin@domain.com",
                    "role": "Hardware admin"
                }
            ],
        }
        cls.db.create_entry(cls.users)

        cls._get_next_entry = cls._entry_gen()
    # setUpClass()

    def test_add_all_fields_many_roles(self):
        """
        Exercise the scenario where a user with permissions creates a netzone
        by specifying all possible fields.
        """
        # try to add as hw admin role
        data = next(self._get_next_entry)
        self._request_and_assert(
            'create', 'user_hw_admin@domain.com:a', data)

        # try to add as admin
        data = next(self._get_next_entry)
        self._request_and_assert('create', 'user_admin@domain.com:a', data)
    # test_add_all_fields_many_roles()

    def test_add_all_fields_fail(self):
        """
        Exercise the scenario where a normal user without permissions tries to
        create a netzone and fails.
        """
        # try as normal user, in this case it should fail
        data = next(self._get_next_entry)
        resp = self._do_request('create', 'user_user@domain.com:a', data)
        # validate the response received, should be forbidden
        self.assertEqual(resp.status_code, 403) # pylint: disable=no-member
    # test_add_all_fields_many_roles()

    def test_add_mandatory_fields(self):
        """
        Exercise the scenario where a user with permissions creates a netzone
        by specifying only the mandatory fields.
        """
        # specify name only
        data = next(self._get_next_entry)
        data.pop('desc')
        data.pop('project')
        resp = self._do_request(
            'create', 'user_hw_admin@domain.com:a', data)
        # validate the response received
        data['desc'] = None
        data['project'] = 'Netzone project'
        self._assert_created(resp, data)
    # test_add_mandatory_fields()

    def test_add_mandatory_fields_fail(self):
        """
        Exercise the scenario where the attempt to create a netzone by
        specifying only mandatory fields fails.
        """
        # try to add as admin - without project specified it should fail as api
        # does not know which project to add since this admin user entry has no
        # role in any project
        data = next(self._get_next_entry)
        data.pop('desc')
        data.pop('project')
        resp = self._do_request('create', 'user_admin@domain.com:a', data)
        # validate the response received 403 forbidden
        self.assertEqual(resp.status_code, 403) # pylint: disable=no-member

        # try as normal user
        resp = self._do_request('create', 'user_user@domain.com:a', data)
        # validate the response received, should be forbidden
        self.assertEqual(resp.status_code, 403) # pylint: disable=no-member
    # test_add_mandatory_fields_fail()

    def test_add_wrong_field_format(self):
        """
        Test if api correctly reports error when an invalid format is used for
        a field during creation.
        """
        # specify a field with wrong type
        data = {'name': 5}
        resp = self._do_request(
            'create', 'user_hw_admin@domain.com:a', data)
        # validate the response received
        self.assertEqual(resp.status_code, 400) # pylint: disable=no-member
    # test_add_wrong_field_format()

    def test_add_missing_field(self):
        """
        Test if api correctly reports error when an invalid format is used for
        a field during creation.
        """
        # specify an optional field and miss a mandatory
        data = next(self._get_next_entry)
        data.pop('name')
        resp = self._do_request(
            'create', 'user_hw_admin@domain.com:a', data)
        # validate the response received
        self.assertEqual(resp.status_code, 400) # pylint: disable=no-member
    # test_add_wrong_field_format()

    def test_del_many_roles(self):
        """
        Exercise to remove entries with different roles
        """
        # 1- create the item to be deleted
        data = next(self._get_next_entry)
        created_id = self._request_and_assert(
            'create', 'user_hw_admin@domain.com:a', data)

        # now request to remove it as a hardware admin
        self._request_and_assert(
            'delete', 'user_hw_admin@domain.com:a', created_id)

        # 2- delete as admin
        data = next(self._get_next_entry)
        created_id = self._request_and_assert(
            'create', 'user_admin@domain.com:a', data)
        # request to remove it
        self._request_and_assert(
            'delete', 'user_admin@domain.com:a', created_id)
    # test_del_many_roles()

    def test_del_has_dependent(self):
        """
        Try to delete a netzone which has a subnet associated with it.
        """
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]

        dep_subnet = models.Subnet(
            name="some_subnet",
            zone=entry['name'],
            address="192.168.0.0/24",
            modifier="user_hw_admin@domain.com",
            desc="",
            vlan=1801,
            project="Netzone project",
            gateway=None,
            dns_1=None,
            dns_2=None,
            owner="user_hw_admin@domain.com"
        )
        self.db.session.add(dep_subnet)
        self.db.session.commit()
        resp = self._do_request(
            'delete', 'user_hw_admin@domain.com:a', entry['id'])
        # validate a conflict response
        # TODO: validate return message when running under postgres
        self.assertEqual(resp.status_code, 409) # pylint: disable=no-member

        # remove subnet to avoid problems with other testcases
        self.db.session.delete(dep_subnet)
        self.db.session.commit()
    # test_del_has_dependent()

    def test_del_invalid_id(self):
        """
        Test if api correctly handles the case when trying to delete an
        invalid id
        """
        resp = self._do_request(
            'delete', 'admin@domain.com:a', -1)
        # validate deletion failed with 404 not found
        self.assertEqual(resp.status_code, 404) # pylint: disable=no-member
    # test_del_wrong_id()

    def test_del_no_role(self):
        """
        Try to remove an entry without permissions
        """
        # create the target entry
        data = next(self._get_next_entry)
        created_id = self._request_and_assert(
            'create', 'user_admin@domain.com:a', data)

        # delete as a user without a valid role - should fail
        resp = self._do_request(
            'delete', 'user_user@domain.com:a', created_id)
        # validate deletion failed
        self.assertEqual(resp.status_code, 403) # pylint: disable=no-member
    # test_del_no_role()

    def test_list_and_read(self):
        """
        Verify if listing and reading permissions are correctly handled
        """
        # make sure table is empty
        prev_entries = self.RESOURCE_MODEL.query.join(
            'project_rel'
        ).filter(
            self.RESOURCE_MODEL.project == 'Netzone project'
        ).all()
        for prev_entry in prev_entries:
            self.db.session.delete(prev_entry)
        self.db.session.commit()

        test_user = 'user_hw_admin@domain.com'

        # create the entries to work with
        entries, time_range = self._create_many_entries(test_user, 5)

        # retrieve list, filter by project to make sure the number of entries
        # is correct
        params = 'where={"project": "Netzone project"}'
        resp = self._do_request('list', '{}:a'.format(test_user), params)
        self._assert_listed_or_read(resp, entries, test_user, time_range)

        # perform a read
        resp = self._do_request(
            'get', '{}:a'.format(test_user), entries[0]['id'])
        self._assert_listed_or_read(
            resp, [entries[0]], test_user, time_range, read=True)
    # test_list_and_read()

    def test_list_and_read_restricted_no_role(self):
        """
        List entries with a restricted user without role in any project
        """
        # create the entries to work with
        entries, _ = self._create_many_entries(
            'user_hw_admin@domain.com', 5)

        resp = self._do_request(
            'list', 'user_restricted@domain.com:a')
        listed_entries = json.loads(resp.get_data(as_text=True))
        self.assertEqual(
            len(listed_entries), 0, 'Restricted user was able to list')

        # perform a read
        resp = self._do_request(
            'get', 'user_restricted@domain.com:a', entries[0]['id'])
        # expect a 403 forbidden
        self.assertEqual(resp.status_code, 403)
    # test_list_and_read_restricted_no_role()

    def test_list_and_read_restricted_with_role(self):
        """
        List entries with a restricted user who has a role in a project
        """
        admin_user = 'user_hw_admin@domain.com'
        restricted_user = 'user_restricted@domain.com'

        # add the role entry for the user
        admin_role = models.UserRole(
            project="Netzone project",
            user=restricted_user,
            role="User"
        )
        self.db.session.add(admin_role)
        self.db.session.commit()

        # make sure table is empty
        prev_entries = self.RESOURCE_MODEL.query.join(
            'project_rel'
        ).filter(
            self.RESOURCE_MODEL.project == 'Netzone project'
        ).all()
        for prev_entry in prev_entries:
            self.db.session.delete(prev_entry)
        self.db.session.commit()

        # create the entries to work with
        entries, time_range = self._create_many_entries(admin_user, 5)

        # retrieve list
        resp = self._do_request('list', '{}:a'.format(restricted_user))
        self._assert_listed_or_read(resp, entries, admin_user, time_range)

        # perform a read
        resp = self._do_request(
            'get', '{}:a'.format(restricted_user), entries[0]['id'])
        self._assert_listed_or_read(
            resp, [entries[0]], admin_user, time_range, read=True)

        # remove the added role to avoid conflict with other testcases
        self.db.session.delete(admin_role)
        self.db.session.commit()
    # test_list_and_read_restricted_with_role()

    def test_update_valid_fields(self):
        """
        Exercise the update of existing objects when correct format and
        writable fields are specified.
        """
        admin_user = 'user_hw_admin@domain.com'

        # create the entries to work with
        entries, _ = self._create_many_entries(admin_user, 5)

        for entry in entries:
            update_item = {
                'desc': '{}_something'.format(entry['desc']),
                # id is not updated but passed as part of the url
                'id': entry['id']
            }
            self._request_and_assert(
                'update', '{}:a'.format(admin_user), update_item)

    # test_update_valid_fields()

    def test_update_conflict(self):
        """
        Try to rename a netzone to a name that already exists.
        """
        # create one item to work with
        entries = self._create_many_entries(
            'user_hw_admin@domain.com', 2)[0]
        # ask to update its name
        updated_item = {
            'id': entries[0]['id'],
            'name': entries[1]['name'],
        }
        resp = self._do_request(
            'update', 'user_hw_admin@domain.com:a', updated_item)
        # validate a conflict
        # TODO: validate return message when running under postgres
        self.assertEqual(resp.status_code, 409) # pylint: disable=no-member
    # test_update_conflict()

    def test_update_no_role(self):
        """
        Try to update with a user without an appropriate role to do so.
        """
        # create an entry
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]
        update_item = {
            'id': entry['id'],
            'name': 'change_to_something',
        }
        resp = self._do_request(
            'update', 'user_user@domain.com:a', update_item)
        # validate the response received, should be forbidden
        self.assertEqual(resp.status_code, 403) # pylint: disable=no-member
    # test_update_no_role()
# TestNetZones
