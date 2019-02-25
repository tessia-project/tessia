# Copyright 2019 IBM Corp.
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
Unit test for bulkop resource_svol module
"""

#
# IMPORTS
#
from copy import deepcopy
from tessia.server.db import models
from tessia.server.state_machines import base
from tessia.server.state_machines.bulkop import resource_svol
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest.mock import patch
from unittest.mock import Mock

import json
import os

#
# CONSTANTS AND DEFINITIONS
#
SVOL_HEADERS = (
    [field.lower() for field in resource_svol.FIELDS_CSV
     if field.lower() not in ['fcp_paths', 'wwid']])

#
# CODE
#

class TestResourceStorageVolume(TestCase):
    """
    Unit test for the resource_svol module of the bulkop state machine.
    """

    @classmethod
    def init_db(cls):
        """
        Create a db from scratch
        """
        cls.db.create_db()
        sample_file = '{}/data.json'.format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(sample_file, 'r') as sample_fd:
            data = sample_fd.read()
        cls.db.create_entry(json.loads(data))
    # init_db()

    @classmethod
    def setUpClass(cls):
        """
        Called once to create the db content for this test.
        """
        cls.db = DbUnit
        cls.init_db()
    # setUpClass()

    def _check_add(self, login, entry):
        """
        Auxiliar method to check results of add
        """
        # check results
        svol_obj = self._get_svol(
            server=entry['server'], volume_id=entry['volume_id'])

        # check volume values
        for field in SVOL_HEADERS:
            # validate volume id conversion to lowercase
            if field == 'volume_id':
                entry_value = entry[field].lower()
            else:
                entry_value = entry[field]
            self.assertEqual(
                entry_value, getattr(svol_obj, field),
                'Comparison of field "{}" failed for login "{}"'
                .format(field, login))
        # check fcp path and wwid
        if svol_obj.type == 'FCP':
            specs = {
                'multipath': True,
                'wwid': entry['wwid'],
                'adapters': [
                    {'devno': '0.0.2100',
                     'wwpns': sorted(
                         ['10050163055341ae', '10050163055041ae'])},
                    {'devno': '0.0.2180',
                     'wwpns': sorted(
                         ['10050163055341ae', '10050163055041ae'])},
                ],
            }
            svol_specs = deepcopy(svol_obj.specs)
            for adapter in svol_specs['adapters']:
                adapter['wwpns'].sort()
            self.assertEqual(svol_specs, specs)
        else:
            self.assertEqual(svol_obj.specs, {})

        # check rollback to original values
        self.db.session.rollback()
        self.assertEqual(
            models.StorageVolume.query.join(
                'server_rel'
            ).filter(
                models.StorageServer.name == entry['server'],
                models.StorageVolume.volume_id == entry['volume_id']
            ).one_or_none(),
            None)
    # _check_add()

    def _check_update(self, login, orig_dict, entry):
        """
        Auxiliar method to check results of update
        """
        # check results
        svol_obj = self._get_svol(
            server=entry['server'], volume_id=entry['volume_id'])
        # IMPORTANT: refresh allows the relationships which were changed by
        # the operation to be loaded with the new values
        self.db.session.refresh(svol_obj)

        # check volume values
        for field in SVOL_HEADERS:
            # normalize empty to None
            if field == 'desc' and not entry[field]:
                entry_value = None
            # validate volume id conversion to lowercase
            elif field == 'volume_id':
                entry_value = entry[field].lower()
            else:
                entry_value = entry[field]
            self.assertEqual(
                entry_value, getattr(svol_obj, field),
                'Comparison of field "{}" failed for login "{}"'
                .format(field, login))
        # check fcp path and wwid
        if svol_obj.type == 'FCP':
            specs = {
                'multipath': True,
                'wwid': entry['wwid'],
                'adapters': [
                    {'devno': '0.0.2100',
                     'wwpns': sorted(
                         ['10050163055341ae', '10050163055041ae'])},
                    {'devno': '0.0.2180',
                     'wwpns': sorted(
                         ['10050163055341ae', '10050163055041ae'])},
                ],
            }
            svol_specs = deepcopy(svol_obj.specs)
            for adapter in svol_specs['adapters']:
                adapter['wwpns'].sort()
            self.assertEqual(svol_specs, specs)
        else:
            self.assertEqual(svol_obj.specs, {})
        # system assignment changed: check volume profile associations
        if orig_dict['system'] and entry['system']:
            assoc_obj = models.StorageVolumeProfileAssociation.query.filter_by(
                volume_id=svol_obj.id).first()
            # re-assign to same system: check that profile associations were
            # preserved
            if orig_dict['system'] == entry['system']:
                self.assertIsNotNone(assoc_obj)
            # system changed: check that iface associations were removed
            else:
                self.assertIsNone(assoc_obj)

        # check rollback to original values
        self.db.session.rollback()
        svol_obj = self._get_svol(
            server=entry['server'], volume_id=entry['volume_id'])
        for field in SVOL_HEADERS:
            self.assertEqual(
                orig_dict[field], getattr(svol_obj, field),
                'Comparison of field "{}" failed for login "{}"'
                .format(field, login))
        self.assertEqual(orig_dict['specs'], svol_obj.specs)
    # _check_update()

    def _get_orig_values(self, ref_entry):
        """
        Given a db object return a dict containing the original values for
        later comparison
        """
        # fetch volume's original values for later comparison
        svol_obj = self._get_svol(
            server=ref_entry['server'], volume_id=ref_entry['volume_id'])
        svol_orig = dict(
            [(field, getattr(svol_obj, field)) for field in SVOL_HEADERS])
        svol_orig['specs'] = svol_obj.specs

        return svol_orig
    # _get_orig_values()

    @staticmethod
    def _get_svol(server, volume_id):
        return models.StorageVolume.query.join(
            'server_rel'
        ).filter(
            models.StorageServer.name == server,
            models.StorageVolume.volume_id == volume_id.lower()
        ).one()
    # _get_svol()

    def setUp(self):
        """
        Prepare the necessary mocks at the beginning of each testcase.
        """
        # mock config object
        patcher = patch.object(base, 'CONF', autospec=True)
        self._mock_conf = patcher.start()
        self.addCleanup(patcher.stop)

        # mock sys object
        patcher = patch.object(base, 'sys', autospec=True)
        self._mock_sys = patcher.start()
        self._mock_sys_tblimit = 10
        self._mock_sys.tracebacklimit = self._mock_sys_tblimit
        self.addCleanup(patcher.stop)

        patcher = patch.object(resource_svol, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)
        mock_logging.getLogger.return_value = Mock(
            spec=['warning', 'error', 'debug', 'info'])
        self._mock_logger = mock_logging.getLogger.return_value
    # setUp()

    def tearDown(self):
        """
        Try to avoid affecting next testcase by rolling back pending db
        transactions
        """
        self.db.session.rollback()
    # tearDown()

    def test_add_many_roles(self):
        """
        Test different scenarios of adding storage volumes
        """
        ref_entry_dasd = {
            'server': 'ds8k16',
            # use uppercase letters to test conversion to lowercase
            'volume_id': '99FF',
            'type': 'DASD',
            'size': 21100,
            'system': '',
            'fcp_paths': '',
            'wwid': '',
            'owner': 'user_hw_admin@domain.com',
            'project': 'bulkop project',
            'desc': 'Some description',
        }
        ref_entry_scsi = {
            'server': 'ds8k16',
            'volume_id': '1020400000000000',
            'type': 'FCP',
            'size': 15000,
            'system': '',
            'fcp_paths': ('2100(10050163055341ae,10050163055041ae) '
                          '2180(10050163055341ae,10050163055041ae)'),
            'wwid': '11002016305bbc1b0000000000002000',
            'owner': 'user_hw_admin@domain.com',
            'project': 'bulkop project',
            'desc': 'Some description',
        }

        def assert_action(ref_entry, login, sys_name=None, sys_owner=None,
                          error_msg=None):
            """
            Helper function to validate action
            """
            orig_sys_owner = None
            if sys_name and sys_owner:
                sys_obj = models.System.query.filter_by(name=sys_name).one()
                orig_sys_owner = sys_obj.owner
                sys_obj.owner = sys_owner
                self.db.session.add(sys_obj)
                self.db.session.commit()

            # perform action
            entry = deepcopy(ref_entry)
            if sys_name:
                entry['system'] = sys_name
            user_obj = models.User.query.filter_by(login=login).one()
            res_obj = resource_svol.ResourceHandlerStorageVolume(user_obj)
            # error message specified: check that error occurs
            if error_msg:
                with self.assertRaisesRegex(PermissionError, error_msg):
                    res_obj.render_item(entry)
                self.db.session.rollback()
            else:
                res_obj.render_item(entry)
                # validate
                self._check_add(login, entry)

            # restore system owner
            if orig_sys_owner:
                sys_obj = models.System.query.filter_by(name=sys_name).one()
                sys_obj.owner = orig_sys_owner
                self.db.session.add(sys_obj)
                self.db.session.commit()
        # assert_action()

        logins = [
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]
        for login in logins:
            # create disk without system
            assert_action(ref_entry_dasd, login)

            # create disk with system
            assert_action(ref_entry_scsi, login, 'cpc3lp52')

        # start section: no role scenarios

        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
        ]
        for login in logins:
            # create disk without system, user has no permission to disk
            msg = 'User has no CREATE permission for the specified project'
            assert_action(ref_entry_dasd, login, error_msg=msg)

            # exercise case where user has permission via ownership
            if login in ('user_restricted@domain.com', 'user_user@domain.com'):
                sys_owner = login
            # exercise case where user has permission via role
            else:
                sys_owner = 'admin'
            # create disk with system, user has permission to system but not to
            # disk
            assert_action(ref_entry_dasd, login, 'cpc3lp52', sys_owner,
                          error_msg=msg)
        logins = [
            'user_hw_admin@domain.com',
        ]
        for login in logins:
            # create disk with system, user has permission to ip but not to
            # system
            msg = 'User has no UPDATE permission for the specified system'
            assert_action(ref_entry_dasd, login, 'cpc3', sys_owner,
                          error_msg=msg)
    # test_add_many_roles()

    def test_invalid_values(self):
        """
        Test general invalid values
        """
        ref_entry = {
            'server': 'ds8k16',
            'volume_id': '1022400000000000',
            'type': 'FCP',
            'size': 15000,
            'system': '',
            'fcp_paths': ('2100(10050163055341ae,10050163055041ae) '
                          '2180(10050163055341ae,10050163055041ae)'),
            'wwid': '11002016305bbc1b0000000000002000',
            'owner': 'user_hw_admin@domain.com',
            'project': 'bulkop project',
            'desc': 'Some description',
        }

        combos = [
            ('FCP paths in invalid format', {'fcp_paths': '2100(1111 2222)'}),
            ('FCP paths invalid: devno 0.0.2100 appears twice',
             {'fcp_paths': '2100(1111) 2100(2222)'}),
            ('System wrong_system not found',
             {'system': 'wrong_system'}),
            ('Storage server wrong_server not found',
             {'server': 'wrong_server'}),
            ('Tried to change volume type from FCP to wrong_type',
             {'type': 'wrong_type'}),
            ('Specified type wrong_type does not match storage server',
             {'volume_id': 'new_volume', 'type': 'wrong_type'}),
            ('Specified project wrong_project not found',
             {'volume_id': 'new_volume', 'project': 'wrong_project'}),
        ]

        user_obj = models.User.query.filter_by(
            login='user_hw_admin@domain.com').one()
        res_obj = resource_svol.ResourceHandlerStorageVolume(user_obj)
        for msg, values in combos:
            entry = deepcopy(ref_entry)
            entry.update(values)
            with self.assertRaisesRegex(ValueError, msg):
                res_obj.render_item(entry)
    # test_invalid_values()

    def test_update_change_project(self):
        """
        Test the case when the volume project is changed
        """
        # use dasd to test update of dasd type
        ref_entry = {
            'server': 'ds8k16',
            # use uppercase letters to test conversion to lowercase
            'volume_id': '39FF',
            'type': 'DASD',
            'size': 21100,
            'system': '',
            'fcp_paths': '',
            'wwid': '',
            'owner': 'user_hw_admin@domain.com',
            'project': 'bulkop project 2',
            # also test empty description
            'desc': '',
        }
        logins = [
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]
        for login in logins:
            user_obj = models.User.query.filter_by(login=login).one()

            svol_obj = self._get_svol(
                server=ref_entry['server'], volume_id=ref_entry['volume_id'])
            svol_orig_owner = svol_obj.owner
            svol_orig_system = svol_obj.system
            svol_obj.system = None
            # exercise case where user is disk owner
            if login not in ('user_hw_admin@domain.com',
                             'user_admin@domain.com'):
                svol_obj.owner = login
            # exercise case where user has disk permission through a role
            else:
                svol_obj.owner = 'admin'
            self.db.session.add(svol_obj)

            # give user a role to update disk on the new project
            role_obj = models.UserRole(
                project=ref_entry['project'],
                user=user_obj.login,
                role="ADMIN_LAB"
            )
            self.db.session.add(role_obj)
            self.db.session.commit()
            role_id = role_obj.id

            # perform action
            orig_dict = self._get_orig_values(ref_entry)
            res_obj = resource_svol.ResourceHandlerStorageVolume(user_obj)
            res_obj.render_item(ref_entry)

            # check results
            self._check_update(login, orig_dict, ref_entry)

            # try again without roles
            role_obj = models.UserRole.query.filter_by(id=role_id).one()
            self.db.session.delete(role_obj)
            self.db.session.commit()

            # admin can update the project
            if login == 'user_admin@domain.com':
                res_obj.render_item(ref_entry)
                self._check_update(login, orig_dict, ref_entry)
            # other users should fail
            else:
                with self.assertRaisesRegex(
                    PermissionError, 'User has no UPDATE permission'):
                    res_obj.render_item(ref_entry)
                self.db.session.rollback()

            # restore original disk owner
            svol_obj = self._get_svol(
                server=ref_entry['server'], volume_id=ref_entry['volume_id'])
            svol_obj.owner = svol_orig_owner
            svol_obj.system = svol_orig_system
            self.db.session.add(svol_obj)
            self.db.session.commit()
    # test_update_change_project()

    def test_update_many_roles(self):
        """
        Test different scenarios of updating a storage volume
        """
        ref_entry = {
            'server': 'ds8k16',
            'volume_id': '1022400000000000',
            'type': 'FCP',
            'size': 15000,
            'system': '',
            'fcp_paths': ('2100(10050163055341ae,10050163055041ae) '
                          '2180(10050163055341ae,10050163055041ae)'),
            'wwid': '11002016305bbc1b0000000000002000',
            'owner': 'user_hw_admin@domain.com',
            'project': 'bulkop project',
            'desc': 'Some description',
        }

        def assert_update(update_user, disk_owner, sys_cur, sys_target,
                          error_msg=None):
            """
            Helper function to validate update action

            Args:
                update_user (str): login performing the update action
                disk_owner (str): owner of disk
                sys_cur (str): name and owner of the current system
                sys_target (str): name and owner of target system
                error_msg (str): should wait for error when specified
            """
            svol_obj = self._get_svol(
                server=ref_entry['server'], volume_id=ref_entry['volume_id'])
            svol_orig_owner = svol_obj.owner
            svol_obj.owner = disk_owner
            self.db.session.add(svol_obj)

            # system values before changes made by the method
            sys_orig_owners = {}
            if sys_cur:
                sys_obj = models.System.query.filter_by(
                    name=sys_cur['name']).one()
                sys_orig_owners['cur'] = sys_obj.owner
                sys_obj.owner = sys_cur['owner']
                # assign disk to system
                svol_obj.system = sys_cur['name']
            else:
                svol_obj.system = None
            self.db.session.add(svol_obj)
            if sys_target:
                sys_obj = models.System.query.filter_by(
                    name=sys_target['name']).one()
                sys_orig_owners['target'] = sys_obj.owner
                sys_obj.owner = sys_target['owner']
                self.db.session.add(sys_obj)
            self.db.session.commit()

            # perform action
            entry = deepcopy(ref_entry)
            if sys_target:
                entry['system'] = sys_target['name']
            orig_dict = self._get_orig_values(entry)
            user_obj = models.User.query.filter_by(login=update_user).one()
            res_obj = resource_svol.ResourceHandlerStorageVolume(user_obj)
            # error message specified: check that error occurs
            if error_msg:
                with self.assertRaisesRegex(PermissionError, error_msg):
                    res_obj.render_item(entry)
                self.db.session.rollback()
            else:
                res_obj.render_item(entry)
                # validate
                self._check_update(update_user, orig_dict, entry)

            # restore cur system owner
            if sys_orig_owners.get('cur'):
                sys_obj = models.System.query.filter_by(
                    name=sys_cur['name']).one()
                sys_obj.owner = sys_orig_owners['cur']
                self.db.session.add(sys_obj)
            # restore target system owner
            if sys_orig_owners.get('target'):
                sys_obj = models.System.query.filter_by(
                    name=sys_target['name']).one()
                sys_obj.owner = sys_orig_owners['target']
                self.db.session.add(sys_obj)
            # restore disk owner
            svol_obj = self._get_svol(
                server=ref_entry['server'], volume_id=ref_entry['volume_id'])
            svol_obj.owner = svol_orig_owner
            self.db.session.add(svol_obj)
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
            # exercise case where user has disk permission through a role
            if login in ('user_hw_admin@domain.com', 'user_admin@domain.com'):
                disk_owner = 'admin'
            # exercise case where user is disk owner
            else:
                disk_owner = login

            # exercise case where user is system owner
            if login in ('user_restricted@domain.com', 'user_user@domain.com'):
                sys_owner = login
            # exercise case where user has system permission through a role
            else:
                sys_owner = 'admin'

            # update disk assign system, user has permission to both disk and
            # system
            assert_update(login, disk_owner, None,
                          {'owner': sys_owner, 'name': 'cpc3lp52'})

            # update disk re-assign to same system, profile associations are
            # preserved
            assert_update(login, disk_owner,
                          {'owner': sys_owner, 'name': 'cpc3lp52'},
                          {'owner': sys_owner, 'name': 'cpc3lp52'})

            # update disk withdraw system, user has permission to disk and
            # system
            assert_update(login, disk_owner,
                          {'owner': sys_owner, 'name': 'cpc3lp52'},
                          None)

            # update disk re-assign system, user has permission to all
            assert_update(login, disk_owner,
                          {'owner': sys_owner, 'name': 'cpc3lp52'},
                          {'owner': sys_owner, 'name': 'cpc3lp53'})


        # start section: no role scenarios

        # roles without update volume permission
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
        ]
        for login in logins:
            # update disk without system, user has no permission to disk
            msg = 'User has no UPDATE permission for the specified volume'
            assert_update(
                login, 'admin', None,
                None, error_msg=msg)

            # update disk assign system, user has permission to system but
            # not to disk
            assert_update(
                login, 'admin', None,
                {'owner': login, 'name': 'cpc3lp52'},
                error_msg=msg)

            # update disk withdraw system, user has permission to system but
            # not to disk
            assert_update(login, 'admin', {'owner': login, 'name': 'cpc3lp52'},
                          None, error_msg=msg)

            # update disk re-assign system, user has permission to disk and
            # target system but not to current system
            msg = ('User has no UPDATE permission for the system '
                   'currently holding the volume')
            assert_update(
                login, login, {'owner': 'admin', 'name': 'cpc3'},
                {'owner': login, 'name': 'cpc3lp53'}, error_msg=msg)

            # update disk re-assign system, user has permission to disk and
            # current system but not to target system
            msg = 'User has no UPDATE permission for the specified system'
            assert_update(
                login, login, {'owner': login, 'name': 'cpc3lp52'},
                {'owner': 'admin', 'name': 'cpc3'}, error_msg=msg)

        for login in ('user_restricted@domain.com', 'user_user@domain.com'):
            # update disk assign system, user has permission to disk but not
            # to system
            msg = 'User has no UPDATE permission for the specified system'
            assert_update(
                login, login, None,
                {'name': 'cpc3lp52', 'owner': 'admin'}, error_msg=msg)

            # update disk assign system, user has no permission to disk nor
            # system
            msg = 'User has no UPDATE permission for the specified volume'
            assert_update(
                login, 'admin', None,
                {'name': 'cpc3lp52', 'owner': 'admin'}, error_msg=msg)

            # update disk withdraw system, user has permission to disk but
            # not to assigned system
            msg = ('User has no UPDATE permission for the system currently '
                   'holding the volume')
            assert_update(
                login, login, {'name': 'cpc3lp52', 'owner': 'admin'},
                None, error_msg=msg)

            # update disk withdraw system, user has no permission to disk nor
            # system
            msg = 'User has no UPDATE permission for the specified volume'
            assert_update(
                login, 'admin', {'name': 'cpc3lp52', 'owner': 'admin'},
                None, error_msg=msg)

    # test_update_many_roles()

    def test_update_no_change(self):
        """
        Test the case when no changes are detected
        """
        # values below match data.json file
        ref_entry = {
            "desc": "Storage volume for tests",
            # add strange key on purpose to test sanitization by code
            "modifier": "admin",
            "owner": "admin",
            "project": "bulkop project",
            "server": "ds8k16",
            "size": 7000,
            "system": "cpc3lp52",
            "type": "DASD",
            # use uppercase letters to test conversion to lowercase
            "volume_id": "39FF",
            "fcp_paths": '',
            "wwid": '',
        }

        login = 'user_hw_admin@domain.com'
        # perform action
        orig_dict = self._get_orig_values(ref_entry)
        user_obj = models.User.query.filter_by(login=login).one()
        res_obj = resource_svol.ResourceHandlerStorageVolume(user_obj)
        res_obj.render_item(ref_entry)

        # check results
        self._check_update(login, orig_dict, ref_entry)

        self._mock_logger.info.assert_any_call(
            'skipping volume %s/%s (no changes)', ref_entry['server'],
            ref_entry['volume_id'].lower())

        # scsi disk
        ref_entry_scsi = {
            "desc": '',
            # add strange key on purpose to test sanitization by code
            "modifier": "admin",
            "owner": "admin",
            "project": "bulkop project",
            "server": "ds8k16",
            "size": 10000,
            "fcp_paths": (
                '1800(100207630503c1ae,100207630508c1ae,100207630510c1ae,'
                '100207630513c1ae) '
                '1840(100207630503c1ae,100207630508c1ae,100207630510c1ae,'
                '100207630513c1ae)'),
            "wwid": "11002076305aac1a0000000000002200",
            "system": "cpc3lp52",
            "type": "FCP",
            "volume_id": "1022400000000000",
        }

        res_obj = resource_svol.ResourceHandlerStorageVolume(user_obj)
        res_obj.render_item(ref_entry_scsi)

        # check results
        self._check_update(login, orig_dict, ref_entry)

        self._mock_logger.info.assert_any_call(
            'skipping volume %s/%s (no changes)', ref_entry['server'],
            ref_entry['volume_id'].lower())
    # test_update_no_change()

# TestResourceStorageVolume
