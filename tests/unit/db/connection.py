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
Unit test for the db.connection module
"""

#
# IMPORTS
#
from tessia.server.db import connection
from unittest import TestCase
from unittest.mock import patch
from unittest.mock import sentinel
from unittest.mock import Mock

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class TestConnection(TestCase):
    """
    Unit test for the db.connection module
    """

    @patch.object(connection, 'scoped_session', autospec=True)
    @patch.object(connection, 'sessionmaker', autospec=True)
    @patch.object(connection, 'create_engine', autospec=True)
    @patch.object(connection, 'CONF', autospec=True)
    def test_conn_valid_url(self, mock_conf, mock_create,
                            mock_session_maker, mock_scoped_session):
        """
        Exercise connecting to sa engine with a valid url from config file

        Args:
            mock_conf (Mock): Mock object replacing config.Config
            mock_create (Mock): Mock object replacing create_engine
            mock_session_maker (Mock): Mock object replacing sessionmaker
            mock_scoped_session (Mock): Mock object replacing scoped_session

        Raises:
            AssertionError: if any of the assertion calls fail
        """
        # create a valid configuration file and assign it to the mock
        config = {
            'db': {
                'url': 'postgresql://user:passwd@localhost/dbname',
            }
        }
        mock_conf.get_config.return_value = config

        # set sa mocks so that we can check behavior later
        mock_create.return_value = sentinel.sa_engine
        mock_session_maker.return_value = sentinel.sa_session
        mock_scoped_session_obj = Mock()
        mock_scoped_session_obj.query_property.return_value = sentinel.query
        mock_scoped_session.return_value = mock_scoped_session_obj

        # force a reconnection because other modules might have connected
        # before
        connection.MANAGER._conn = None

        # verify the result
        self.assertIs(connection.MANAGER.engine, sentinel.sa_engine)
        self.assertIs(connection.MANAGER.session, mock_scoped_session_obj)

        # verify that module behaved as expected
        mock_create.assert_called_with(
            config['db']['url'])
        mock_session_maker.assert_called_with(bind=sentinel.sa_engine)
        mock_scoped_session.assert_called_with(
            mock_session_maker.return_value)

        # try a second instance of the internal class
        self.assertRaises(RuntimeError, connection._DbManager)
    # test_conn_valid_url()

    @patch.object(connection, 'CONF', autospec=True)
    def test_conn_missing_url(self, mock_conf):
        """
        Exercise connecting to sa engine with an invalid url from config file

        Args:
            mock_conf (Mock): Mock object replacing config.Config

        Raises:
            AssertionError: if any of assertion calls fail
        """
        mock_conf.get_config.return_value = {}

        # force a reconnection because other modules might have connected
        # before
        connection.MANAGER._conn = None
        self.assertRaises(RuntimeError, lambda: connection.MANAGER.session)
    # test_conn_missing_url()

# TestConnection
