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
from unittest.mock import Mock
from unittest.mock import patch

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

    @staticmethod
    def _create_open_mock(mock_cls, option):
        """
        Helper function to create a mock to simulate reading the config file

        Args:
            mock_cls (Mock): Mock object replacing builtin open()
            option (str): string 'good' for a valid config file content or
                          'bad' for invalid content

        Returns:
            Mock: representing a file-like object

        Raises:
            RuntimeError: if the wrong option is provided
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

        # create a mock which returns a valid config content
        mock_open = Mock()
        mock_open.read.return_value = content
        mock_cls.return_value = mock_open

        return mock_open
    # _create_open_mock()

    def setUp(self):
        """
        Clear the cfg environment variable and cached dictionary before each
        test.
        """
        # make sure variable was not inherited from calling environment or
        # previous test
        config.os.environ.pop('TESSIA_CFG', None)
        config.os.environ.pop('VIRTUAL_ENV', None)

        # force re-read of file
        # pylint: disable=protected-access
        config.CONF._config_dict = None
    # setUp()

    def test_create_config_obj(self):
        """
        Test if the Config class correctly fails to be instantiated

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: if class instantiates fails to raise exception
        """
        self.assertRaises(NotImplementedError, config.Config)
    # test_create_config_obj()

    @patch('builtins.open')
    def test_bad_file_default_path(self, mock_open_cls):
        """
        Exercise parsing configuration file from path set by env variable

        Args:
            mock_open_cls (Mock): Mock object replacing builtin open()

        Returns:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        # set the mock to return invalid config content
        self._create_open_mock(mock_open_cls, 'bad')

        # perform the action and validate result
        self.assertRaises(yaml.scanner.ScannerError,
                          config.CONF.get_config)

    # test_bad_file_default_path()

    @patch('builtins.open')
    def test_bad_log_content(self, mock_open_cls):
        """
        Exercise parsing log configuration with invalid content

        Args:
            mock_open_cls (Mock): Mock object replacing builtin open()

        Returns:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        self._create_open_mock(mock_open_cls, 'log_bad')

        # perform the action
        with self.assertRaises(RuntimeError):
            config.CONF.log_config()

    # test_bad_log_content()

    @patch('builtins.open')
    def test_bad_path(self, mock_open_cls):
        """
        Exercise parsing configuration file from path set by env variable

        Args:
            mock_open_cls (mock): Mock object replacing builtin open()

        Returns:
            None

        Raises:
            AssertionError: if the assertion call fails
        """
        # set mock to raise error on file access
        mock_open_cls.side_effect = IOError('No such file or directory')

        with self.assertRaisesRegex(
            IOError, '^.* {} *$'.format(config.CONF.DEFAULT_CFG)):
            config.CONF.get_config()
    # test_bad_path()

    @patch('builtins.open')
    def test_empty_file(self, mock_open_cls):
        """
        Exercise parsing an empty configuration file

        Args:
            mock_open_cls (Mock): object replacing builtin open()

        Returns:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        # set the mock to return invalid config content
        self._create_open_mock(mock_open_cls, 'empty')

        # perform the action and validate result
        self.assertEqual({}, config.CONF.get_config())
    # test_empty_file()

    @patch('builtins.open')
    def test_good_file_def_path_caching(self, mock_open_cls):
        """
        Exercise parsing configuration file from default path and caching

        Args:
            mock_open_cls (Mock): Mock object replacing builtin open()

        Returns:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        mock_open = self._create_open_mock(mock_open_cls, 'good')

        # perform the action
        cfg_dict = config.CONF.get_config()

        # validate values
        self.assertEqual(cfg_dict.get('some_key'), 'some_value')
        self.assertEqual(cfg_dict.get('some-other-key'), 'some-other-value')

        # validate behavior
        mock_open_cls.assert_called_with(config.CONF.DEFAULT_CFG, 'r')
        mock_open.read.assert_called_once_with()
        mock_open.close.assert_called_once_with()

        # also test caching of configuration
        mock_open.read.reset_mock()

        # fetch data again to make cache work
        cfg_dict = config.CONF.get_config()

        # confirm that file was not read again
        mock_open.read.assert_not_called()

    # test_good_file_def_path_caching()

    @patch.object(config, 'os')
    @patch('builtins.open')
    def test_good_file_env_path(self, mock_open_cls, mock_os):
        """
        Exercise parsing configuration file from path set by env variable

        Args:
            mock_open_cls (Mock): Mock object replacing builtin open()
            mock_os (Mock): object replacing os module

        Returns:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        mock_open = self._create_open_mock(mock_open_cls, 'good')
        dummy_path = '/dummy/path.yaml'
        def env_get(key, default=None):
            """Stub for dict.get"""
            if key == 'TESSIA_CFG':
                return dummy_path
            elif key == 'VIRTUAL_ENV':
                return '/some/virtual/env'
            return default
        # env_get()
        mock_os.environ.get.side_effect = env_get

        # perform the action
        cfg_dict = config.CONF.get_config()

        # validate values
        self.assertEqual(cfg_dict.get('some_key'), 'some_value')
        self.assertEqual(cfg_dict.get('some-other-key'), 'some-other-value')

        # validate behavior
        mock_open_cls.assert_called_with('/some/virtual/env' + dummy_path, 'r')
        mock_open.read.assert_called_once_with()
        mock_open.close.assert_called_once_with()

    # test_good_file_env_path()

    @patch('builtins.open')
    def test_good_log_content(self, mock_open_cls):
        """
        Exercise parsing log configuration with valid content

        Args:
            mock_open_cls (Mock): Mock object replacing builtin open()

        Returns:
            None

        Raises:
            AssertionError: if any of the assertion calls fails
        """
        self._create_open_mock(mock_open_cls, 'log_good')

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
