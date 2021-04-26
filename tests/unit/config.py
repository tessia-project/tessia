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
from tessia.server import config
from tempfile import NamedTemporaryFile
from unittest import TestCase
from unittest import mock
from unittest.mock import patch

import os
import sys
import yaml

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class EnvConfig:
    """Simple helper class to set config content in a temp file"""

    def __init__(self):
        self._orig_var = None
        self._temp_tessia_cfg = None
    # __init__()

    def start(self, content):
        """
        Apply the passed config content to the environment.

        Args:
            content (str): valid config file content
        """
        # multiple patches to many modules would be needed to make sure all of
        # them point to the same config mock. Instead we use the env variable
        # pointing to a temp file to achieve global setup.
        self._orig_var = os.environ.get('TESSIA_CFG')
        self._temp_tessia_cfg = NamedTemporaryFile(mode='w') # pylint: disable=consider-using-with
        os.environ['TESSIA_CFG'] = self._temp_tessia_cfg.name
        # set the config file content
        self._temp_tessia_cfg.write(yaml.dump(content))
        self._temp_tessia_cfg.flush()
        # force module to re-read file
        config.CONF._config_dict = None
    # start()

    def stop(self):
        """
        Stop serving the config file content previously set with start.
        """
        # not started: nothing to do
        if self._temp_tessia_cfg is None:
            return

        if self._orig_var is None:
            os.environ.pop('TESSIA_CFG', None)
        else:
            os.environ['TESSIA_CFG'] = self._orig_var
            self._orig_var = None
        self._temp_tessia_cfg.close()
        self._temp_tessia_cfg = None
        # prevent module from reusing our content
        config.CONF._config_dict = None
    # stop()

    def update(self, content):
        """
        Update the content of a temp file already in place.

        Args:
            content (str): valid config file content

        Raises:
            RuntimeError: in case start() was not previously called.
        """
        if self._temp_tessia_cfg is None:
            raise RuntimeError('Config file not applied yet')
        self._temp_tessia_cfg.seek(0)
        self._temp_tessia_cfg.write(yaml.dump(content))
        self._temp_tessia_cfg.flush()
        # force module to re-read file
        config.CONF._config_dict = None
    # update()
# EnvConfig


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
                          else use the string provided as content

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
  formatters:
    default:
      format: '%(asctime)s | %(levelname)s | %(message)s'
      datefmt: '%Y-%m-%d %H:%M:%S'
  handlers:
    console:
      class: logging.StreamHandler
      formatter: default
      level: INFO
      stream: ext://sys.stdout
  loggers:
    tessia:
      handlers: [console]
      level: INFO
"""
        elif option == 'log_bad':
            content = """
log:
  - handlers
"""
        elif option == 'empty':
            content = ''
        else:
            content = option

        self._mock_open_fd.read.return_value = content
        # force re-read of file
        config.CONF._config_dict = None
    # _set_open_mock()

    def setUp(self):
        """
        Clear the cfg environment variable and cached dictionary before each
        test.
        """
        # make sure variable was not inherited from calling environment or
        # previous test
        orig_cfg_var = config.os.environ.get('TESSIA_CFG')

        def restore_var():
            """Helper to restore original variable value"""
            if orig_cfg_var is None:
                config.os.environ.pop('TESSIA_CFG', None)
            else:
                config.os.environ['TESSIA_CFG'] = orig_cfg_var
            config.CONF._config_dict = None
        self.addCleanup(restore_var)
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
        Exercise parsing configuration file with unparseable content

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

        # set the mock to return a random string
        self._set_open_mock(' random-string ')

        # perform the action and validate result
        with self.assertRaisesRegex(
                ValueError, 'Invalid configuration file content'):
            config.CONF.get_config()

        # set the mock to return a list
        self._set_open_mock('- bla')

        # perform the action and validate result
        with self.assertRaisesRegex(
                ValueError, 'Invalid configuration file content'):
            config.CONF.get_config()

    # test_bad_content()

    def test_bad_log_content(self):
        """
        Exercise parsing log configuration with invalid content

        Args:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        # log key missing from config
        self._set_open_mock('wrong_key_instead_of_log:')

        # perform the action
        with self.assertRaisesRegex(
                ValueError, 'Missing or corrupt log configuration section'):
            config.CONF.log_config()

        # log key present but in wrong format (a list)
        self._set_open_mock('log_bad')

        # perform the action
        with self.assertRaisesRegex(
                ValueError, 'Invalid format for log configuration section'):
            config.CONF.log_config()

        # log key present but 'handlers' key missing
        self._set_open_mock('log:\n  loggers:')

        # perform the action
        with self.assertRaisesRegex(
                ValueError, "Missing log configuration section 'handlers'"):
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

        # set the mock to return a blank
        self._set_open_mock(' ')

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
        config.CONF.log_config(log_level='DEBUG')

        # now use a mock to validate behavior
        patcher = patch.object(config, 'dictConfig')
        mock_dict_config = patcher.start()
        self.addCleanup(patcher.stop)
        config.CONF.log_config()

        conf = mock_dict_config.call_args[0][0]
        for key in ('handlers', 'loggers'):
            for item in conf[key].values():
                self.assertEqual(item['level'], 'INFO')

        # custom log level - make sure it was applied
        mock_dict_config.reset()
        config.CONF.log_config(log_level='DEBUG')

        conf = mock_dict_config.call_args[0][0]
        for key in ('handlers', 'loggers'):
            for item in conf[key].values():
                self.assertEqual(item['level'], 'DEBUG')
    # test_good_log_content()
# TestConfig
