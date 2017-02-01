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
Unit test for storage_volumes resource module
"""

#
# IMPORTS
#
from tessia_engine.api.resources.storage_volumes import MSG_INVALID_PTABLE
from tessia_engine.api.resources.storage_volumes import MSG_INVALID_TYPE
from tessia_engine.api.resources.storage_volumes import StorageVolumeResource
from tessia_engine.db import models
from tests.unit.api.resources.secure_resource import TestSecureResource

import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestStorageVolume(TestSecureResource):
    """
    Validates the StorageVolume resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/storage-volumes'
    # model associated with this resource
    RESOURCE_MODEL = models.StorageVolume
    # potion object associated with this resource
    RESOURCE_API = StorageVolumeResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        specs_template = {
            'multipath': True,
            'adapters': [
                {
                    'devno': '0.0.1800',
                    'wwpns': [
                        '5005076300c213e5',
                        '5005076300c213e9'
                    ]
                },
                {
                    'devno': '0.0.1900',
                    'wwpns': [
                        '5005076300c213e9'
                    ]
                }
            ]
        }
        while True:
            specs_dict = specs_template.copy()
            specs_dict['wwid'] = str(10000000000 + index)
            data = {
                'project': cls._db_entries['Project'][0]['name'],
                'desc': '- Storage volume with some *markdown*',
                'volume_id': '%x' % (0x1022400000000000 + index),
                'size': 10000,
                'part_table': None,
                'specs': specs_dict,
                'system_attributes': {},
                'type': 'FCP',
                'server': 'DSK8_x_0',

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
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
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
            ('specs', None),
            ('part_table', None),
            ('desc', None),
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
        pop_fields = [
            'volume_id', 'size', 'type', 'system_attributes', 'server']
        self._test_add_missing_field('user_hw_admin@domain.com', pop_fields)
    # test_add_missing_field()

    def test_add_update_conflict(self):
        """
        Test two scenarios:
        1- add an item with a volume_id that already exists
        2- update an item to a volume_id that already exists
        """
        self._test_add_update_conflict('user_hw_admin@domain.com', 'volume_id')
    # test_update_conflict()

    def test_add_update_wrong_field(self):
        """
        Test if api correctly reports error when invalid values are used for
        a field during creation and update.
        """
        # specify fields with wrong types
        wrong_data = [
            ('volume_id', 5),
            ('volume_id', True),
            ('volume_id', None),
            ('size', -1),
            ('size', 'something_wrong'),
            ('size', '5000'),
            ('size', True),
            ('size', None),
            ('part_table', 5),
            ('part_table', 'something_wrong'),
            ('part_table', True),
            ('part_table', {'invalid': 'something'}),
            ('specs', 5),
            ('specs', 'something_wrong'),
            ('specs', True),
            ('specs', {'invalid': 'something'}),
            ('type', 'something_wrong'),
            ('type', 5),
            ('type', None),
            # server with string is an association error not bad request so
            # it is not tested here
            ('server', 5),
            ('server', None),
            ('desc', False),
            ('project', 5),
            ('project', False),
            ('owner', False),
            # read-only fields
            ('unique_id', 'something'),
            ('modified', 'something'),
            ('pool', 'something'),
            ('system', 'something'),
            ('system_profiles', 'something'),
            ('system_attributes', {'invalid': 'something'}),
            ('system_attributes', "invalid_something"),
            ('system_attributes', None),
        ]
        self._test_add_update_wrong_field(
            'user_hw_admin@domain.com', wrong_data)

        # test special cases when volume type does not match storage server
        def validate_resp(resp, attempted_type, server_type):
            """Helper validator"""
            self.assertEqual(resp.status_code, 400) # pylint: disable=no-member
            msg = MSG_INVALID_TYPE.format(attempted_type, server_type)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(msg, body['message'])
        # validate_resp()

        # exercise a failed creation due to mismatched types
        data = next(self._get_next_entry)
        orig_server_type = models.StorageServer.query.filter_by(
            name=data['server']).one().type
        data['type'] = 'ISCSI'

        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        validate_resp(resp, data['type'], orig_server_type)

        # exercise update, create an item with good values first
        item = self._create_many_entries('user_hw_admin@domain.com', 1)[0][0]

        iscsi_server = models.StorageServer(
            name='iSCSI Server',
            type='ISCSI',
            model='DSK8',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )
        iscsi_server_type = 'ISCSI'
        self.db.session.add(iscsi_server)
        self.db.session.commit()

        # 1- only update type
        update_fields = {
            'id': item['id'],
            'type': 'ISCSI',
        }
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, update_fields['type'], orig_server_type)

        # 2- update type and server
        update_fields['type'] = 'FCP'
        update_fields['server'] = 'iSCSI Server'
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, update_fields['type'], iscsi_server_type)

        # 3- only update the server
        update_fields.pop('type')
        update_fields['server'] = 'iSCSI Server'
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, item['type'], iscsi_server_type)

        self.db.session.delete(iscsi_server)
        self.db.session.commit()
    # test_add_update_wrong_field()

    def test_add_update_wrong_ptable(self):
        """
        Test the scenario where the partitions in the ptable exceed the size of
        the volume
        """
        def validate_resp(resp, parts_size, vol_size):
            """Helper validator"""
            self.assertEqual(resp.status_code, 400) # pylint: disable=no-member
            msg = MSG_INVALID_PTABLE.format(parts_size, vol_size)
            body = json.loads(resp.get_data(as_text=True))
            self.assertEqual(msg, body['message'], body)
        # validate_resp()

        # prepare a new entry for creation
        data = next(self._get_next_entry)
        data['part_table'] = {
            'type': 'msdos',
            'table': [
                {
                    'mp': '/',
                    'size': int(data['size']/2),
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/home',
                    'size': (int(data['size']/2)) + 1000,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
            ]
        }
        parts_size = sum(
            [part['size'] for part in data['part_table']['table']])
        # perform create request and validate response
        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        validate_resp(resp, parts_size, data['size'])

        # prepare an existing entry for update
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]
        entry['part_table'] = data['part_table']
        entry['part_table']['table'][0]['size'] = int(entry['size'] / 2)
        entry['part_table']['table'][1]['size'] = (
            int(entry['size'] / 2) + 1000)
        parts_size = sum(
            [part['size'] for part in entry['part_table']['table']])

        # perform update request and validate response
        update_fields = {
            'id': entry['id'],
            'part_table': entry['part_table'],
        }
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        validate_resp(resp, parts_size, entry['size'])
    # test_add_update_wrong_ptable()

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

    def test_del_has_dependent(self):
        """
        Try to delete an item which has a system profile associated with it.
        """
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]

        profile = models.SystemProfile(
            name='dependent profile',
            system='lpar0',
            default=False
        )
        self.db.session.add(profile)
        self.db.session.commit()

        # create the dependent object
        dep_profile = models.StorageVolumeProfileAssociation(
            profile_id=profile.id,
            volume_id=entry['id']
        )
        self._test_del_has_dependent(
            'user_hw_admin@domain.com', entry['id'], dep_profile)

        self.db.session.delete(profile)
        self.db.session.commit()
    # test_del_has_dependent()

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
        # some items have to be created first so that association works
        system = models.System(
            name='New system',
            hostname='new_system.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )
        storage_server = models.StorageServer(
            name='New Server',
            type='DASD-FCP',
            model='DSK8',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )
        pool = models.StoragePool(
            name='New pool',
            type='LVM_VG',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )

        self.db.session.add(system)
        self.db.session.add(storage_server)
        self.db.session.add(pool)
        self.db.session.commit()

        # part_table and specs are not searchable so we don't add them
        filter_values = {
            'owner': 'user_user@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'volume_id': 'some_id_for_filter',
            'desc': 'some_desc_for_filter',
            'system': system.name,
            'pool': pool.name,
            'type': 'FCP',
            'server': storage_server.name,
        }
        self._test_list_filtered('user_hw_admin@domain.com', filter_values)

        self.db.session.delete(storage_server)
        self.db.session.delete(system)
        self.db.session.delete(pool)
        self.db.session.commit()
    # test_list_filtered()

    def test_update_valid_fields(self):
        """
        Exercise the update of existing objects when correct format and
        writable fields are specified.
        """
        # some items have to be created first so that association works
        system = models.System(
            name='New system',
            hostname='new_system.domain.com',
            type='LPAR',
            model='ZGENERIC',
            state='AVAILABLE',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )
        storage_server = models.StorageServer(
            name='New Server',
            type='DASD-FCP',
            model='DSK8',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )
        pool = models.StoragePool(
            name='New pool',
            type='LVM_VG',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )

        self.db.session.add(system)
        self.db.session.add(storage_server)
        self.db.session.add(pool)
        self.db.session.commit()

        update_fields = {
            'owner': 'user_user@domain.com',
            'project': self._db_entries['Project'][1]['name'],
            'desc': 'some_desc',
            'volume_id': '1500',
            'type': 'DASD',
            'part_table': {'type': 'msdos', 'table': []},
            'specs': None,
            'size': 5000,
            'server': storage_server.name,
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

        # in order to test caching in update do a request to update server and
        # part_table at the same time
        item = self._create_many_entries('user_hw_admin@domain.com', 1)[0][0]
        update_fields = {
            'id': item['id'],
            'server': update_fields['server'],
            'part_table': {'type': 'msdos', 'table': []}
        }
        self._request_and_assert(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)

        # clean up
        self.db.session.query(self.RESOURCE_MODEL).filter_by(
            id=item['id']).delete()
        self.db.session.delete(system)
        self.db.session.delete(storage_server)
        self.db.session.delete(pool)
        self.db.session.commit()
    # test_update_valid_fields()

    def test_update_assoc_error(self):
        """
        Try to update a FK field to a value that has no entry in the associated
        table.
        """
        self._test_update_assoc_error(
            'user_admin@domain.com', 'server', 'some_server')
        self._test_update_assoc_error(
            'user_admin@domain.com', 'project', 'some_project')
        self._test_update_assoc_error(
            'user_admin@domain.com', 'owner', 'some_owner')
    # test_update_assoc_error()

    def test_update_no_role(self):
        """
        Try to update with a user without an appropriate role to do so.
        """
        update_fields = {
            'volume_id': 'this_should_not_work',
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

    # TODO:
    # test add same volume_id but different server
    # test invalid partition table combinations
    # storage server: do not allow to change type when volumes exist
    # filter by modifier and modified fields

# TestStorageVolume
