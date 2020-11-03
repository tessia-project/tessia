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
from copy import deepcopy
from tessia.server.api.resources.storage_volumes import \
    MSG_PTABLE_SIZE_MISMATCH
from tessia.server.api.resources.storage_volumes import MSG_INVALID_TYPE
from tessia.server.api.resources.storage_volumes import MSG_INVALID_PTABLE
from tessia.server.api.resources.storage_volumes import StorageVolumeResource
from tessia.server.api.resources.storage_volumes import MSG_PTABLE_BAD_PLACE
from tessia.server.api.resources.storage_volumes import MSG_PTABLE_MANY_PARTS
from tessia.server.api.resources.storage_volumes import MSG_PTABLE_DASD_PARTS
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
        logins = [
            'user_hw_admin@domain.com',
            'user_admin@domain.com'
        ]

        # create disk without system, user has permission to disk
        self._test_add_all_fields_many_roles(logins)

        sys_name = 'New system'
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

        def cleanup_helper():
            """Helper to remove system on test end/failure"""
            self.db.session.delete(system)
            self.db.session.commit()
        self.addCleanup(cleanup_helper)
        for login in logins:
            # create disk with system, user has permission to both
            vol_new = next(self._get_next_entry)
            vol_new['system'] = sys_name
            created_id = self._request_and_assert(
                'create', '{}:a'.format(login), vol_new)

            # clean up
            self.db.session.query(self.RESOURCE_MODEL).filter_by(
                id=created_id).delete()
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
        # create disk without system, user has no permission to disk
        # note that restricted has no access to server
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
        # create disk with system, user has permission to system but not to
        # disk
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
                422: "No associated item found with value 'DSK8_x_0' for "
                     "field 'Storage server'"
            }
            self._assert_failed_req(
                resp, http_code,
                expected_response[http_code]
            )
            # try without specifying project
            data['project'] = None
            expected_response = {
                403: 'No CREATE permission found for the user in any project',
                422: "No associated item found with value 'DSK8_x_0' for "
                     "field 'Storage server'"
            }
            resp = self._do_request('create', '{}:a'.format(login), data)
            self._assert_failed_req(
                resp, http_code,
                expected_response[http_code]
            )

        # create disk with system, user has permission to disk but not to
        # system
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
                422: "No associated item found with value 'DSK8_x_0' for "
                     "field 'Storage server'"
            }
            self._assert_failed_req(resp, http_code,
                                    expected_response[http_code])
            # try without specifying project
            data['project'] = None
            self._assert_failed_req(resp, http_code,
                                    expected_response[http_code])

        self.db.session.delete(system)
    # test_add_all_fields_no_role()

    def test_add_update_allowed_chars(self):
        """
        Test adding and updating a volume using valid characters as volume_id
        """
        user_pass = '{}:a'.format('user_hw_admin@domain.com')

        vol_new = next(self._get_next_entry)
        # current allowed characters are numbers, lowercase letters, and
        # special chars '.', '-', '_'
        vol_new['volume_id'] = '0.0-0_3dda'
        created_id = self._request_and_assert(
            'create', '{}:a'.format('user_hw_admin@domain.com'), vol_new)
        update_fields = {
            'id': created_id,
            'volume_id': '1-0.a_3a33'
        }
        self._request_and_assert(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)

        # cleanup
        self._request_and_assert('delete', user_pass, created_id)
    # test_add_update_allowed_chars()

    def test_add_update_assoc_error(self):
        """
        Try creation and edit while setting a FK field to a value that has no
        entry in the associated table.
        """
        wrong_fields = [
            ('project', 'some_project'),
            ('owner', 'some_owner'),
            ('server', 'some_server'),
            ('system', 'some_system'),
        ]
        self._test_add_update_assoc_error(
            'user_hw_admin@domain.com', wrong_fields)
    # test_add_update_assoc_error()

    def test_add_update_hpav(self):
        """
        Test creation and update of HPAV aliases
        """
        user = 'user_hw_admin@domain.com'
        vol_new = next(self._get_next_entry)
        vol_new['volume_id'] = '1234'
        vol_new['type'] = 'HPAV'
        vol_new['size'] = 0
        fcp_spec = vol_new['specs']
        vol_new['specs'] = {}

        invalid_combos = [
            {'field': 'specs', 'value': fcp_spec,
             'msg': 'HPAV type cannot have specs'},
            {'field': 'size', 'value': 1,
             'msg': 'HPAV type must have size 0'},
            {'field': 'part_table', 'value': {'type': 'msdos', 'table': []},
             'msg': 'HPAV type cannot have partition table'},
            {'field': 'system_attributes', 'value': {'libvirt': 'xxxx'},
             'msg': 'HPAV type cannot have system_attributes'},
            {'field': 'volume_id', 'value': 'zzzzz',
             'msg': 'HPAV alias zzzzz is not in valid format'}
        ]
        # test create actions
        for combo in invalid_combos:
            orig_value = deepcopy(vol_new[combo['field']])
            vol_new[combo['field']] = combo['value']
            resp = self._do_request('create', '{}:a'.format(user), vol_new)
            self._assert_failed_req(resp, 400, combo['msg'])
            vol_new[combo['field']] = orig_value

        vol_new['part_table'] = None
        vol_new['size'] = 0
        vol_new['specs'] = {}
        vol_id = self._request_and_assert(
            'create', '{}:a'.format(user), vol_new)

        # test update actions
        for combo in invalid_combos:
            update_fields = {
                'id': vol_id, combo['field']: combo['value']}
            resp = self._do_request(
                'update', '{}:a'.format(user), update_fields)
            self._assert_failed_req(resp, 400, combo['msg'])

        # update with valid content
        update_fields = {'id': vol_id, 'volume_id': '9999'}
        self._request_and_assert('update', '{}:a'.format(user), update_fields)
    # test_add_update_hpav()

    def test_add_mandatory_fields(self):
        """
        Exercise the scenario where a user with permissions creates an item
        by specifying only the mandatory fields.
        """
        # the fields to be omitted and their expected values on response
        pop_fields = [
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

    def test_add_same_volid_other_server(self):
        """
        Test adding a volume with a volume_id of an existing volume but in a
        different storage server.
        """
        user_pass = '{}:a'.format('user_hw_admin@domain.com')
        # first, create an existing entry with same vol id but different
        # storage server
        alternate_server = models.StorageServer(
            name='DSK8_2x_0',
            type='DASD-FCP',
            model='DS8K',
            owner='user_hw_admin@domain.com',
            modifier='user_hw_admin@domain.com',
            project=self._db_entries['Project'][0]['name'],
        )
        self.db.session.add(alternate_server)
        self.db.session.commit()
        vol_existing = next(self._get_next_entry)
        vol_existing['server'] = alternate_server.name
        vol_existing['id'] = self._request_and_assert(
            'create', user_pass, vol_existing)

        # finally, create the vol with same id on the original server
        # and confirm that it works
        vol_new = next(self._get_next_entry)
        vol_new['volume_id'] = vol_existing['volume_id']
        self._request_and_assert(
            'create', '{}:a'.format('user_hw_admin@domain.com'), vol_new)

        # cleanup
        self._request_and_assert('delete', user_pass, vol_existing['id'])
        self.db.session.delete(alternate_server)
        self.db.session.commit()
    # test_add_same_volid_other_server()

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
            ('volume_id', 'WRONG_UPPERCASE_ID'),
            ('volume_id', 'a/111'),
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
            ('specs', None),
            # although type field is a fk (and would be a 422 association
            # error) it actually returns 400 because it tries to match with the
            # storage server type
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
            ('system', False),
            ('system', {'invalid': 'something'}),
            ('system_profiles', 'something'),
            ('system_attributes', {'invalid': 'something'}),
            ('system_attributes', "invalid_something"),
            ('system_attributes', None),
        ]
        self._test_add_update_wrong_field(
            'user_hw_admin@domain.com', wrong_data)

        # test special cases when volume type does not match storage server
        # exercise a failed creation due to mismatched types
        data = next(self._get_next_entry)
        orig_server_type = models.StorageServer.query.filter_by(
            name=data['server']).one().type
        data['type'] = 'ISCSI'

        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        self._assert_failed_req(
            resp, 400, MSG_INVALID_TYPE.format(data['type'], orig_server_type))

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
        self._assert_failed_req(
            resp, 400,
            MSG_INVALID_TYPE.format(update_fields['type'], orig_server_type))

        # 2- update type and server
        update_fields['type'] = 'FCP'
        update_fields['server'] = 'iSCSI Server'
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        self._assert_failed_req(
            resp, 400,
            MSG_INVALID_TYPE.format(update_fields['type'], iscsi_server_type))

        # 3- only update the server
        update_fields.pop('type')
        update_fields['server'] = 'iSCSI Server'
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        self._assert_failed_req(
            resp, 400,
            MSG_INVALID_TYPE.format(item['type'], iscsi_server_type))

        # cleanup
        self.db.session.delete(iscsi_server)
        self.db.session.commit()
    # test_add_update_wrong_field()

    def test_add_update_wrong_ptable_dasd_primary(self):
        """
        Test the scenario where the partition table has four primary partitions
        on a dasd labeled disk
        """
        # prepare a new entry for creation
        data = next(self._get_next_entry)
        part_size = int(data['size'] / 4)
        data['type'] = 'DASD'
        data['volume_id'] = 'ffff'
        data['specs'] = {}
        data['part_table'] = {
            'type': 'dasd',
            'table': [
                {
                    'mp': '/',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/home',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/var',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/tmp',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
            ]
        }
        # perform create request and validate response
        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        self._assert_failed_req(resp, 400, MSG_PTABLE_DASD_PARTS)

        # try an update, prepare an existing entry
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]
        entry['part_table'] = data['part_table']
        # perform update request and validate response
        update_fields = {
            'id': entry['id'],
            'part_table': entry['part_table'],
            'type': 'DASD'
        }
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        self._assert_failed_req(resp, 400, MSG_PTABLE_DASD_PARTS)
    # test_add_update_wrong_ptable_dasd_primary()

    def test_add_update_wrong_ptable_msdos_primary(self):
        """
        Test the scenario where the partition table has five primary partitions
        on a msdos labeled disk.
        """
        # prepare a new entry for creation
        data = next(self._get_next_entry)
        part_size = int(data['size'] / 5)
        data['part_table'] = {
            'type': 'msdos',
            'table': [
                {
                    'mp': '/',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/home',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/var',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/tmp',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/boot',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
            ]
        }
        # perform create request and validate response
        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        self._assert_failed_req(resp, 400, MSG_PTABLE_MANY_PARTS)

        # try an update, prepare an existing entry
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]
        entry['part_table'] = data['part_table']
        # perform update request and validate response
        update_fields = {
            'id': entry['id'],
            'part_table': entry['part_table'],
        }
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        self._assert_failed_req(resp, 400, MSG_PTABLE_MANY_PARTS)
    # test_add_update_wrong_ptable_msdos_primary()

    def test_add_update_wrong_ptable_msdos_sparsed_logicals(self):
        """
        Test the scenario where the partition table has primary / logical /
        primary / logical on a msdos labeled disk (sparsed)
        """
        # prepare a new entry for creation
        data = next(self._get_next_entry)
        part_size = int(data['size'] / 4)
        data['part_table'] = {
            'type': 'msdos',
            'table': [
                {
                    'mp': '/boot',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'logical',
                    'mo': None
                },
                {
                    'mp': '/home',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'primary',
                    'mo': None
                },
                {
                    'mp': '/home/tmp',
                    'size': part_size,
                    'fs': 'ext4',
                    'type': 'logical',
                    'mo': None
                },
            ]
        }
        # perform create request and validate response
        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        self._assert_failed_req(resp, 400, MSG_PTABLE_BAD_PLACE)

        # try different combination with logical as first partition
        orig_ptable = data['part_table'].copy()
        data['part_table']['table'][0]['type'] = 'logical'
        data['part_table']['table'][1]['type'] = 'primary'
        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        self._assert_failed_req(resp, 400, MSG_PTABLE_BAD_PLACE)

        # try updates, prepare an existing entry
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]
        # first variant, primary as first partition
        entry['part_table'] = orig_ptable

        # perform update request and validate response
        update_fields = {
            'id': entry['id'],
            'part_table': entry['part_table'],
        }
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        self._assert_failed_req(resp, 400, MSG_PTABLE_BAD_PLACE)

        # second variant, logical as first partition
        entry['part_table'] = data['part_table']
        # perform update request and validate response
        update_fields = {
            'id': entry['id'],
            'part_table': entry['part_table'],
        }
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields)
        self._assert_failed_req(resp, 400, MSG_PTABLE_BAD_PLACE)
    # test_add_update_wrong_ptable_msdos_sparsed_logicals()

    def test_update_wrong_parttable_for_volume(self):
        """
        Test the Scenario where you apply a DASD ptable to an FCP type Volume
        """
        # prepare some Data
        data = next(self._get_next_entry)
        data['part_table'] = {
            'type': 'dasd',
            'table': [
                {
                    'mp': '/',
                    'size': int(data['size']),
                    'fs':'ext4',
                    'type':'primary',
                    'mo': None
                }
            ],
        }
        # perform create request and check if it returns an exception
        resp = self._do_request(
            'create', '{}:a'.format('user_hw_admin@domain.com'), data)
        self._assert_failed_req(resp, 400, MSG_INVALID_PTABLE)
        # prepare an existing entry
        entry = self._create_many_entries(
            'user_hw_admin@domain.com', 1)[0][0]
        entry['part_table'] = data['part_table']
        # prepare data for update requests
        update_fields = {
            'id': entry['id'],
            'part_table': entry['part_table'],
        }
        # perform update request and check if it returns an exception
        resp = self._do_request(
            'update', '{}:a'.format('user_hw_admin@domain.com'), update_fields
        )
        self._assert_failed_req(resp, 400, MSG_INVALID_PTABLE)
    # test_update_wrong_parttable_for_volume()

    def test_add_update_wrong_ptable_size(self):
        """
        Test the scenario where the partitions in the ptable exceed the size of
        the volume
        """
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
        self._assert_failed_req(
            resp, 400,
            MSG_PTABLE_SIZE_MISMATCH.format(parts_size, data['size']))

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
        self._assert_failed_req(
            resp, 400,
            MSG_PTABLE_SIZE_MISMATCH.format(parts_size, entry['size']))
    # test_add_update_wrong_ptable_size()

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

        # disks without system, restricted user without role on project
        self._test_list_and_read_restricted_no_role(
            'user_hw_admin@domain.com', user_res, http_code=404)

        # list/read disks with system, restricted user has no role in system's
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

        # list/read disks with system, restricted user has role in system's
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
            'modifier': 'user_project_admin@domain.com',
        }
        self._test_list_filtered('user_hw_admin@domain.com', filter_values)

        self.db.session.delete(storage_server)
        self.db.session.delete(system)
        self.db.session.delete(pool)
        self.db.session.commit()
    # test_list_filtered()

    def test_update_project(self):
        """
        Exercise the update of the item's project. For that operation a user
        requires permission on both projects.
        """
        self._test_update_project()
    # test_update_project()

    def test_update_has_role(self):
        """
        Exercise different update scenarios
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
        prof_obj = models.SystemProfile(
            name='profile for test_update_has_role',
            system=sys_name,
            default=True,
        )
        self.db.session.add(prof_obj)
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
        prof_id = prof_obj.id

        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]
        for login in logins:
            data = next(self._get_next_entry)
            data['owner'] = login
            vol_id = self._request_and_assert(
                'create', '{}:a'.format('user_hw_admin@domain.com'), data)

            # update disk assign system, user has permission to both disk and
            # system
            # exercise case where user is system owner
            if login in ('user_restricted@domain.com', 'user_user@domain.com'):
                sys_obj.owner = login
            # exercise case where user has permission through a role
            else:
                sys_obj.owner = 'admin'
            sys_obj.project = self._db_entries['Project'][0]['name']
            self.db.session.add(sys_obj)
            self.db.session.commit()
            # perform request
            data = {'id': vol_id, 'system': sys_name}
            self._request_and_assert('update', '{}:a'.format(login), data)
            self.assertEqual(
                self.RESOURCE_MODEL.query.filter_by(id=vol_id).one().system,
                sys_name, 'System was not assigned to disk')

            # update disk re-assign to same system, profile associations are
            # preserved
            # associate to a profile
            assoc_obj = models.StorageVolumeProfileAssociation(
                profile_id=prof_id, volume_id=vol_id)
            self.db.session.add(assoc_obj)
            self.db.session.commit()
            # perform request
            data = {'id': vol_id, 'system': sys_name}
            self._request_and_assert('update', '{}:a'.format(login), data)
            self.assertEqual(
                self.RESOURCE_MODEL.query.filter_by(id=vol_id).one().system,
                sys_name, 'System was withdrawn from disk')
            # validate that profile association was preserved
            self.assertEqual(
                len(models.StorageVolumeProfileAssociation.query.filter_by(
                    profile_id=prof_id, volume_id=vol_id).all()),
                1, 'Association was not preserved'
            )

            # update disk withdraw system, user has permission to disk and
            # system
            data = {'id': vol_id, 'system': None}
            self._request_and_assert('update', '{}:a'.format(login), data)
            self.assertEqual(
                self.RESOURCE_MODEL.query.filter_by(id=vol_id).one().system,
                None, 'System was not withdrawn')
            # validate that profile association was removed
            self.assertEqual(
                models.StorageVolumeProfileAssociation.query.filter_by(
                    profile_id=prof_id, volume_id=vol_id).one_or_none(),
                None, 'Association was not removed'
            )

            # update disk allowed attributes, user has permission to system but
            # not to disk (derived permission)
            # first, prepare the disk's permissions
            data = {'id': vol_id, 'system': sys_name, 'owner': 'admin',
                    'project': self._db_entries['Project'][1]['name']}
            self._request_and_assert('update', 'admin:a', data)
            # perform request
            data = {'id': vol_id, 'part_table': None, 'system_attributes': {}}
            if login in ('user_admin@domain.com',):
                data.update({'size': 10000, 'specs': {}})
            self._request_and_assert('update', '{}:a'.format(login), data)

            # other fields should not be updatable through derived permissions
            if login not in ('user_admin@domain.com',):
                data = {'id': vol_id, 'size': 10000}
                resp = self._do_request('update', '{}:a'.format(login), data)
                self._assert_failed_req(resp, 403)
                data = {'id': vol_id, 'specs': {}}
                resp = self._do_request('update', '{}:a'.format(login), data)
                self._assert_failed_req(resp, 403)

            # update disk (no system update), user has permission to disk but
            # not to system
            # first, prepare the disk's permissions
            data = {'id': vol_id,
                    'project': self._db_entries['Project'][0]['name']}
            # exercise case where user has permission through a role
            if login in ('user_hw_admin@domain.com', 'user_admin@domain.com'):
                data['owner'] = 'admin'
            # exercise case where user is disk owner
            else:
                data['owner'] = login
            self._request_and_assert('update', 'admin:a', data)
            # prepare system's permissions
            sys_obj.owner = 'admin'
            sys_obj.project = self._db_entries['Project'][1]['name']
            self.db.session.add(sys_obj)
            self.db.session.commit()
            # perform request
            data = {'id': vol_id, 'size': 10000, 'part_table': None,
                    'specs': {}, 'system_attributes': {}}
            self._request_and_assert('update', '{}:a'.format(login), data)

            # update disk re-assign system, user has permission to all
            # prepare disk's permissions
            if login not in ('user_hw_admin@domain.com',
                             'user_admin@domain.com'):
                data = {'id': vol_id, 'owner': login}
            # exercise case where user has permission through a role
            else:
                data = {'id': vol_id, 'owner': 'admin'}
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
            data = {'id': vol_id, 'system': sys_name_2}
            self._request_and_assert('update', '{}:a'.format(login), data)
            self.assertEqual(
                self.RESOURCE_MODEL.query.filter_by(id=vol_id).one().system,
                sys_name_2, 'System was not assigned to disk')

            # clean up
            self.RESOURCE_MODEL.query.filter_by(id=vol_id).delete()
            self.db.session.commit()

        # clean up
        self.db.session.delete(prof_obj)
        self.db.session.delete(sys_obj)
        self.db.session.delete(sys_obj_2)
        self.db.session.commit()
    # test_update_has_role()

    def test_update_no_role(self):
        """
        Try to update a volume without an appropriate role to do so.
        """
        hw_admin = 'user_hw_admin@domain.com'
        update_fields = {
            'owner': 'user_user@domain.com',
            'desc': 'some_desc',
            'volume_id': '1500',
            'type': 'DASD',
            'part_table': {'type': 'msdos', 'table': []},
            'specs': {},
            'size': 5000,
            'server': 'storage_server',
        }
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com'
        ]
        # update disk without system, user has no permission to disk
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

        def assert_update(error_msg, update_user, disk_owner, sys_cur,
                          sys_target, http_code=403):
            """
            Helper function to validate update action is forbidden

            Args:
                update_user (str): login performing the update action
                disk_owner (str): set this login as owner of the volume
                sys_cur (str): name and owner of the current system
                sys_target (str): name and owner of target system
                error_msg (str): expected error message
                http_code (int): expected HTTP status code
            """
            data = next(self._get_next_entry)
            data['owner'] = disk_owner
            if sys_cur:
                data['system'] = sys_cur['name']
                sys_obj = models.System.query.filter_by(
                    name=sys_cur['name']).one_or_none()
                if sys_obj is None:
                    return
                sys_obj.owner = sys_cur['owner']
                self.db.session.add(sys_obj)
                self.db.session.commit()
            vol_id = self._request_and_assert('create', 'admin:a', data)

            if sys_target:
                sys_obj = models.System.query.filter_by(
                    name=sys_target['name']).one()
                sys_obj.owner = sys_target['owner']
                self.db.session.add(sys_obj)
                self.db.session.commit()
                sys_tgt_name = sys_target['name']
            else:
                sys_tgt_name = None

            data = {'id': vol_id, 'system': sys_tgt_name}
            resp = self._do_request('update', '{}:a'.format(update_user), data)
            # validate the response received, should be forbidden
            self._assert_failed_req(resp, http_code, error_msg)
            # clean up
            self.db.session.query(self.RESOURCE_MODEL).filter_by(
                id=vol_id).delete()
        # assert_update()

        for login in logins:
            # update disk assign system, user has permission to system but
            # not to disk
            msg = 'User has no UPDATE permission for the specified volume'
            assert_update(msg, login, hw_admin,
                          None, {'name': sys_name, 'owner': login})

            # update disk withdraw system, user has permission to system but
            # not to disk
            assert_update(msg, login, hw_admin,
                          {'name': sys_name, 'owner': login}, None)

            # update disk re-assign system, user has permission to disk and
            # target system but not to current system
            msg = ('User has no UPDATE permission for the system '
                   'currently holding the volume')
            assert_update(msg, login, login,
                          {'name': sys_name_2, 'owner': 'admin'},
                          {'name': sys_name, 'owner': login})

            # update disk re-assign system, user has permission to disk and
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
            # update disk assign system, user has permission to disk but not
            # to system
            msg = 'User has no UPDATE permission for the specified system'
            assert_update(msg, login, login,
                          None, {'name': sys_name, 'owner': hw_admin})

            # update disk assign system, user has no permission to disk nor
            # system
            msg = 'User has no UPDATE permission for the specified volume'
            assert_update(msg, login, hw_admin,
                          None, {'name': sys_name, 'owner': hw_admin})

            # update disk withdraw system, user has permission to disk but
            # not to assigned system
            msg = ('User has no UPDATE permission for the system currently '
                   'holding the volume')
            assert_update(msg, login, login,
                          {'name': sys_name, 'owner': hw_admin}, None)

            # update disk withdraw system, user has no permission to disk nor
            # system
            msg = 'User has no UPDATE permission for the specified volume'
            assert_update(msg, login, hw_admin,
                          {'name': sys_name, 'owner': hw_admin}, None)

        # clean up
        self.db.session.delete(sys_obj)
        self.db.session.delete(sys_obj_2)
        self.db.session.commit()
    # test_update_no_role()

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

        # fields 'project' and 'system' are tested separately due to special
        # permission handling
        update_fields = {
            'owner': 'user_user@domain.com',
            'desc': 'some_desc',
            'volume_id': '1500',
            'type': 'DASD',
            'part_table': {'type': 'msdos', 'table': []},
            'specs': {},
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

        # clean up
        self.db.session.delete(system)
        self.db.session.delete(storage_server)
        self.db.session.delete(pool)
        self.db.session.commit()
    # test_update_valid_fields()
# TestStorageVolume
