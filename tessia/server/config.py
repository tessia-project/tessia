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
from copy import deepcopy
from logging.config import dictConfig

import os
import sys
import yaml

#
# CONSTANTS AND DEFINITIONS
#
# 'debugger' formatter to use when not defined in config file
DEBUGGER_FORMATTER = {
    'datefmt': '%Y-%m-%d %H:%M:%S',
    'format': '%(asctime)s | %(levelname)s | %(filename)s(%(lineno)s) '
              '| %(message)s'
}

#
# CODE
#


class Config:
    """Handles parsing of the configuration file"""

    # default cfg file path
    DEFAULT_CFG = '/etc/tessia/server.yaml'

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
            OSError: if config file cannot be read
            ValueError: if file content evaluates to invalid content
        """
        def _read_file(file_path):
            """Auxiliar method to read the content of a file"""
            with open(file_path, 'r') as file_fd:
                file_content = file_fd.read()
            return file_content
        # _read_file()

        cls._config_file = os.environ.get('TESSIA_CFG')
        # env variable defined: it takes precedence
        if cls._config_file is not None:
            try:
                config_content = _read_file(cls._config_file)
            except IOError as exc:
                msg = 'Could not read config file from {}'.format(
                    cls._config_file)
                raise IOError(msg) from exc
        # no env variable: look at standard locations
        else:
            # try to read conf file from absolute path
            cls._config_file = cls.DEFAULT_CFG
            try:
                config_content = _read_file(cls._config_file)
            except IOError:
                # retry at prefixed locations (virtualenv or installed
                # by setuptools)
                cls._config_file = '{}{}'.format(sys.prefix, cls.DEFAULT_CFG)
                try:
                    config_content = _read_file(cls._config_file)
                except IOError as exc:
                    msg = 'Could not read config file from {}'.format(
                        ' , '.join([cls.DEFAULT_CFG, cls._config_file]))
                    raise IOError(msg) from exc

        # let any exceptions from yaml lib reach the user to give a hint of
        # what to fix
        yaml_config = yaml.safe_load(config_content)
        config_dict = {}

        # file is empty: set an appropriate dict type so that consumer modules
        # don't fail while accessing the dict
        if (yaml_config is None or
                (isinstance(yaml_config, str) and not yaml_config.strip())):
            config_dict = {}
        elif isinstance(yaml_config, dict):
            config_dict.update(yaml_config)
        else:
            raise ValueError('Invalid configuration file content')

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
    def log_config(cls, conf=None, log_level=None):
        """
        Apply logging configuration from config file.

        Args:
            conf (dict): log configuration to be applied; if not specified
                         use from config file
            log_level (str): custom log level to apply to all loggers and
                             handlers

        Raises:
            ValueError: if log configuration is missing or invalid
        """
        server_config=cls.get_config().get('log')
        if server_config:
            try:
                conf = server_config
            except (TypeError, KeyError) as exc:
                raise ValueError(
                     'Missing or corrupt log configuration section')

        if not isinstance(conf, dict):
            raise ValueError('Invalid format for log configuration section')
        conf = deepcopy(conf)

        try:
            handlers = conf['handlers']
            loggers = conf['loggers']
        except KeyError as exc:
            raise ValueError(
                "Missing log configuration section '{}'".format(exc.args[0]))

        # custom log level: apply it for all loggers and handlers
        if log_level:
            # debug level: use special formatter
            if log_level == 'DEBUG':
                formatters = conf.setdefault('formatters', {})
                try:
                    formatters['debugger']
                except KeyError:
                    formatters['debugger'] = DEBUGGER_FORMATTER

            for handler in handlers.values():
                handler['level'] = log_level
                if log_level == 'DEBUG':
                    handler['formatter'] = 'debugger'
            for logger in loggers.values():
                logger['level'] = log_level

        dictConfig(conf)
    # log_config()
# Config


# expose the class as a constant variable for access by consumer modules
CONF = Config
