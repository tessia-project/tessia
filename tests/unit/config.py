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
Unit test for config module
"""

#
# IMPORTS
#
from tessia_engine import config
from unittest import TestCase
from unittest import mock
from unittest.mock import patch

import sys
import yaml

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class TestConfig(TestCase):
    """
    Unit test for the config module.
    """

    def _set_open_mock(self, option):
        """
        Helper function to setup a mock to simulate reading the config file

        Args:
            option (str): string 'good' for a valid config file content,
                          'bad' for invalid content, 'empty',
                          'log_good' for a valid logging config, or
                          'log_bad' for an invalid logging config

        Raises:
            RuntimeError: if an unsupported option is provided
        """
        if option == 'good':
            content = "some_key: some_value\n"
            content += "some-other-key: some-other-value"
        elif option == 'bad':
            content = "| some_variable: some-value"
        elif option == 'log_good':
            content = """
log:
  version: 1
  disable_existing_loggers: false
  formatters:
    default: {format: '%(asctime)s|%(levelname)s|%(filename)s(%(lineno)s)|%(message)s'}
  handlers:
    console:
      class: logging.StreamHandler
      formatter: default
      level: INFO
      stream: ext://sys.stderr
  loggers:
    tessia_engine:
      handlers: [console]
"""
        elif option == 'log_bad':
            content = """
log:
  - handlers
