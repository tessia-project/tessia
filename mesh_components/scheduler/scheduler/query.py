# Copyright 2021 IBM Corp.
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
Query external services
"""

#
# IMPORTS
#
import requests

from .errors import NotAuthorized

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


class ConnectedQuery:
    """Common session operations"""

    def __init__(self, conf) -> None:
        self._conf = conf
        self._session = requests.session()

        # apply TLS connection configuration
        if self._conf.get('no-tls-verify'):
            self._session.verify = False
        elif self._conf.get('ca-bundle'):
            self._session.verify = self._conf.get('ca-bundle')
        if self._conf.get('client-cert'):
            self._session.cert = self._conf.get('client-cert')
    # __init__()
# ConnectedQuery


class PermissionManagerQueryFactory:
    """Create a query class according to configuration"""
    def __new__(cls, conf):
        if conf:
            instance = object.__new__(PermissionManagerQuery)
            instance.__init__(conf)
        else:
            instance = object.__new__(PermissionManagerQueryStub)
            instance.__init__()

        return instance
    # __new__()
# PermissionManagerQueryFactory


class PermissionManagerQueryStub:
    """Permision manager stub"""

    def assert_use_resources(self, subject, objects):
        """Allow all actions"""
    # assert_use_resources()
# PermissionManagerQueryStub


class PermissionManagerQuery(PermissionManagerQueryStub, ConnectedQuery):
    """Query permissions"""

    def assert_use_resources(self, subject, objects):
        """
        Submit a permission query

        Raise an exception if not enough permissions
        """
        url = f'{self._conf["url"]}/v1/is-action-permissible'
        response = self._session.post(url, json={
            'subject': subject,
            'action': 'use',
            'resources': objects
        }).json()
        if not response.get('action-allowed', False):
            subject_fmt = (subject['login']
                           if subject['login'] else '<anonymous>')
            msg = ', '.join([obj['identifier'] for obj in objects[:5]])
            if len(objects) > 5:
                msg += f' and {len(objects) - 5} more'
            raise NotAuthorized(f'No permission for {subject_fmt} to use {msg}')
    # assert_use_resources()
# PermissionManagerQuery


class ResourceManagerQueryFactory:
    """Create a query class according to configuration"""
    def __new__(cls, conf):
        if conf:
            instance = object.__new__(ResourceManagerQuery)
            instance.__init__(conf)
        else:
            instance = object.__new__(ResourceManagerQueryStub)
            instance.__init__()

        return instance
    # __new__()
# ResourceManagerQueryFactory


class ResourceManagerQueryStub:
    """Resource manager stub"""

    def get_user_info(self, user_login) -> dict:
        """Get user information"""
        return {
            'login': user_login,
            'group_roles': []
        }
    # get_user_info()

    def get_resources(self, resources) -> list:
        """Get extended information about resources"""
        return [
            {
                'identifier': item['identifier'],
                'resource': {},
                'groups': [],
                'owner': {
                    'login': '',
                    'group_roles': []
                }
            } for item in resources
        ]
    # get_resources()
# ResourceManagerQueryStub


class ResourceManagerQuery(ResourceManagerQueryStub, ConnectedQuery):
    """Query resource manager"""
# ResourceManagerQuery
