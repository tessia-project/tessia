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
Unit test for api.views.auth module
"""

#
# IMPORTS
#
from base64 import b64encode
from tessia_engine.api.app import API
from tessia_engine.api.views import auth
from tessia_engine.db import models
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest.mock import patch

import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestAuth(TestCase):
    """
    Validates the authentication decorator
    """
    @classmethod
    def setUpClass(cls):
        """
        Called once before any test in this test class runs.
        """
        DbUnit.create_db()
        # at this point we can create the app as the db configuration was
        # already stablished
        API._api = None # pylint: disable=protected-access
        # the potion resource might be tied to a previous instance so we remove
        # the association
        from tessia_engine.api.resources import RESOURCES
        for resource in RESOURCES:
            resource.api = None
        API.app.config['TESTING'] = True
        cls.app = API.app.test_client()
        cls.models = models
    # setUpClass()

    def setUp(self):
        """
        Prepare mocks before each test's execution.
        """
        # prepare a mock for the login manager used to validate credentials
        patcher = patch.object(auth, 'LOGIN_MANAGER', autospec=True)
        self._mock_login_man = patcher.start()
        resp = {
            'login': 'user_x_0@domain.com',
            'fullname': 'name of user_x_0',
            'title': 'Job title of user_x_0',
        }
        self._mock_login_man.authenticate.return_value = resp
        self.addCleanup(patcher.stop)

        # mock for config file (auth section)
        patcher = patch.object(auth, 'CONF', autospec=True)
        self._mock_conf = patcher.start()
        self._mock_conf.get_config.return_value = {
            'auth': {
                'allow_user_auto_create': False,
                'realm': 'Fake realm',
            }
        }
        self.addCleanup(patcher.stop)
    # setUp()

    def test_basic_auto_fail(self):
        """
        Exercise the scenario where in a basic authentication the login manager
        validates the user but auto creation is disabled.
        """
        # set login manager to return the entry of the new user
        login_resp = {
            'login': 'new_user@domain.com',
            'fullname': 'John Doe',
            'title': 'Job title of John Doe',
        }
        self._mock_login_man.authenticate.return_value = login_resp

        # perform the request
        auth_header = 'basic {}'.format(
            b64encode(b'new_user@domain.com:a').decode('ascii'))
        resp = self.app.get(
            '/users',
            headers={'Authorization': auth_header}
        )

        # validate the response
        self.assertEqual(401, resp.status_code) # pylint: disable=no-member
        data = json.loads(resp.data.decode('ascii')) # pylint: disable=no-member
        self.assertEqual(
            data['message'],
            'User authenticated but not registered in database')
    # test_basic_auto_fail()

    def test_basic_auto_success(self):
        """
        Exercise the scenario where a basic authentication works and the user
        is automatically created in the database.
        """
        # set login manager to return the entry of the new user
        login_resp = {
            'login': 'new_user@domain.com',
            'fullname': 'John Doe',
            'title': 'Job title of John Doe',
        }
        self._mock_login_man.authenticate.return_value = login_resp
        # set config to allow user auto creation
        conf = self._mock_conf.get_config.return_value
        conf['auth']['allow_user_auto_create'] = True

        # perform the request
        auth_header = 'basic {}'.format(
            b64encode(b'new_user@domain.com:a').decode('ascii'))
        resp = self.app.get(
            '/users',
            headers={'Authorization': auth_header}
        )

        # validate a 200 ok response
        self.assertEqual(200, resp.status_code) # pylint: disable=no-member
        # validate that the user was created in database
        user = self.models.User.query.filter_by(
            login=login_resp['login']).one()
        self.assertEqual(user.name, login_resp['fullname'])
        self.assertEqual(user.title, login_resp['title'])
    # test_basic_auto_success()

    def test_basic_fail(self):
        """
        Exercise the scenario where a basic authentication fails.
        """
        # make the login manager fail to authenticate
        self._mock_login_man.authenticate.return_value = None

        # perform request
        auth_header = 'basic {}'.format(
            b64encode(b'user_x_0@domain.com:a').decode('ascii'))
        resp = self.app.get(
            '/users',
            headers={'Authorization': auth_header}
        )

        # validate a 401 unauthorized was received
        self.assertEqual(401, resp.status_code) # pylint: disable=no-member
    # test_basic_fail()

    def test_basic_noauto_success(self):
        """
        Exercise the scenario where a basic authentication with an existing
        user works.
        """
        # perform the request
        auth_header = 'basic {}'.format(
            b64encode(b'user_x_0@domain.com:a').decode('ascii'))
        resp = self.app.get(
            '/users',
            headers={'Authorization': auth_header}
        )

        # validate a 200 ok was received
        self.assertEqual(200, resp.status_code) # pylint: disable=no-member
    # test_basic_noauto_success()

    def test_basic_wrong(self):
        """
        Exercise the scenario where a basic authentication has a wrong
        syntax in the authentication header.
        """
        for wrong in ('basic', 'basic x', 'basic 1::2', 'basic ::', 'basic :'):
            # perform the request
            resp = self.app.get(
                '/users',
                headers={'Authorization': wrong}
            )

            # validate a 400 badrequest or 401 unauthorized
            self.assertIn(resp.status_code, (400, 401)) # pylint: disable=no-member
    # test_key_wrong()

    def test_key_fail(self):
        """
        Exercise the scenario where a key based authentication fails.
        """
        # perform the request
        resp = self.app.get(
            '/users',
            headers={'Authorization': 'x-key 1:1'}
        )

        # validate a 401 unauthorized
        self.assertEqual(401, resp.status_code) # pylint: disable=no-member
    # test_key_fail()

    def test_key_success(self):
        """
        Exercise the scenario where a key based authentication works.
        """
        # retrieve the key entry in db
        key = self.models.UserKey.query.filter_by(
            user='user_x_0@domain.com').one()

        # perform the request
        auth_header = 'x-key {}:{}'.format(key.key_id, key.key_secret)
        resp = self.app.get(
            '/users',
            headers={'Authorization': auth_header}
        )

        # validate a 200 ok was received
        self.assertEqual(200, resp.status_code) # pylint: disable=no-member
    # test_key_success()

    def test_key_wrong(self):
        """
        Exercise the scenario where a key based authentication has a wrong
        syntax in the authentication header.
        """
        for wrong in ('x-key', 'x-key x', 'x-key 1::2', 'x-key ::', 'x-key :'):
            # perform the request
            resp = self.app.get(
                '/users',
                headers={'Authorization': wrong}
            )

            # validate a 400 badrequest or 401 unauthorized
            self.assertIn(resp.status_code, (400, 401)) # pylint: disable=no-member
    # test_key_wrong()

    def test_no_auth(self):
        """
        Exercise the scenario where no authentication header is provided.
        """
        # perform the request
        resp = self.app.get(
            '/users',
            headers={}
        )

        # validate a 401 unauthorized
        self.assertEqual(resp.status_code, 401) # pylint: disable=no-member
        # check that the error message is correct
        data = json.loads(resp.data.decode('ascii')) # pylint: disable=no-member
        self.assertEqual(
            data['message'],
            'You need to provide credentials to access this resource.')

    # test_no_auth()

    def test_scheme_wrong(self):
        """
        Exercise the scenario where an invalid scheme is used in the
        authentication header.
        """
        for wrong in ('something_wrong', 'something_wrong with_cred'):
            # perform the request
            resp = self.app.get(
                '/users',
                headers={'Authorization': wrong}
            )

            # validate a 401 unauthorized
            self.assertEqual(resp.status_code, 401) # pylint: disable=no-member
    # test_scheme_wrong()

# TestAuth
