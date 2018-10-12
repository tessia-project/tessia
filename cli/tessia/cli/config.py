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
Module to handle configuration file parsing
"""

#
# IMPORTS
#
from logging.config import dictConfig
from tessia.cli.secutils import \
    is_file_private, makedirs_private, open_private_file

import click
import os
import sys
import yaml

#
# CONSTANTS AND DEFINITIONS
#
SUPPORTED_API_VERSION = 20180426
DEFAULT_CONF = {
    'log': {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '%(asctime)s|%(levelname)s|%(filename)s'
                          '(%(lineno)s)|%(message)s',
            }
        },
        'handlers': {
            'log_file': {
                'class':
                    'logging.handlers.RotatingFileHandler',
                'formatter': 'default',
                'level': 'DEBUG',
                'filename': '~/.tessia-cli/cli.log',
                'maxBytes': 10000000,
                'backupCount': 0,
            },
        },
        'loggers': {
            'tessia.cli': {
                'handlers': ['log_file'],
                'level': 'DEBUG',
            }
        },
    }
}

#
# CODE
#

class Config(object):
    """Handles parsing of the configuration file"""

    # global cfg file path
    GLOBAL_CONF_PATH = '/etc/tessia-cli/config.yaml'

    # user's cfg file path
    USER_CONF_PATH = os.path.expanduser('~/.tessia-cli/config.yaml')

    # key file path
    KEY_PATH = os.path.expanduser('~/.tessia-cli/auth.key')

    # config parameters dictionary
    _config_dict = None

    # authentication key
    _auth_key = None

    # modules should not instantiate the class since configuration content
    # is the same for everyone and we want a single access point to
    # configuration parameters.
    def __new__(cls, *args, **kwargs):
        """
        Constructor, enforces a singleton pattern

        Args:
            None

        Raises:
            NotImplementedError: as the class should not be instantiated
        """
        raise NotImplementedError('Class should not be instantiated')
    # __new__()

    @classmethod
    def _parse_config(cls):
        """
        Read config file and parse it. Create one with default values if it
        does not exist.

        Args:
            None

        Returns:
            dict: parsed configuration

        Raises:
            IOError: if config file cannot be accessed
            OSError: see IOError
            RuntimeError: in case a parsing error occurs
        """
        try:
            if not is_file_private(os.path.dirname(cls.USER_CONF_PATH)):
                click.echo(
                    'warning: configuration folder {} may be accessible for '
                    'others!'.format(os.path.abspath(cls.USER_CONF_PATH))
                )

            with open_private_file(cls.USER_CONF_PATH, 'r') as config_fd:
                config_content = config_fd.read()
        except FileNotFoundError:
            config_content = cls._set_init_config()
        except IOError as exc:
            msg = 'Failed to access configuration file: {}'.format(str(exc))
            raise IOError(msg)

        # let any exceptions from yaml lib reach the user to give a hint of
        # what to fix
        try:
            config_dict = yaml.safe_load(config_content)
        except yaml.YAMLError as exc:
            msg = 'Failed to parse configuration file'
            if hasattr(exc, 'problem_mark'):
                # pylint: disable=no-member
                msg += ', error position: line {}, column {}'.format(
                    exc.problem_mark.line+1, exc.problem_mark.column+1)
            raise RuntimeError(msg)

        # file is empty or corrupt: set an appropriate dict type so that
        # consumer modules don't fail while accessing the dict
        if not isinstance(config_dict, dict):
            config_dict = {}

        return config_dict
    # _parse_config()

    @classmethod
    def _set_init_config(cls):
        """
        Auxiliar method to create an initial client configuration for the user.

        Raises:
            IOError: if user config file can't be created
            OSError: see IOError

        Returns:
            str: initial configuration created
        """
        global_config = ''

        # look for global config file in default locations
        default_paths = [
            cls.GLOBAL_CONF_PATH,
            # check if there's a config file in prefixed locations
            # (for cases like virtualenv or deployed via setuptools)
            '{}{}'.format(sys.prefix, cls.GLOBAL_CONF_PATH)
        ]
        for global_path in default_paths:
            try:
                with open(global_path, 'r') as config_fd:
                    global_config = config_fd.read().strip()
                break
            except FileNotFoundError:
                pass
            except IOError:
                click.echo(
                    'warning: could not read global config file {}, '
                    'skipping.'.format(global_path),
                    err=True)

        global_dict = {}

        # global config found: parse its yaml content
        if global_config:
            try:
                read_dict = yaml.safe_load(global_config)
                # content is valid: use it
                if isinstance(read_dict, dict):
                    global_dict = read_dict
                # malformed content, inform user and skip it
                else:
                    click.echo(
                        'warning: malformed global config file, ignoring.',
                        err=True)
            #  malformed yaml file
            except yaml.YAMLError as exc:
                click.echo(
                    'warning: malformed global config file, ignoring.',
                    err=True)

        # create the user config file by merging the default and global confs
        content_dict = DEFAULT_CONF.copy()
        content_dict.update(global_dict)
        content_str = yaml.dump(
            content_dict, default_flow_style=False)
        try:
            makedirs_private(
                os.path.abspath(os.path.dirname(cls.USER_CONF_PATH)),
                exist_ok=True
            )
            with open_private_file(cls.USER_CONF_PATH, 'w') as config_fd:
                config_fd.write(content_str)
        except IOError as exc:
            msg = 'Failed to write configuration file: {}'.format(str(exc))
            raise IOError(msg)

        return content_str
    # _set_init_config()

    @classmethod
    def get_api_version(cls):
        """
        Return the current api version supported by this client.

        Returns:
            int: api version
        """
        return SUPPORTED_API_VERSION
    # get_api_version()

    @classmethod
    def get_cacert_path(cls):
        """
        Return the filesystem path to server's trusted ca certificate file.

        Args:
            None

        Returns:
            str: filepath

        Raises:
            None
        """
        ca_file = '/etc/tessia-cli/ca.crt'
        if os.path.exists(ca_file):
            return ca_file

        ca_file = '{}/ca.crt'.format(os.path.dirname(cls.USER_CONF_PATH))
        if os.path.exists(ca_file):
            return ca_file

        return None
    # get_cacert_path()

    @classmethod
    def get_config(cls):
        """
        Return the dict containing the parameters from config file.

        Args:
            None

        Returns:
            dict: containing conf parameters

        Raises:
            None
        """
        # dict will be None in the first call to get_config, upon subsequent
        # calls it will be cached already.
        if cls._config_dict is None:
            cls._config_dict = cls._parse_config()

        return cls._config_dict
    # get_config()

    @classmethod
    def get_key(cls):
        """
        Return the user authentication key

        Args:
            None

        Returns:
            tuple: (key_id, key_secret)
            None: if no token file exists

        Raises:
            IOError: in case token file is not accessible
            OSError: see IOError
            ValueError: in case key is not in expected format
        """
        if cls._auth_key is not None:
            return cls._auth_key

        if not is_file_private(os.path.dirname(cls.KEY_PATH)):
            click.echo(
                'warning: key folder {} may be accessible for others!'
                .format(os.path.abspath(cls.KEY_PATH)),
                err=True
            )

        try:
            key_fd = open_private_file(cls.KEY_PATH, 'r')
            key_id, key_secret = key_fd.read().strip().split(':')
            key_fd.close()
        except FileNotFoundError:
            return None
        except IOError as exc:
            msg = 'Failed to access authentication key file: {}'.format(
                str(exc))
            raise IOError(msg)
        except ValueError:
            raise ValueError('Authentication key is corrupted')

        cls._auth_key = (key_id, key_secret)
        return cls._auth_key
    # get_key()

    @classmethod
    def log_config(cls):
        """
        Apply logging configuration from config file.

        Raises:
            RuntimeError: in case log section in config file is corrupt
        """
        try:
            conf = cls.get_config()['log']
        except KeyError:
            # conf is missing: use default values
            conf = DEFAULT_CONF['log']
        try:
            handlers = conf['handlers']
        except (KeyError, TypeError):
            raise RuntimeError('log section in config file is corrupt')

        # replace tilde by user's home path
        for _, attrs in handlers.items():
            attrs['filename'] = os.path.expanduser(attrs['filename'])

        # exceptions can happen here - we let them go up since at this point we
        # wouldn't know what to do
        dictConfig(conf)
    # log_config()

    @classmethod
    def update_config(cls, new_dict):
        """
        Receive a dictionary and dump it to the configuration file.

        Args:
            new_dict (dict): new configuration values

        Returns:
            dict: containing the new configuration after re-parsing from file

        Raises:
            IOError: in case accessing configuration file fails
            OSError: see IOError
        """
        try:
            makedirs_private(
                os.path.abspath(os.path.dirname(cls.USER_CONF_PATH)),
                exist_ok=True
            )
            config_fd = open_private_file(cls.USER_CONF_PATH, 'w')
            config_content = yaml.dump(
                new_dict, default_flow_style=False)
            config_fd.write(config_content)
            config_fd.close()
        except IOError as exc:
            msg = 'Failed to access configuration file: {}'.format(str(exc))
            raise IOError(msg)

        # force a re-read of the config
        cls._config_dict = None
        return cls.get_config()
    # update_config()

    @classmethod
    def update_key(cls, key_id, key_secret):
        """
        store a new user authentication key

        Args:
            key_id (str): key id
            key_secret (str): key secret

        Returns:
            tuple: (key_id, key_secret) updated after re-reading from token
                   file

        Raises:
            IOError: in case token file is not accessible
            OSError: see IOError
        """
        try:
            key_fd = open_private_file(cls.KEY_PATH, 'w')
            key_fd.write('{}:{}'.format(key_id, key_secret))
            key_fd.close()
        except IOError as exc:
            msg = 'Failed to access authentication key file: {}'.format(
                str(exc))
            raise IOError(msg)

        # force re-read of key
        cls._auth_key = None
        return cls.get_key()
    # update_key()
# Config

# expose the class as a constant variable for access by consumer modules
CONF = Config
