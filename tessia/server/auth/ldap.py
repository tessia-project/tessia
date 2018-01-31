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
Enable LDAP based authentication and user info retrieval
"""

#
# IMPORTS
#
from jsonschema import validate
from tessia.server.config import CONF
from tessia.server.auth.base import BaseLoginManager

import ldap3
import logging

#
# CONSTANTS AND DEFINITIONS
#
CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'host': {'type': 'string'},
        'port': {'type': 'number'},
        'ssl': {'type': 'boolean'},
        'username': {'type': 'string'},
        'password': {'type': 'string'},
        'timeout': {'type': 'number'},
        'user_base': {'type': 'string'},
        'user_filter': {'type': 'string'},
        'user_attributes': {
            'type': 'object',
            'properties': {
                'fullname': {'type': ['string', 'null']},
                'login': {'type': ['string', 'null']},
                'title': {'type': ['string', 'null']},
            },
        },
        'group_base': {
            'type': ['string', 'null'],
        },
        'group_filter': {
            'type': ['string', 'null'],
        },
        'group_membership_attr': {
            'type': ['string', 'null'],
        },
    },
    'required': ['host', 'user_base'],
}
#
# CODE
#

class LdapLoginManager(BaseLoginManager):
    """
    Implement support to login authentication against LDAP
    """

    def __init__(self):
        """
        Constructor

        Args:
            None

        Raises:
            RuntimeError: in case db config is missing
        """
        self._logger = logging.getLogger(__name__)

        # validate config file and prepare internal config values
        self._parse_conf()
        self._logger.debug(
            'LDAP module activated with the following config: %s', self._conf)

        self._server = ldap3.Server(
            self._conf['host'],
            port=self._conf['port'],
            use_ssl=self._conf['ssl'],
            get_info=ldap3.NONE
        )
    # __init__()

    def _bind(self, user_dn, password):
        """
        Perform a bind (authentication) operation with the LDAP server

        Args:
            user_dn (str): distiguished name for user
            password (str): password

        Returns:
            bool: True if authentication succeded, False otherwise

        Raises:
            None
        """
        try:
            conn = self._connect(user_dn, password)
            result = conn.bind()
        except Exception as exc:
            self._logger.debug(
                'User %s bind failed, debug info:', user_dn, exc_info=exc)
            return False

        if not result:
            self._logger.debug(
                'User %s bind failed: %s', user_dn, conn.result)

        return result
    # _bind()

    def _connect(self, user_dn, password):
        """
        Open a LDAP connection

        Args:
            user_dn (str): distiguished name for user
            password (str): password

        Returns:
            ldap3.Connection: connection instance

        Raises:
            None
        """
        conn = ldap3.Connection(
            self._server,
            user_dn,
            password,
            read_only=True,
            receive_timeout=self._conf['timeout']
        )

        return conn
    # _connect()

    def _is_group_member(self, conn, user_dn):
        """
        Verify if a given user distiguished name is part of a group (if group
        verification was set in config file).

        Args:
            conn (ldap3.Connection): connection instance
            user_dn (str): user distinguished name

        Returns:
            bool: True if user belongs to group (or no group checking
                  configured), False otherwise

        Raises:
            None
        """
        # group verification not active: nothing to do
        if self._conf['group_filter'] is None:
            return True

        # ask ldap to return the group member list
        search_filter = '(&{group_filter}({member_attr}={user_dn}))'.format(
            group_filter=self._conf['group_filter'],
            member_attr=self._conf['group_membership_attr'],
            user_dn=user_dn
        )
        self._logger.debug(
            "perform membership search with filter: '%s'", search_filter)

        # perform operation
        result = conn.search(
            search_base=self._conf['group_base'],
            search_filter=search_filter,
            attributes=[self._conf['group_membership_attr']],
        )
        # operation failed or list is empty: user is not part of the group
        result = result and len(conn.response) > 0
        if not result:
            self._logger.debug('group membership failed: %s', conn.result)

        return result
    # _is_group_member()

    def _parse_conf(self):
        """
        Verify if mandatory values were set in config file with appropriate
        types and define defaults for optional values not provided.

        Args:
            None

        Raises:
            RuntimeError: in case ldap config is missing or wrong
        """
        # make sure the config section is available
        try:
            self._conf = CONF.get_config()['auth']['ldap']
        except (TypeError, KeyError):
            raise RuntimeError('No ldap configuration section found')

        # apply schema validation
        validate(self._conf, CONFIG_SCHEMA)

        # set default values for optional configuration fields
        self._conf['port'] = self._conf.get('port', 636)
        self._conf['ssl'] = self._conf.get('ssl', True)
        self._conf['username'] = self._conf.get('username')
        self._conf['password'] = self._conf.get('password')
        self._conf['timeout'] = self._conf.get('timeout', 10)

        user_attributes = self._conf.get('user_attributes', {})
        self._conf['user_attributes'] = {}
        self._conf['user_attributes']['login'] = (
            user_attributes.get('login', 'mail'))
        self._conf['user_attributes']['fullname'] = (
            user_attributes.get('fullname', 'cn'))
        # job's title is an optional attribute
        try:
            self._conf['user_attributes']['title'] = user_attributes['title']
        except KeyError:
            pass

        if self._conf.get('group_filter') is None:
            self._conf['group_filter'] = None
            self._conf['group_base'] = None
            self._conf['group_membership_attr'] = None
        else:
            if self._conf.get('group_base') is None:
                raise RuntimeError(
                    'group_filter requires group_base parameter')
            if self._conf.get('group_membership_attr') is None:
                raise RuntimeError(
                    'group_filter requires group_membership_attr parameter')

    # _parse_conf()

    def _search_user(self, conn, username):
        """
        Perform a search on the LDAP seaver for the specified user and return
        its entry.

        Args:
            conn (ldap3.Connection): connection instance
            username (str): the username to be searched

        Returns:
            dict: entry containing user attributes retrieved from ldap server
            None: in case no entry is found

        Raises:
            RuntimeError: in case one of the expected attributes is not
                          provided in the server's response
        """
        # create the user search filter based on config file values
        search_filter = '({0}={1})'.format(
            self._conf['user_attributes']['login'], username)

        if self._conf['user_filter'] is not None:
            search_filter = '(&{0}{1})'.format(
                search_filter, self._conf['user_filter'])
        self._logger.debug(
            "perform user search with filter: '%s'", search_filter)

        # search for user entry
        ret = conn.search(
            search_base=self._conf['user_base'],
            search_filter=search_filter,
            attributes=list(self._conf['user_attributes'].values()),
        )
        # user not found: return nothing
        if ret is False or not conn.response:
            self._logger.debug('user not found, result: %s', conn.result)
            return None

        # build a dict of attributes we need from the user entry
        user_attrs = {}
        for key in self._conf['user_attributes'].keys():
            ldap_key = self._conf['user_attributes'][key]
            try:
                value = conn.response[0]['attributes'][ldap_key]
            except KeyError:
                self._logger.warning(
                    'User attribute %s not found in server response: %s',
                    ldap_key, conn.response[0])
                raise RuntimeError(
                    'User attribute {} not found in server response'.format(
                        ldap_key))

            if isinstance(value, list):
                if value:
                    value = value[0]
                else:
                    value = ''
            user_attrs[key] = value

        # save the dn (distiguished name) for further operations
        user_attrs['dn'] = conn.response[0]['dn']

        return user_attrs
    # _search_user()

    def authenticate(self, username, password):
        """
        Perform a search and bind operation to authentication the user with the
        ldap server.

        Args:
            username (str): username
            password (str): password

        Returns:
            dict: entry containing the attributes defined in section
                  user_attributes of config file
            None: in case authentication fails

        Raises:
            None
        """
        # TODO: enable caching

        # open connection to ldap server and perform the operations
        with self._connect(self._conf['username'], \
            self._conf['password']) as conn:

            entry = self._search_user(conn, username)
            if entry is None:
                self._logger.warning('user %s not found', username)
                return None

            # verify group membership if activated
            if not self._is_group_member(conn, entry['dn']):
                self._logger.warning(
                    'user %s not member of allowed group(s)', username)
                return None

        # password invalid: user is not authorized
        if not self._bind(entry['dn'], password):
            self._logger.warning(
                'authentication failed for user %s (invalid password)',
                username)
            return None

        # 'dn' is ldap specific and should not be returned
        entry.pop('dn')

        self._logger.info('authentication successful for user %s', username)
        return entry
    # authenticate()

# LdapLoginManager

MANAGER = LdapLoginManager
