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
Unit test for bulkop machine module
"""

#
# IMPORTS
#
from copy import deepcopy
from tessia.server.db import models
from tessia.server.state_machines import base
from tessia.server.state_machines.bulkop import resource_system
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest.mock import patch
from unittest.mock import Mock

import json
import os

#
# CONSTANTS AND DEFINITIONS
#
SYS_HEADERS = (
    [field.lower() for field in resource_system.FIELDS_CSV
     if field.lower() not in ['ip', 'iface', 'layer2', 'portno']])

#
# CODE
#

class TestResourceSystem(TestCase):
    """
    Unit test for the resource_system module of the bulkop state machine.
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
        # subnet used for ip testing
        cls._subnet_name = 'lab1-1801-cpc3'
    # setUpClass()

    def _check_add(self, login, ip_dict, entry):
        """
        Auxiliar method to check results of add
        """
        # check results
        sys_obj = models.System.query.filter_by(name=entry['name']).one()

        # check system values
        for field in SYS_HEADERS:
            # ip field: must add subnet name to it
            if field == 'ip':
                entry_value = '{}/{}'.format(self._subnet_name, entry[field])
            else:
                entry_value = entry[field]
            self.assertEqual(
                entry_value, getattr(sys_obj, field),
                'Comparison of field "{}" failed for login "{}"'
                .format(field, login))

        # check system iface values
        iface_obj = models.SystemIface.query.filter_by(
            system_id=sys_obj.id).one()
        iface_entry = {
            'name': 'osa-{}'.format(
                entry['iface'].strip("'").split(',')[0].lstrip('0.0.')),
            'osname': 'enc{}'.format(
                entry['iface'].strip("'").split(',')[0].lstrip('0.0.')),
            'attributes': {
                'ccwgroup': entry['iface'].strip("'"),
                'portno': '0',
                'layer2': True,
            }
        }
        # add subnet name to ip
        iface_entry['ip_address'] = '{}/{}'.format(
            self._subnet_name, entry['ip'])
        for field in ['ip_address', 'attributes']:
            self.assertEqual(
                iface_entry[field], getattr(iface_obj, field),
                "Field {} did not match".format(field))

        # check new ip address assignment
        ip_obj = self._get_ip(
            address=entry['ip'], subnet=self._subnet_name)
        self.db.session.refresh(ip_obj)
        self.assertEqual(ip_obj.system, sys_obj.name)

        # check rollback to original values
        self.db.session.rollback()
        self.assertEqual(models.System.query.filter_by(
            name=entry['name']).one_or_none(), None)

        ip_obj = models.IpAddress.query.filter_by(id=ip_dict['id']).one()
        self.assertEqual(ip_obj.system, ip_dict['system'])
    # _check_add()

    def _check_update(self, login, orig_dict, entry):
        """
        Auxiliar method to check results of update
        """
        # check results
        sys_obj = models.System.query.filter_by(name=entry['name']).one()
        # IMPORTANT: refresh allows the relationships which were changed by
        # the operation to be loaded with the new values
        self.db.session.refresh(sys_obj)

        # check that system values were changed
        for field in SYS_HEADERS:
            # ip field: must add subnet name to it
            if field == 'ip':
                entry_value = '{}/{}'.format(self._subnet_name, entry[field])
            # normalize empty to None
            elif field == 'desc' and not entry[field]:
                entry_value = None
            else:
                entry_value = entry[field]
            self.assertEqual(
                entry_value, getattr(sys_obj, field),
                'Comparison of field "{}" failed for login "{}"'
                .format(field, login))

        # check that system iface values were changed
        iface_obj = models.SystemIface.query.filter_by(
            id=orig_dict['iface']['id']).one()
        self.db.session.refresh(iface_obj)
        iface_entry = {
            'attributes': {
                'ccwgroup': entry['iface'].strip("'"),
                'portno': '1',
                'layer2': False,
            }
        }
        # add subnet name to ip
        iface_entry['ip_address'] = '{}/{}'.format(
            self._subnet_name, entry['ip'])
        for field in ['ip_address', 'attributes']:
            self.assertEqual(
                iface_entry[field], getattr(iface_obj, field),
                "Field {} did not match".format(field))

        # check new ip address assignment
        ip_obj = models.IpAddress.query.filter_by(
            id=orig_dict['ip']['new']['id']).one()
        self.db.session.refresh(ip_obj)
        self.assertEqual(ip_obj.system, sys_obj.name)
        # check that new ip has no iface associated with a previous system
        self.assertIsNone(models.SystemIface.query.filter(
            models.SystemIface.ip_address_id == ip_obj.id,
            models.SystemIface.system_id != sys_obj.id
            ).first(), None)

        # system switched ips: check that old ip remains assigned to system
        if orig_dict['ip'].get('old') and (
                orig_dict['ip']['old']['system'] ==
                orig_dict['ip']['new']['system']):
            old_ip_obj = models.IpAddress.query.filter_by(
                id=orig_dict['ip']['old']['id']).one()
            self.assertEqual(old_ip_obj.system, sys_obj.name)

        # check rollback to original values
        self.db.session.rollback()
        sys_obj = models.System.query.filter_by(name=entry['name']).one()
        for field in SYS_HEADERS:
            self.assertEqual(
                orig_dict['sys'][field], getattr(sys_obj, field),
                'Comparison of field "{}" failed for login "{}"'
                .format(field, login))
        iface_obj = models.SystemIface.query.filter_by(
            id=orig_dict['iface']['id']).one()
        for field in ['ip_address', 'attributes']:
            self.assertEqual(
                orig_dict['iface'][field], getattr(iface_obj, field),
                'Field {} did not match'.format(field))

        if orig_dict['ip'].get('old'):
            ip_obj = models.IpAddress.query.filter_by(
                id=orig_dict['ip']['old']['id']).one()
            self.assertEqual(ip_obj.system, orig_dict['ip']['old']['system'])
        ip_obj = models.IpAddress.query.filter_by(
            id=orig_dict['ip']['new']['id']).one()
        self.assertEqual(ip_obj.system, orig_dict['ip']['new']['system'])
    # _check_update()

    @staticmethod
    def _get_ip(address, subnet):
        return models.IpAddress.query.join(
            'subnet_rel'
        ).filter(
            models.IpAddress.address == address,
            models.Subnet.name == subnet
        ).one()
    # _get_ip()

    def _get_orig_values(self, ref_entry, old_ip):
        """
        Given a db object return a dict containing the original values for
        later comparison
        """
        # fetch system's original values for later comparison
        sys_obj = models.System.query.filter_by(name=ref_entry['name']).one()
        sys_orig = dict(
            [(field, getattr(sys_obj, field)) for field in SYS_HEADERS])

        # fetch iface's original values for later comparison
        iface_obj = models.SystemIface.query.filter_by(
            system_id=sys_obj.id
        ).filter(
            models.SystemIface.attributes['ccwgroup'].astext ==
            ref_entry['iface'].strip("'")
        ).one()
        iface_orig = {
            'id': iface_obj.id,
            'ip_address': iface_obj.ip_address,
            'attributes': iface_obj.attributes
        }

        # fetch ip's original values for later comparison
        new_ip_obj = self._get_ip(
            address=ref_entry['ip'], subnet=self._subnet_name)
        ip_orig = {
            'new': {'id': new_ip_obj.id, 'system': new_ip_obj.system},
        }
        if old_ip:
            old_ip_obj = self._get_ip(
                address=old_ip['address'], subnet=self._subnet_name)
            ip_orig['old'] = {'id': old_ip_obj.id, 'system': old_ip_obj.system}

        return {'sys': sys_orig, 'iface': iface_orig, 'ip': ip_orig}
    # _get_orig_values()

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

        patcher = patch.object(resource_system, 'logging')
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
        Test different scenarios of adding system/iface
        """
        ip_addr = '192.168.160.10'
        # new IP
        ip_obj = models.IpAddress(
            address=ip_addr,
            desc=None,
            modifier='admin',
            owner='admin',
            project='bulkop project',
            subnet=self._subnet_name,
        )
        self.db.session.add(ip_obj)
        self.db.session.commit()
        def cleanup_helper():
            """Helper to clean up db to original state"""
            # remove ip
            ifaces = models.SystemIface.query.filter_by(
                ip_address_id=ip_obj.id).all()
            for iface_obj in ifaces:
                iface_obj.ip_address = None
                self.db.session.add(iface_obj)
            self.db.session.delete(ip_obj)
            self.db.session.commit()
        self.addCleanup(cleanup_helper)

        ref_entry = {
            'hypervisor': 'cpc3',
            'name': 'cpc3lp60',
            'type': 'LPAR',
            'hostname': 'cpc3lp60.domain._com',
            'ip': ip_addr,
            'iface': "0.0.f500,0.0.f501,0.0.f502",
            'layer2': '1',
            'portno': '0',
            'owner': 'user_user@domain.com',
            'project': 'bulkop project',
            'state': 'AVAILABLE',
            'desc': 'Some description',
        }

        def assert_action(login, ip_owner, ip_system=None, error_msg=None):
            """
            Helper function to validate action
            """
            ip_obj = self._get_ip(address=ip_addr, subnet=self._subnet_name)
            ip_orig = {'id': ip_obj.id, 'owner': ip_obj.owner,
                       'system': ip_obj.system}
            ip_obj.owner = ip_owner
            # assign ip to a system
            if ip_system:
                ip_obj.system = ip_system
            else:
                ip_obj.system = None
            self.db.session.add(ip_obj)

            # commit all changes
            self.db.session.commit()

            # perform action
            entry = deepcopy(ref_entry)
            user_obj = models.User.query.filter_by(login=login).one()
            res_obj = resource_system.ResourceHandlerSystem(user_obj)
            # error message specified: check that error occurs
            if error_msg:
                with self.assertRaisesRegex(PermissionError, error_msg):
                    res_obj.render_item(entry)
                self.db.session.rollback()
            else:
                res_obj.render_item(entry)
                # validate
                self._check_add(login, ip_orig, entry)

            # restore ip values
            ip_obj = self._get_ip(address=ip_addr, subnet=self._subnet_name)
            ip_obj.owner = ip_orig['owner']
            ip_obj.system = ip_orig['system']
            self.db.session.add(ip_obj)
            self.db.session.commit()
        # assert_action()

        logins = [
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        ]
        for login in logins:
            # logins with update-ip permission
            if login in ('user_hw_admin@domain.com', 'user_admin@domain.com'):
                ip_owner = 'admin'
            # logins without permission, must be owner of the ip
            else:
                ip_owner = login

            assert_action(login, ip_owner)

        # start section: no role scenarios

        # logins without update-system and update-ip permission
        logins = [
            'user_restricted@domain.com',
        ]
        for login in logins:
            # user has permission to ip but not to create system
            msg = 'User has no CREATE permission for the specified project'
            assert_action(login, login, error_msg=msg)

            # user has no permission to create system nor ip
            assert_action(login, 'admin', error_msg=msg)

        # logins without update-ip permission
        logins = [
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
        ]
        for login in logins:
            # user has permission to create system but not to ip
            msg = 'User has no UPDATE permission for the specified IP address'
            assert_action(login, 'admin', error_msg=msg)

            # user has permission to create system but ip is already assigned
            # to another system
            msg = ("User has no UPDATE permission for the system 'cpc3' "
                   "currently holding the IP address")
            assert_action(login, 'admin', ip_system='cpc3', error_msg=msg)

        # logins with all permissions
        logins = [
            'user_hw_admin@domain.com',
        ]
        for login in logins:
            # user has permission to create system but ip is already assigned
            # to another system
            msg = ("User has no UPDATE permission for the system 'cpc3' "
                   "currently holding the IP address")
            assert_action(login, 'admin', ip_system='cpc3', error_msg=msg)

    # test_add_many_roles()

    def test_update_change_project(self):
        """
        Test the case when the system project is changed
        """
        ref_entry = {
            'hypervisor': 'cpc3',
            'name': 'cpc3lp52',
            'type': 'LPAR',
            'hostname': 'new_cpc3lp52.domain._com',
            # use same ip already assigned
            'ip': '192.168.161.222',
            'iface': "0.0.f500,0.0.f501,0.0.f502",
            # switch from true to false
            'layer2': '0',
            # add portno parameter
            'portno': '1',
            'owner': 'user_user@domain.com',
            'project': 'bulkop project 2',
            'state': 'LOCKED',
            'desc': 'A new description',
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

            sys_obj = models.System.query.filter_by(
                name=ref_entry['name']).one()
            sys_orig_owner = sys_obj.owner
            # exercise case where user is system owner
            if login == 'user_user@domain.com':
                sys_obj.owner = login
            # exercise case where user has system permission through a role
            else:
                sys_obj.owner = 'admin'
            self.db.session.add(sys_obj)

            ip_obj = self._get_ip(
                address=ref_entry['ip'], subnet=self._subnet_name)
            ip_orig_owner = ip_obj.owner
            # exercise case where user is ip owner
            if login in ('user_user@domain.com', 'user_privileged@domain.com',
                         'user_project_admin@domain.com'):
                ip_obj.owner = login
            # exercise case where user has ip permission through a role
            else:
                ip_obj.owner = 'admin'
            self.db.session.add(ip_obj)

            # give user a role to update system on the new project
            role_obj = models.UserRole(
                project=ref_entry['project'],
                user=user_obj.login,
                role="USER_PRIVILEGED"
            )
            self.db.session.add(role_obj)
            self.db.session.commit()
            role_id = role_obj.id

            # perform action
            orig_dict = self._get_orig_values(
                ref_entry, {'address': ip_obj.address})
            res_obj = resource_system.ResourceHandlerSystem(user_obj)
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

            # restore original owners
            sys_obj = models.System.query.filter_by(
                name=ref_entry['name']).one()
            sys_obj.owner = sys_orig_owner
            self.db.session.add(sys_obj)
            ip_obj = models.IpAddress.query.filter_by(
                id=orig_dict['ip']['new']['id']).one()
            ip_obj.owner = ip_orig_owner
            self.db.session.add(ip_obj)
            self.db.session.commit()

    # test_update_change_project()

    def test_update_invalid_ip(self):
        """
        Exercise invalid IP input
        """
        ref_entry = {
            'hypervisor': 'cpc3',
            'name': 'cpc3lp52',
            'type': 'LPAR',
            'hostname': 'new_cpc3lp52.domain._com',
            'ip': '',
            'iface': "0.0.f500,0.0.f501,0.0.f502",
            # switch from true to false
            'layer2': '0',
            # add portno parameter
            'portno': '1',
            'owner': 'user_user@domain.com',
            'project': 'bulkop project',
            'state': 'LOCKED',
            'desc': 'A new description',
        }

        combos = [
            # make sure ip is mandatory
            ('A system must have an IP address assigned', ''),
            # invalid ips
            ("Invalid IP address 'wrong_ip'", 'wrong_ip'),
            ("Invalid IP address 'wrong/wrong_ip'", 'wrong/wrong_ip'),
            # ip not found
            ("IP address specified not found", 'subnet/10.100.10.10'),
            ("IP address specified not found", '10.100.10.10'),
        ]

        user_obj = models.User.query.filter_by(
            login='user_hw_admin@domain.com').one()
        res_obj = resource_system.ResourceHandlerSystem(user_obj)
        for msg, value in combos:
            ref_entry['ip'] = value
            with self.assertRaisesRegex(ValueError, msg):
                res_obj.render_item(ref_entry)
            self.db.session.rollback()
    # test_update_invalid_ip()

    def test_update_invalid_values(self):
        """
        Test general invalid values
        """
        ref_entry = {
            'hypervisor': 'cpc3',
            'name': 'cpc3lp52',
            'type': 'LPAR',
            'hostname': 'new_cpc3lp52.domain._com',
            'ip': '192.168.161.222',
            'iface': "0.0.f500,0.0.f501,0.0.f502",
            'layer2': '0',
            'portno': '1',
            'owner': 'user_user@domain.com',
            'project': 'bulkop project 2',
            'state': 'LOCKED',
            'desc': 'A new description',
        }
        combos = [
            ('Tried to change hypervisor from cpc3 to cpc3lp53',
             {'hypervisor': 'cpc3lp53'}),
            ('Value for layer2 must be 1 or 0', {'layer2': 'true'}),
            ('Value for portno must be 1 or 0', {'portno': '2'}),
            ('Tried to change system type from LPAR to KVM',
             {'type': 'KVM'}),
        ]

        user_obj = models.User.query.filter_by(
            login='user_hw_admin@domain.com').one()
        res_obj = resource_system.ResourceHandlerSystem(user_obj)
        for msg, values in combos:
            entry = deepcopy(ref_entry)
            entry.update(values)
            with self.assertRaisesRegex(ValueError, msg):
                res_obj.render_item(entry)
            self.db.session.rollback()
    # test_update_invalid_values()

    def test_update_many_roles(self):
        """
        Test different scenarios of updating system/iface
        """
        # new IPs for testing
        ip_addr = '192.168.160.10'
        ip_addr_2 = '192.168.160.11'
        for addr in [ip_addr, ip_addr_2]:
            # new IPs for testing
            ip_obj = models.IpAddress(
                address=addr,
                desc=None,
                modifier='admin',
                owner='admin',
                project='bulkop project',
                subnet=self._subnet_name,
            )
            self.db.session.add(ip_obj)
        self.db.session.commit()
        def cleanup_helper():
            """Helper to clean up db to original state"""
            # remove ips
            for addr in [ip_addr, ip_addr_2]:
                ip_obj = self._get_ip(address=addr, subnet=self._subnet_name)
                ifaces = models.SystemIface.query.filter_by(
                    ip_address_id=ip_obj.id).all()
                for iface_obj in ifaces:
                    iface_obj.ip_address = None
                    self.db.session.add(iface_obj)
                self.db.session.delete(ip_obj)
            self.db.session.commit()
        self.addCleanup(cleanup_helper)

        ref_entry = {
            'hypervisor': 'cpc3',
            'name': 'cpc3lp52',
            'type': 'LPAR',
            'hostname': 'new_cpc3lp52.domain._com',
            # assign a new ip
            'ip': ip_obj.address,
            'iface': "0.0.f500,0.0.f501,0.0.f502",
            # switch from true to false
            'layer2': '0',
            # add portno parameter
            'portno': '1',
            'owner': 'user_user@domain.com',
            'project': 'bulkop project 2',
            'state': 'LOCKED',
            'desc': 'A new description',
        }

        def assert_update(update_user, sys_owner, ip_cur, ip_target,
                          error_msg=None):
            """
            Helper function to validate update action

            Args:
                update_user (str): login performing the update action
                sys_owner (str): set this login as owner of the system
                ip_cur (str): name and owner of the current ip address
                ip_target (str): name and owner of target ip address
                error_msg (str): wait for error when specified
            """
            # set system owner
            sys_obj = models.System.query.filter_by(
                name=ref_entry['name']).one()
            orig_sys_owner = sys_obj.owner
            sys_obj.owner = sys_owner
            self.db.session.add(sys_obj)

            # values before changes made by the method
            ip_orig_values = {}
            if ip_cur:
                ip_obj = self._get_ip(
                    address=ip_cur['address'], subnet=self._subnet_name)
                ip_obj.owner = ip_cur['owner']
                # assign ip to system
                ip_obj.system = ref_entry['name']
                self.db.session.add(ip_obj)
                ip_orig_values['cur'] = {
                    'owner': ip_obj.owner, 'system': ip_obj.system,
                    'iface': 'update_test_iface'}

            # target ip
            ip_obj = self._get_ip(
                address=ip_target['address'], subnet=self._subnet_name)
            ip_orig_values['target'] = {
                'owner': ip_obj.owner, 'system': ip_obj.system}
            ip_obj.owner = ip_target['owner']
            # assign ip to system
            if ip_target.get('assign'):
                ip_obj.system = ip_target['assign']
                # make sure at least one iface with the ip assigned exists in
                # order to exercise ip removal
                iface_obj = models.SystemIface(
                    name='update_test_iface', attributes={},
                    system=ip_target['assign'], type='OSA',
                    ip_address_id=ip_obj.id)
                self.db.session.add(iface_obj)
            else:
                ip_obj.system = None
            self.db.session.add(ip_obj)

            # commit all changes
            self.db.session.commit()

            # perform action
            entry = deepcopy(ref_entry)
            entry['project'] = 'bulkop project'
            entry['ip'] = ip_target['address']
            orig_dict = self._get_orig_values(entry, ip_cur)
            user_obj = models.User.query.filter_by(login=update_user).one()
            res_obj = resource_system.ResourceHandlerSystem(user_obj)
            # error message specified: check that error occurs
            if error_msg:
                with self.assertRaisesRegex(PermissionError, error_msg):
                    res_obj.render_item(entry)
                self.db.session.rollback()
            else:
                res_obj.render_item(entry)
                # validate
                self._check_update(update_user, orig_dict, entry)

            # restore cur ip
            if ip_orig_values.get('cur'):
                ip_obj = self._get_ip(
                    address=ip_cur['address'], subnet=self._subnet_name)
                ip_obj.owner = ip_orig_values['cur']['owner']
                ip_obj.system = ip_orig_values['cur']['system']
                self.db.session.add(ip_obj)

            # restore target ip
            ip_obj = self._get_ip(
                address=ip_target['address'], subnet=self._subnet_name)
            ip_obj.owner = ip_orig_values['target']['owner']
            ip_obj.system = ip_orig_values['target']['system']
            self.db.session.add(ip_obj)

            # remove temporary iface
            if ip_target.get('assign'):
                iface_obj = models.SystemIface.query.join(
                    'system_rel').filter(
                        models.SystemIface.name == 'update_test_iface',
                        models.System.name == ip_target['assign']
                    ).one()
                self.db.session.delete(iface_obj)

            # restore system owner
            sys_obj = models.System.query.filter_by(name=entry['name']).one()
            sys_obj.owner = orig_sys_owner
            self.db.session.add(sys_obj)
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
            # update iface set ip, user has permission to both system and ip
            # exercise case where user is owner of system
            if login in ('user_restricted@domain.com', 'user_user@domain.com'):
                sys_owner = login
            # exercise case where user has permission via a role
            else:
                sys_owner = 'admin'
            # exercise case where user is owner of ip
            if login not in ('user_hw_admin@domain.com',
                             'user_admin@domain.com'):
                ip_owner = login
            # exercise case where user has permission via a role
            else:
                ip_owner = 'admin'

            # update iface set ip assigned to system, user has permission to
            # system but not to ip
            assert_update(
                login, sys_owner,
                None, {'address': ip_addr, 'owner': 'admin',
                       'assign': ref_entry['name']},
            )

            # update iface change ip, user has permission to both
            # exercise case where user is owner
            if login not in ('user_hw_admin@domain.com',
                             'user_admin@domain.com'):
                ip_owner_2 = login
            # exercise case where user has permission via a role
            else:
                ip_owner_2 = 'admin'
            assert_update(
                login, sys_owner,
                {'address': ip_addr, 'owner': ip_owner},
                {'address': ip_addr_2, 'owner': ip_owner_2}
            )

            # update iface change ip already assigned to system, user has
            # permission to system but not to ip
            assert_update(
                login, sys_owner,
                {'address': ip_addr, 'owner': ip_owner},
                {'address': ip_addr_2, 'owner': ip_owner_2,
                 'assign': ref_entry['name']},
            )

        logins_system = (
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
            'user_admin@domain.com',
        )
        for login in logins_system:
            # update iface set ip already assigned to another system, user
            # has permission to system and ip
            assert_update(
                login, 'admin', None,
                {'address': ip_addr, 'owner': login, 'assign': 'cpc3lp53'}
            )

        # start section: no role scenarios
        hw_admin = 'user_hw_admin@domain.com'

        # logins with update-system permission but no update-ip
        logins_system = (
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
        )
        for login in logins_system:
            msg = (
                'User has no UPDATE permission for the specified IP address')

            # update iface assign ip, user has permission to system but not
            # to ip
            assert_update(
                login, hw_admin,
                None, {'address': ip_addr, 'owner': hw_admin}, error_msg=msg)

            # update iface change ip, user has permission to system and
            # current ip but not to target ip
            assert_update(
                login, hw_admin,
                {'address': ip_addr, 'owner': login},
                {'address': ip_addr_2, 'owner': hw_admin}, error_msg=msg)

        # logins without update-system permission
        logins_no_system = (
            'user_restricted@domain.com',
            'user_user@domain.com'
        )
        for login in logins_no_system:
            # update iface assign ip, user has permission to ip but
            # not to system
            msg = 'User has no UPDATE permission for the specified system'
            assert_update(
                login, hw_admin,
                None, {'address': ip_addr, 'owner': login}, error_msg=msg)

            # update iface assign ip, user has permission to system but not
            # to ip
            msg = 'User has no UPDATE permission for the specified IP address'
            assert_update(
                login, login,
                None, {'address': ip_addr, 'owner': hw_admin}, error_msg=msg)

            # update iface assign ip, user has no permission to system nor ip
            msg = 'User has no UPDATE permission for the specified system'
            assert_update(
                login, hw_admin,
                None, {'address': ip_addr, 'owner': hw_admin}, error_msg=msg)

            # update iface change ip, user has permission to system and
            # current ip but not to target ip
            msg = 'User has no UPDATE permission for the specified IP address'
            assert_update(
                login, login,
                {'address': ip_addr, 'owner': login},
                {'address': ip_addr_2, 'owner': hw_admin}, error_msg=msg)

        # test cases where target ip belongs to another system in a project
        # without permission
        another_system = 'cpc3'
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com',
        ]
        for login in logins:
            # update iface assign ip, user has permission to system and
            # ip but ip is already assigned to another system
            msg = ("User has no UPDATE permission for the system '{}' "
                   "currently holding the IP address".format(another_system))
            assert_update(
                login, login, None,
                {'address': ip_addr, 'owner': login,
                 'assign': another_system}, error_msg=msg)

            # update iface change ip, user has permission to system and ip but
            # ip is already assigned to another system
            assert_update(
                login, login,
                {'address': ip_addr, 'owner': login},
                {'address': ip_addr_2, 'owner': login,
                 'assign': another_system}, error_msg=msg)
    # test_update_many_roles()

    def test_update_no_change(self):
        """
        Test the case when no changes are detected
        """
        # values below match data.json file
        ref_entry = {
            "desc": '',
            "hostname": "cpc3lp52.domain._com",
            "hypervisor": "cpc3",
            # add strange key on purpose to test sanitization by code
            "modifier": "admin",
            "name": "cpc3lp52",
            "owner": "admin",
            "project": "bulkop project",
            "state": "AVAILABLE",
            "type": "LPAR",
            "iface": "0.0.f500,0.0.f501,0.0.f502",
            "ip": "192.168.161.222",
            "layer2": "1",
            "portno": "0",
        }

        login = 'user_hw_admin@domain.com'
        # perform action
        user_obj = models.User.query.filter_by(login=login).one()
        res_obj = resource_system.ResourceHandlerSystem(user_obj)
        res_obj.render_item(ref_entry)
        self.db.session.rollback()

        self._mock_logger.info.assert_any_call(
            'skipping iface %s/%s (no changes)', ref_entry['name'],
            "gb-extern")
        self._mock_logger.info.assert_any_call(
            'skipping system %s (no changes)', ref_entry['name'])
    # test_update_no_change()
# TestResourceSystem
