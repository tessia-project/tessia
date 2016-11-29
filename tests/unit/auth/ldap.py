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
Unit test for ldap auth module
"""

#
# IMPORTS
#
from tessia_engine.auth import ldap
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch
from unittest.mock import sentinel

import jsonschema
#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

# pylint: disable=no-member
class TestLdapLoginManager(TestCase):
    """
    Unit test for the package constructor.
    """
    def setUp(self):
        """
        Prepare the mocks for dependencies used by the module.
        """
        # patch the logging module
        self.patcher_logging = patch.object(ldap, 'logging')
        mock_logging = self.patcher_logging.start()
        mock_logging.getLogger.return_value = Mock(
            spec=['info', 'warning', 'error', 'debug'])
        self.mock_logger = mock_logging.getLogger.return_value

        # prepare the configuration values
        self.patcher_config = patch.object(ldap, 'CONF')
        self.mock_config = self.patcher_config.start()
        self.test_conf = {
            'auth': {
                'ldap': {
                    'host': 'foo.com',
                    'username': 'userfoo',
                    'password': 'foopwd',
                    'user_base': 'ou=base,o=foo.com',
                    'user_filter': '(objectclass=Person)',
                    'user_attributes': {
                        'title': 'title',
                    },
                    'group_filter': '(cn=foo-users)',
                    'group_base': 'ou=foogroup,o=foo.com',
                    'group_membership_attr': 'uniquemember',
                }
            }
        }
        self.mock_config.get_config.return_value = self.test_conf

        # prepare the mocks for ldap3 library
        self.patcher_ldap3 = patch.object(ldap, 'ldap3')
        self.mock_ldap3 = self.patcher_ldap3.start()
        self.mock_ldap3.Server.return_value = sentinel.server_obj
        self.mock_ldap3.NONE = sentinel.ldap3_none
        self.mock_conn = MagicMock(
            spec_set=['bind', 'search', 'response', 'result', '__exit__',
                      '__enter__']
        )
        self.mock_conn.__enter__.return_value = self.mock_conn
        self.mock_ldap3.Connection.return_value = self.mock_conn

    # setUp()

    def tearDown(self):
        """
        Stop patching the mocks. Before each test setUp will be executed and
        the patch created again.
        """
        self.patcher_logging.stop()
        self.patcher_config.stop()
        self.patcher_ldap3.stop()
    # tearDown()

    def test_auth_conn_exception(self):
        """
        Test the scenario where the authentication fails due to exception in
        Connection instantiation
        """
        # prepare search operation
        self.mock_conn.search.return_value = True
        fake_resp = {
            'attributes': {
                'mail': ['baruser@foo.com'],
                'cn': ['Bar User', 'Baruser'],
                'title': 'Job title',
            },
            'type': 'searchResEntry',
            'dn': 'uid=000000000,c=de,ou=base,o=foo.com',
        }
        self.mock_conn.response.__getitem__.return_value = fake_resp
        self.mock_conn.response.__len__.return_value = 1

        # simulate ldap3 Connection failing
        empty_exc = Exception('Empty password')
        self.mock_ldap3.Connection.side_effect = [self.mock_conn, empty_exc]

        # validate result
        ldap_manager = ldap.MANAGER()
        self.assertIs(None, ldap_manager.authenticate('baruser', ''))

        # validate behavior
        self.mock_conn.bind.assert_not_called()
        self.mock_logger.debug.assert_called_with(
            'User %s bind failed, debug info:',
            fake_resp['dn'],
            exc_info=empty_exc)
    # test_auth_conn_fail()

    def test_auth_bind_exception(self):
        """
        Test the scenario where the authentication fails due to exception in
        bind call. This test simulates the scenario where an empty password is
        provided which causes an exception in this method.
        """
        # prepare search operation
        self.mock_conn.search.return_value = True
        fake_resp = {
            'attributes': {
                'mail': ['baruser@foo.com'],
                'cn': ['Bar User', 'Baruser'],
                'title': 'Job title',
            },
            'type': 'searchResEntry',
            'dn': 'uid=000000000,c=de,ou=base,o=foo.com',
        }
        self.mock_conn.response.__getitem__.return_value = fake_resp
        self.mock_conn.response.__len__.return_value = 1

        # simulate ldap3 bind failing
        empty_exc = Exception('Empty password')
        self.mock_conn.bind.side_effect = empty_exc

        # validate result
        ldap_manager = ldap.MANAGER()
        self.assertIs(None, ldap_manager.authenticate('baruser', ''))

        # validate behavior
        self.mock_conn.bind.assert_called_with()
        self.mock_logger.debug.assert_called_with(
            'User %s bind failed, debug info:',
            fake_resp['dn'],
            exc_info=empty_exc)
    # test_auth_conn_fail()

    def test_auth_empty_list(self):
        """
        Verify if module correctly treats responses with empty lists as
        attributes
        """
        # prepare search mock
        self.mock_conn.search.return_value = True
        # bind operation
        self.mock_conn.bind.return_value = True
        # response to the search and bind calls
        self.mock_conn.response.__len__.return_value = 1
        fake_resp = {
            'attributes': {
                'mail': ['baruser@foo.com'],
                'cn': ['Bar User', 'Baruser'],
                'title': [],
            },
            'type': 'searchResEntry',
            'dn': 'uid=000000000,c=de,ou=base,o=foo.com',
        }
        self.mock_conn.response.__getitem__.return_value = fake_resp

        # perform action
        ldap_manager = ldap.MANAGER()

        # validate response
        check_resp = {
            'login': fake_resp['attributes']['mail'][0],
            'fullname': fake_resp['attributes']['cn'][0],
            'title': '',
        }
        self.assertEqual(
            check_resp, ldap_manager.authenticate('baruser', 'barpwd'))
    # test_auth_empty_list()

    def test_auth_no_group(self):
        """
        Test a successful authentication without group filter
        """
        # that causes a search without verifying group membership
        del self.test_conf['auth']['ldap']['group_filter']

        # prepare search mock
        self.mock_conn.search.return_value = True
        # bind operation
        self.mock_conn.bind.return_value = True
        # response to the search and bind calls
        self.mock_conn.response.__len__.return_value = 1
        fake_resp = {
            'attributes': {
                'mail': ['baruser@foo.com'],
                'cn': ['Bar User', 'Baruser'],
                'title': 'Job title',
            },
            'type': 'searchResEntry',
            'dn': 'uid=000000000,c=de,ou=base,o=foo.com',
        }
        self.mock_conn.response.__getitem__.return_value = fake_resp

        # perform action
        ldap_manager = ldap.MANAGER()

        # validate response
        check_resp = {
            'login': fake_resp['attributes']['mail'][0],
            'fullname': fake_resp['attributes']['cn'][0],
            'title': fake_resp['attributes']['title'],
        }
        self.assertEqual(
            check_resp, ldap_manager.authenticate('baruser', 'barpwd'))

        # validate behavior
        _, kwargs = self.mock_conn.search.call_args
        self.assertEqual(
            kwargs['search_base'], self.test_conf['auth']['ldap']['user_base'])
        self.assertEqual(
            kwargs['search_filter'], '(&(mail=baruser)(objectclass=Person))')
        for item in ['mail', 'cn', 'title']:
            if item not in kwargs['attributes']:
                raise AssertionError('User attribute {} missing'.format(item))

        self.mock_ldap3.Connection.assert_any_call(
            sentinel.server_obj,
            self.test_conf['auth']['ldap']['username'],
            self.test_conf['auth']['ldap']['password'],
            read_only=True,
            receive_timeout=10
        )
        self.mock_ldap3.Connection.assert_any_call(
            sentinel.server_obj,
            fake_resp['dn'],
            'barpwd',
            read_only=True,
            receive_timeout=10
        )
        self.mock_conn.bind.assert_called_with()

    # test_auth_no_group()

    def test_auth_with_group(self):
        """
        Test a successful authentication using group filter
        """
        # prepare search mock
        self.mock_conn.search.return_value = True
        # bind operation
        self.mock_conn.bind.return_value = True
        # response to the search and bind calls
        self.mock_conn.response.__len__.return_value = 1
        fake_resp = {
            'attributes': {
                'mail': ['baruser@foo.com'],
                'cn': ['Bar User', 'Baruser'],
                'title': 'Job title',
            },
            'type': 'searchResEntry',
            'dn': 'uid=000000000,c=de,ou=base,o=foo.com',
        }
        self.mock_conn.response.__getitem__.return_value = fake_resp

        # perform action
        ldap_manager = ldap.MANAGER()

        # validate response
        check_resp = {
            'login': fake_resp['attributes']['mail'][0],
            'fullname': fake_resp['attributes']['cn'][0],
            'title': fake_resp['attributes']['title'],
        }
        self.assertEqual(
            check_resp, ldap_manager.authenticate('baruser', 'barpwd'))

        # validate behavior
        ldap_conf = self.test_conf['auth']['ldap']

        search_filter = '(&{group_filter}({member_attr}={user_dn}))'.format(
            group_filter=ldap_conf['group_filter'],
            member_attr=ldap_conf['group_membership_attr'],
            user_dn=fake_resp['dn']
        )
        self.mock_conn.search.assert_called_with(
            search_base=ldap_conf['group_base'],
            search_filter=search_filter,
            attributes=[ldap_conf['group_membership_attr']]
        )
        self.mock_ldap3.Connection.assert_any_call(
            sentinel.server_obj,
            ldap_conf['username'],
            ldap_conf['password'],
            read_only=True,
            receive_timeout=10
        )
        self.mock_ldap3.Connection.assert_any_call(
            sentinel.server_obj,
            fake_resp['dn'],
            'barpwd',
            read_only=True,
            receive_timeout=10
        )
        self.mock_conn.bind.assert_called_with()

    # test_auth_with_group()

    def test_auth_with_group_fail(self):
        """
        Test an authentication when the user is not part of the group
        """
        # prepare search mock
        self.mock_conn.search.side_effect = [True, False]
        # response to the first search
        self.mock_conn.response.__len__.return_value = 1
        fake_resp = {
            'attributes': {
                'mail': ['baruser@foo.com'],
                'cn': ['Bar User', 'Baruser'],
                'title': 'Job title',
            },
            'type': 'searchResEntry',
            'dn': 'uid=000000000,c=de,ou=base,o=foo.com',
        }
        self.mock_conn.response.__getitem__.return_value = fake_resp

        # perform action
        ldap_manager = ldap.MANAGER()

        # validate result
        self.assertEqual(None, ldap_manager.authenticate('baruser', 'barpwd'))

        # validate behavior - since most behavior is already checked by the
        # positive test we just check the difference
        self.mock_logger.warning.assert_called_with(
            'user %s not member of allowed group(s)', 'baruser')
    # test_auth_with_group_fail()

    def test_bind_fail(self):
        """
        Test the scenario where the bind operation fails
        """
        # prepare search operation
        self.mock_conn.search.return_value = True
        fake_resp = {
            'attributes': {
                'mail': ['baruser@foo.com'],
                'cn': ['Bar User', 'Baruser'],
                'title': 'Job title',
            },
            'type': 'searchResEntry',
            'dn': 'uid=000000000,c=de,ou=base,o=foo.com',
        }
        self.mock_conn.response.__getitem__.return_value = fake_resp
        self.mock_conn.response.__len__.return_value = 1
        # make bind fail
        self.mock_conn.bind.return_value = False

        # validate result
        ldap_manager = ldap.MANAGER()
        self.assertIs(None, ldap_manager.authenticate('baruser', 'barpwd'))

        # validate behavior
        self.mock_conn.bind.assert_called_with()
        self.mock_logger.debug.assert_called_with(
            'User %s bind failed: %s', fake_resp['dn'], self.mock_conn.result)
    # test_bind_fail()

    def test_invalid_config(self):
        """
        Test if the module fails when invalid configuration is found
        """
        # configuration has no auth section
        self.mock_config.get_config.return_value = {}
        with self.assertRaisesRegex(
            RuntimeError, 'No ldap configuration section found'):
            ldap.MANAGER()

        # configuration has auth section but no ldap sub-section
        self.mock_config.get_config.return_value = {'auth': None}
        with self.assertRaisesRegex(
            RuntimeError, 'No ldap configuration section found'):
            ldap.MANAGER()

        # configuration has ldap section but invalid parameters
        self.mock_config.get_config.return_value = {
            'auth': {
                'ldap': 'foo'
            }
        }
        self.assertRaises(jsonschema.exceptions.ValidationError, ldap.MANAGER)

        # configuration has missing parameters
        self.mock_config.get_config.return_value = {
            'auth': {
                'ldap': 'host'
            }
        }
        self.assertRaises(jsonschema.exceptions.ValidationError, ldap.MANAGER)

        # specified group filter but no group base
        self.mock_config.get_config.return_value = {
            'auth': {
                'ldap': {
                    'host': 'foo.com',
                    'user_base': 'ou=base,o=foo.com',
                    'group_filter': '(cn=foo-users)',
                }
            }
        }
        self.assertRaisesRegex(
            RuntimeError,
            'group_filter requires group_base parameter',
            ldap.MANAGER)

        # specified group filter and group base but no group membership
        # attribute
        self.mock_config.get_config.return_value = {
            'auth': {
                'ldap': {
                    'host': 'foo.com',
                    'user_base': 'ou=base,o=foo.com',
                    'group_filter': '(cn=foo-users)',
                    'group_base': 'ou=foogroups,o=foo.com',
                }
            }
        }
        self.assertRaisesRegex(
            RuntimeError,
            'group_filter requires group_membership_attr parameter',
            ldap.MANAGER)

    # test_invalid_config()

    def test_search_fail(self):
        """
        Test the scenario where the search operation fails.
        """
        # make search fail
        self.mock_conn.search.return_value = False
        ldap_manager = ldap.MANAGER()
        self.assertIs(None, ldap_manager.authenticate('baruser', 'barpwd'))

        # validate behavior
        self.mock_ldap3.Server.assert_called_with(
            self.test_conf['auth']['ldap']['host'], port=636, use_ssl=True,
            get_info=sentinel.ldap3_none)
        self.mock_ldap3.Connection.assert_called_with(
            sentinel.server_obj,
            self.test_conf['auth']['ldap']['username'],
            self.test_conf['auth']['ldap']['password'],
            read_only=True,
            receive_timeout=10
        )
        _, kwargs = self.mock_conn.search.call_args
        self.assertEqual(
            kwargs['search_base'], self.test_conf['auth']['ldap']['user_base'])
        self.assertEqual(
            kwargs['search_filter'], '(&(mail=baruser)(objectclass=Person))')
        for item in ['mail', 'cn', 'title']:
            if item not in kwargs['attributes']:
                raise AssertionError('User attribute {} missing'.format(item))

    # test_search_fail()

    def test_search_missing_attribute(self):
        """
        Test search returning response with missing attribute
        """
        # prepare search mock
        self.mock_conn.search.return_value = True
        # bind operation
        self.mock_conn.bind.return_value = True
        # response to the search and bind calls
        self.mock_conn.response.__len__.return_value = 1
        # removed title attribute to cause error
        fake_resp = {
            'attributes': {
                'mail': ['baruser@foo.com'],
                'cn': ['Bar User', 'Baruser'],
            },
            'type': 'searchResEntry',
            'dn': 'uid=000000000,c=de,ou=base,o=foo.com',
        }
        self.mock_conn.response.__getitem__.return_value = fake_resp

        # perform action
        ldap_manager = ldap.MANAGER()

        # validate response
        with self.assertRaisesRegex(
            RuntimeError, 'User attribute title not found in server response'):
            ldap_manager.authenticate('baruser', 'barpwd')
    # test_search_missing_attribute()

# TestLdapLoginManager
