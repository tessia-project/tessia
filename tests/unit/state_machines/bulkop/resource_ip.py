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
Unit test for bulkop resource_ip module
"""

#
# IMPORTS
#
from copy import deepcopy
from tessia.server.db import models
from tessia.server.state_machines import base
from tessia.server.state_machines.bulkop import resource_ip
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest.mock import patch
from unittest.mock import Mock

import json
import os

#
# CONSTANTS AND DEFINITIONS
#
IP_HEADERS = [field.lower() for field in resource_ip.FIELDS_CSV]

#
# CODE
#


class TestResourceIpAddress(TestCase):
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
        cls._subnet_name = 'lab1-1801-cpc3'
    # setUpClass()

    def _check_add(self, login, entry):
        """
        Auxiliar method to check results of add
        """
        # check results
        ip_obj = self._get_ip(subnet=entry['subnet'], address=entry['address'])

        # check ip values
        for field in IP_HEADERS:
            self.assertEqual(
                entry[field], getattr(ip_obj, field),
                'Comparison of field "{}" failed for login "{}"'
                .format(field, login))

        # check rollback to original values
        self.db.session.rollback()
        self.assertEqual(
            models.IpAddress.query.join(
                'subnet_rel'
            ).filter(
                models.IpAddress.address == entry['address'],
                models.Subnet.name == entry['subnet']
            ).one_or_none(),
            None)
    # _check_add()

    def _check_update(self, login, orig_dict, entry):
        """
        Auxiliar method to check results of update
        """
        # check results
        ip_obj = self._get_ip(
            subnet=entry['subnet'], address=entry['address'])
        # IMPORTANT: refresh allows the relationships which were changed by
        # the operation to be loaded with the new values
        self.db.session.refresh(ip_obj)

        # check ip values
        for field in IP_HEADERS:
            # normalize empty to None
            if field == 'desc' and not entry[field]:
                entry_value = None
            else:
                entry_value = entry[field]
            self.assertEqual(
                entry_value, getattr(ip_obj, field),
                'Comparison of field "{}" failed for login "{}"'
                .format(field, login))
        # system assignment changed: check ip iface associations
        if orig_dict['system'] and entry['system']:
            iface_obj = models.SystemIface.query.filter_by(
                ip_address_id=ip_obj.id).first()
            # re-assign to same system: check that iface associations were
            # preserved
            if orig_dict['system'] == entry['system']:
                self.assertIsNotNone(iface_obj)
            # system changed: check that iface associations were removed
            else:
                self.assertIsNone(iface_obj)

        # check rollback to original values
        self.db.session.rollback()
        ip_obj = self._get_ip(
            subnet=entry['subnet'], address=entry['address'])
        for field in IP_HEADERS:
            self.assertEqual(
                orig_dict[field], getattr(ip_obj, field),
                'Comparison of field "{}" failed for login "{}"'
                .format(field, login))
    # _check_update()

    def _get_orig_values(self, ref_entry):
        """
        Given a db object return a dict containing the original values for
        later comparison
        """
        # fetch ip original values for later comparison
        ip_obj = self._get_ip(
            subnet=ref_entry['subnet'], address=ref_entry['address'])
        ip_orig = {field: getattr(ip_obj, field) for field in IP_HEADERS}

        return ip_orig
    # _get_orig_values()

    @staticmethod
    def _get_ip(address, subnet):
        return models.IpAddress.query.join(
            'subnet_rel'
        ).filter(
            models.IpAddress.address == address,
            models.Subnet.name == subnet
        ).one()
    # _get_ip()

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

        patcher = patch.object(resource_ip, 'logging')
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
        ref_entry = {
            'subnet': self._subnet_name,
            'address': '192.168.160.10',
            'system': '',
            'owner': 'admin',
            'project': 'bulkop project',
            'desc': 'Some description',
        }

        logins = [
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]

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
            res_obj = resource_ip.ResourceHandlerIpAddress(user_obj)
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

        for login in logins:
            # create ip without system, user has permission to ip
            assert_action(ref_entry, login)

            # create ip with system, user has permission to both
            assert_action(ref_entry, login, 'cpc3lp52')

        # start section: no role scenarios

        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
        ]
        for login in logins:
            # create ip without system, user has no permission to ip
            msg = 'User has no CREATE permission for the specified project'
            assert_action(ref_entry, login, error_msg=msg)

            # exercise case where user has permission via ownership
            if login in ('user_restricted@domain.com', 'user_user@domain.com'):
                sys_owner = login
            # exercise case where user has permission via role
            else:
                sys_owner = 'admin'
            # create ip with system, user has permission to system but not
            # to ip
            assert_action(ref_entry, login, 'cpc3lp52', sys_owner,
                          error_msg=msg)
        logins = [
            'user_hw_admin@domain.com',
        ]
        for login in logins:
            # create ip with system, user has permission to ip but not
            # to system
            msg = 'User has no UPDATE permission for the specified system'
            assert_action(ref_entry, login, 'cpc3', sys_owner,
                          error_msg=msg)
    # test_add_many_roles()

    def test_invalid_values(self):
        """
        Test general invalid values
        """
        ref_entry = {
            'subnet': self._subnet_name,
            'address': '192.168.160.10',
            'system': '',
            'owner': 'admin',
            'project': 'bulkop project',
            'desc': 'Some description',
        }

        combos = [
            ('Subnet wrong_subnet not found',
             {'subnet': 'wrong_subnet'}),
            ('IP address xxxxx has invalid format',
             {'address': 'xxxxx'}),
        ]

        user_obj = models.User.query.filter_by(
            login='user_hw_admin@domain.com').one()
        res_obj = resource_ip.ResourceHandlerIpAddress(user_obj)
        for msg, values in combos:
            entry = deepcopy(ref_entry)
            entry.update(values)
            with self.assertRaisesRegex(ValueError, msg):
                res_obj.render_item(entry)
    # test_invalid_values()

    def test_update_change_project(self):
        """
        Test the case when the ip project is changed
        """
        ref_entry = {
            'subnet': self._subnet_name,
            'address': '192.168.161.222',
            'system': '',
            'owner': 'admin',
            'project': 'bulkop project 2',
            'desc': 'Some description',
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

            ip_obj = self._get_ip(
                subnet=ref_entry['subnet'], address=ref_entry['address'])
            ip_orig_owner = ip_obj.owner
            ip_orig_system = ip_obj.system
            ip_obj.system = None
            # exercise case where user is ip owner
            if login not in ('user_hw_admin@domain.com',
                             'user_admin@domain.com'):
                ip_obj.owner = login
            # exercise case where user has ip permission through a role
            else:
                ip_obj.owner = 'admin'
            self.db.session.add(ip_obj)

            # give user a role to update ip on the new project
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
            res_obj = resource_ip.ResourceHandlerIpAddress(user_obj)
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

            # restore original ip owner
            ip_obj = self._get_ip(
                subnet=ref_entry['subnet'], address=ref_entry['address'])
            ip_obj.owner = ip_orig_owner
            ip_obj.system = ip_orig_system
            self.db.session.add(ip_obj)
            self.db.session.commit()
    # test_update_change_project()

    def test_update_many_roles(self):
        """
        Test different scenarios of updating an ip address
        """
        ref_entry = {
            'subnet': self._subnet_name,
            'address': '192.168.161.222',
            'system': '',
            'owner': 'admin',
            'project': 'bulkop project',
            'desc': 'Some description',
        }

        def assert_update(update_user, ip_owner, sys_cur, sys_target,
                          error_msg=None):
            """
            Helper function to validate update action

            Args:
                update_user (str): login performing the update action
                ip_owner (str): owner of ip
                sys_cur (str): name and owner of the current system
                sys_target (str): name and owner of target system
                error_msg (str): should wait for error when specified
            """
            ip_obj = self._get_ip(
                subnet=ref_entry['subnet'], address=ref_entry['address'])
            ip_orig_owner = ip_obj.owner
            ip_obj.owner = ip_owner
            self.db.session.add(ip_obj)

            # system values before changes made by the method
            sys_orig_owners = {}
            if sys_cur:
                sys_obj = models.System.query.filter_by(
                    name=sys_cur['name']).one()
                sys_orig_owners['cur'] = sys_obj.owner
                sys_obj.owner = sys_cur['owner']
                # assign ip to system
                ip_obj.system = sys_cur['name']
            else:
                ip_obj.system = None
            self.db.session.add(ip_obj)
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
            res_obj = resource_ip.ResourceHandlerIpAddress(user_obj)
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
            # restore ip owner
            ip_obj = self._get_ip(
                subnet=ref_entry['subnet'], address=ref_entry['address'])
            ip_obj.owner = ip_orig_owner
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
            # exercise case where user has ip permission through a role
            if login in ('user_hw_admin@domain.com', 'user_admin@domain.com'):
                ip_owner = 'admin'
            # exercise case where user is ip owner
            else:
                ip_owner = login

            # exercise case where user is system owner
            if login in ('user_restricted@domain.com', 'user_user@domain.com'):
                sys_owner = login
            # exercise case where user has system permission through a role
            else:
                sys_owner = 'admin'

            # update ip assign system, user has permission to both ip and
            # system
            assert_update(login, ip_owner, None,
                          {'owner': sys_owner, 'name': 'cpc3lp52'})

            # update ip re-assign to same system, profile associations are
            # preserved
            assert_update(login, ip_owner,
                          {'owner': sys_owner, 'name': 'cpc3lp52'},
                          {'owner': sys_owner, 'name': 'cpc3lp52'})

            # update ip withdraw system, user has permission to ip and
            # system
            assert_update(login, ip_owner,
                          {'owner': sys_owner, 'name': 'cpc3lp52'},
                          None)

            # update ip re-assign system, user has permission to all
            assert_update(login, ip_owner,
                          {'owner': sys_owner, 'name': 'cpc3lp52'},
                          {'owner': sys_owner, 'name': 'cpc3lp53'})

        # start section: no role scenarios

        # roles without update ip permission
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
        ]
        for login in logins:
            # update ip without system, user has no permission to ip
            msg = 'User has no UPDATE permission for the specified IP address'
            assert_update(
                login, 'admin', None,
                None, error_msg=msg)

            # update ip assign system, user has permission to system but
            # not to ip
            msg = 'User has no UPDATE permission for the specified IP address'
            assert_update(
                login, 'admin', None,
                {'owner': login, 'name': 'cpc3lp52'},
                error_msg=msg)

            # update ip withdraw system, user has permission to system but
            # not to ip
            assert_update(login, 'admin', {'owner': login, 'name': 'cpc3lp52'},
                          None, error_msg=msg)

            # update ip re-assign system, user has permission to ip and
            # target system but not to current system
            msg = ('User has no UPDATE permission for the system '
                   'currently holding the IP address')
            assert_update(
                login, login, {'owner': 'admin', 'name': 'cpc3'},
                {'owner': login, 'name': 'cpc3lp53'}, error_msg=msg)

            # update ip re-assign system, user has permission to ip and
            # current system but not to target system
            msg = 'User has no UPDATE permission for the specified system'
            assert_update(
                login, login, {'owner': login, 'name': 'cpc3lp52'},
                {'owner': 'admin', 'name': 'cpc3'}, error_msg=msg)

        for login in ('user_restricted@domain.com', 'user_user@domain.com'):
            # update ip assign system, user has permission to ip but not
            # to system
            msg = 'User has no UPDATE permission for the specified system'
            assert_update(
                login, login, None,
                {'name': 'cpc3lp52', 'owner': 'admin'}, error_msg=msg)

            # update ip assign system, user has no permission to ip nor
            # system
            msg = 'User has no UPDATE permission for the specified IP address'
            assert_update(
                login, 'admin', None,
                {'name': 'cpc3lp52', 'owner': 'admin'}, error_msg=msg)

            # update ip withdraw system, user has permission to ip but
            # not to assigned system
            msg = ('User has no UPDATE permission for the system currently '
                   'holding the IP address')
            assert_update(
                login, login, {'name': 'cpc3lp52', 'owner': 'admin'},
                None, error_msg=msg)

            # update ip withdraw system, user has no permission to ip nor
            # system
            msg = 'User has no UPDATE permission for the specified IP address'
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
            "address": "192.168.161.222",
            "desc": '',
            # add strange key on purpose to test sanitization by code
            "modifier": "admin",
            "owner": "admin",
            "project": "bulkop project",
            "subnet": "lab1-1801-cpc3",
            "system": "cpc3lp52"
        }

        login = 'user_hw_admin@domain.com'
        # perform action
        orig_dict = self._get_orig_values(ref_entry)
        user_obj = models.User.query.filter_by(login=login).one()
        res_obj = resource_ip.ResourceHandlerIpAddress(user_obj)
        res_obj.render_item(ref_entry)

        # check results
        self._check_update(login, orig_dict, ref_entry)

        self._mock_logger.info.assert_any_call(
            'skipping IP address %s/%s (no changes)', ref_entry['subnet'],
            ref_entry['address'])
    # test_update_no_change()
# TestResourceIpAddress
