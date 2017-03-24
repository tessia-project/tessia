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

import os
import yaml

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class Config(object):
    """Handles parsing of the configuration file"""

    # default cfg file path
    DEFAULT_CFG = '/etc/tessia/engine.yaml'

    # config parameters dictionary
    _config_dict = None

    # modules should not instantiate the class since configuration content
    # is the same for everyone and we want a single access point to
    # configuration parameters.
    def __new__(cls, *args, **kwargs):
        """
        Constructor, enforces a singleton pattern

        Args:
            None

        Returns:
            None

        Raises:
            NotImplementedError: as the class should not be instantiated
        """
        raise NotImplementedError('Class should not be instantiated')
    # __new__()

    @classmethod
    def _parse_config(cls):
        """
        Read config file and call yaml library to parse it. Config file path is
        defined by env variable TESSIA_CFG if set, otherwise falls back to
        default.

        Args:
            None

        Returns:
            dict: parsed configuration

        Raises:
            IOError: if config file cannot be read
        """
        cls._config_file = os.environ.get('TESSIA_CFG', cls.DEFAULT_CFG)

        # virtual env active: place files there
        virtual_env = os.environ.get('VIRTUAL_ENV')
        if (virtual_env is not None and len(cls._config_file) > 0 and
                cls._config_file.startswith('/')):
            cls._config_file = '{}{}'.format(virtual_env, cls._config_file)

        try:
            config_fd = open(cls._config_file, 'r')
            config_content = config_fd.read()
            config_fd.close()
        except IOError as exc:
            msg = 'Failed to read configuration file: {}'.format(
                cls._config_file)
            raise IOError(msg) from exc

        # let any exceptions from yaml lib reach the user to give a hint of
        # what to fix
        config_dict = yaml.safe_load(config_content)

        # file is empty: set an appropriate dict type so that consumer modules
        # don't fail while accessing the dict
        if config_dict is None:
            config_dict = {}

        return config_dict
    # _parse_config()

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
    def log_config(cls, debug=False):
        """
        Apply logging configuration from config file.

        Args:
            debug (bool): in case debug level should be enabled for all
                          handlers

        Returns:
            None

        Raises:
            RuntimeError: if log configuration is missing or invalid
        """
        try:
            conf = cls.get_config()['log']
            handlers = conf['handlers']
        except (TypeError, KeyError):
            raise RuntimeError(
                'Missing or corrupt log handlers configuration section')

        # debug mode: set debug level for all handlers
        if debug:
            for _, attrs in handlers.items():
                attrs['level'] = 'DEBUG'

        dictConfig(conf)
    # log_config()

# Config

# expose the class as a constant variable for access by consumer modules
CONF = Config