"""
        elif option == 'empty':
            content = ''
        else:
            raise RuntimeError("unrecognized option '{}'".format(option))

        self._mock_open_fd.read.return_value = content
    # _set_open_mock()

    def setUp(self):
        """
        Clear the cfg environment variable and cached dictionary before each
        test.
        """
        # make sure variable was not inherited from calling environment or
        # previous test
        config.os.environ.pop('TESSIA_CFG', None)

        # patch the open function
        patcher = patch.object(config, 'open')
        self._mock_open_method = patcher.start()
        self.addCleanup(patcher.stop)
        # the read of file descriptor mock is configured by each testcase
        self._mock_open_fd = mock.MagicMock()
        self._mock_open_method.return_value = self._mock_open_fd
        self._mock_open_fd.__enter__.return_value = self._mock_open_fd

        # force re-read of file
        config.CONF._config_dict = None
    # setUp()

    def test_bad_content(self):
        """
        Exercise parsing configuration file from path set by env variable

        Args:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        # set the mock to return invalid config content
        self._set_open_mock('bad')

        # perform the action and validate result
        self.assertRaises(yaml.scanner.ScannerError,
                          config.CONF.get_config)

    # test_bad_content()

    def test_bad_log_content(self):
        """
        Exercise parsing log configuration with invalid content

        Args:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        # set the mock to return invalid log config content
        self._set_open_mock('log_bad')

        # perform the action
        with self.assertRaises(RuntimeError):
            config.CONF.log_config()

    # test_bad_log_content()

    def test_bad_default_paths(self):
        """
        Exercise files in the standard locations that are not readable.

        Args:
            None

        Raises:
            AssertionError: if the assertion call fails
        """
        # set mock to raise error on file access
        self._mock_open_method.side_effect = [
            PermissionError("[Errno 13] Permission denied: '{}'".format(
                config.CONF.DEFAULT_CFG)),
            FileNotFoundError('No such file or directory')
        ]

        prefixed_cfg_path = '{}{}'.format(sys.prefix, config.CONF.DEFAULT_CFG)
        paths_list = ' , '.join([config.CONF.DEFAULT_CFG, prefixed_cfg_path])
        expected_msg = 'Could not read config file from {} *$'.format(
            paths_list)
        with self.assertRaisesRegex(IOError, expected_msg):
            config.CONF.get_config()
    # test_bad_default_paths()

    @patch.object(config.os.environ, 'get')
    def test_bad_env_path(self, mock_get):
        """
        Exercise a file defined by env variable that is not readable.

        Args:
            mock_get (Mock): mock replacing os.environ.get function

        Returns:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        dummy_path = '/dummy/path.yaml'
        def env_get(key, default=None):
            """Stub for dict.get"""
            if key == 'TESSIA_CFG':
                return dummy_path
            return default
        # env_get()
        mock_get.side_effect = env_get

        # set mock to raise error on file access
        self._mock_open_method.side_effect = FileNotFoundError(
            'No such file or directory')

        # perform the action
        expected_msg = 'Could not read config file from {} *$'.format(
            dummy_path)
        with self.assertRaisesRegex(IOError, expected_msg):
            config.CONF.get_config()

    # test_bad_env_path()

    def test_create_config_obj(self):
        """
        Test if the Config class correctly fails to be instantiated

        Args:
            None

        Raises:
            AssertionError: if class instantiates fails to raise exception
        """
        self.assertRaises(NotImplementedError, config.Config)
    # test_create_config_obj()

    def test_empty_file(self):
        """
        Exercise parsing an empty configuration file

        Args:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        # set the mock to return empty config content
        self._set_open_mock('empty')

        # perform the action and validate result
        self.assertEqual({}, config.CONF.get_config())
    # test_empty_file()

    def test_good_default_path_caching(self):
        """
        Exercise parsing configuration file from default path and caching

        Args:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        self._set_open_mock('good')

        # perform the action
        cfg_dict = config.CONF.get_config()

        # validate values
        self.assertEqual(cfg_dict.get('some_key'), 'some_value')
        self.assertEqual(cfg_dict.get('some-other-key'), 'some-other-value')

        # validate behavior
        self._mock_open_method.assert_called_with(config.CONF.DEFAULT_CFG, 'r')
        self._mock_open_fd.read.assert_called_once_with()
        self._mock_open_fd.__exit__.assert_called_once_with(None, None, None)

        # also test caching of configuration
        self._mock_open_fd.read.reset_mock()

        # fetch data again to make cache work
        cfg_dict = config.CONF.get_config()

        # confirm that file was not read again
        self._mock_open_fd.read.assert_not_called()

    # test_good_default_path_caching()

    def test_good_default_prefix_path_caching(self):
        """
        Exercise parsing configuration file from prefixed default path and
        caching.

        Args:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        self._set_open_mock('good')
        # set mock to raise error on file access
        self._mock_open_method.side_effect = [
            PermissionError("[Errno 13] Permission denied: '{}'".format(
                config.CONF.DEFAULT_CFG)),
            self._mock_open_fd
        ]

        # perform the action
        cfg_dict = config.CONF.get_config()

        # validate values
        self.assertEqual(cfg_dict.get('some_key'), 'some_value')
        self.assertEqual(cfg_dict.get('some-other-key'), 'some-other-value')

        # validate behavior
        prefixed_cfg_path = '{}{}'.format(sys.prefix, config.CONF.DEFAULT_CFG)
        calls = [
            mock.call(config.CONF.DEFAULT_CFG, 'r'),
            mock.call(prefixed_cfg_path, 'r')
        ]
        self._mock_open_method.assert_has_calls(calls)
        self._mock_open_fd.read.assert_called_once_with()
        self._mock_open_fd.__exit__.assert_called_once_with(None, None, None)

        # also test caching of configuration
        self._mock_open_fd.read.reset_mock()

        # fetch data again to make cache work
        cfg_dict = config.CONF.get_config()

        # confirm that file was not read again
        self._mock_open_fd.read.assert_not_called()

    # test_good_default_prefix_path_caching()

    @patch.object(config.os.environ, 'get')
    def test_good_env_path(self, mock_get):
        """
        Exercise parsing configuration file from path set by env variable

        Args:
            mock_get (Mock): mock replacing os.environ.get function

        Returns:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        self._set_open_mock('good')
        dummy_path = '/dummy/path.yaml'
        def env_get(key, default=None):
            """Stub for dict.get"""
            if key == 'TESSIA_CFG':
                return dummy_path
            return default
        # env_get()
        mock_get.side_effect = env_get

        # perform the action
        cfg_dict = config.CONF.get_config()

        # validate values
        self.assertEqual(cfg_dict.get('some_key'), 'some_value')
        self.assertEqual(cfg_dict.get('some-other-key'), 'some-other-value')

        # validate behavior
        self._mock_open_method.assert_called_with(dummy_path, 'r')
        self._mock_open_fd.read.assert_called_once_with()
        self._mock_open_fd.__exit__.assert_called_once_with(None, None, None)
    # test_good_env_path()

    def test_good_log_content(self):
        """
        Exercise parsing log configuration with valid content

        Args:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        self._set_open_mock('log_good')

        # perform the action - we don't use a mock to exercise the call to the
        # log library
        config.CONF.log_config()
        config.CONF.log_config(True)

        # now use a mock to make sure debug was enabled
        patcher = patch.object(config, 'dictConfig')
        mock_config = patcher.start()
        self.addCleanup(patcher.stop)
        config.CONF.log_config(True)

        conf = mock_config.call_args[0][0]
        for _, attr in conf['handlers'].items():
            self.assertEqual(attr['level'], 'DEBUG')
    # test_good_log_content()

# TestConfig
