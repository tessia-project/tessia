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
Abstract state machine class
"""

#
# IMPORTS
#
from tessia.server.config import CONF
import abc
import sys

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#
class BaseMachine(metaclass=abc.ABCMeta):
    """
    Abstract state machine class which defines the mininum interface that any
    state machine class needs to implement.
    """
    # allowed log levels
    _LOG_LEVELS = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")
    # default log config used by state machines
    _LOG_CONFIG = {
        'version': 1,
        'formatters': {
            'default': {
                'format': '%(asctime)s | %(levelname)s | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'debugger': {
                'format': '%(asctime)s | %(levelname)s | '
                          '%(filename)s(%(lineno)s) | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': 'INFO',
                'stream': 'ext://sys.stdout'
            }
        },
        'loggers': {
            'tessia': {
                'handlers': ['console'],
                'level': 'INFO',
            }
        }
    }

    @abc.abstractmethod
    def __init__(self, params):
        """
        Receives the same parameters as those provided to parse method so in
        most cases it makes sense to call parse() to validate and convert the
        parameters here.
        """
        self.cleaning_up = False

        CONF.log_config(conf=self._LOG_CONFIG)
    # __init__()

    def _log_config(self, log_level):
        """
        Apply log configuration using the specified log level. To be used by
        concrete classes during initialization.
        """
        if not log_level:
            sys.tracebacklimit = 0
            return

        CONF.log_config(conf=self._LOG_CONFIG, log_level=log_level)
        if log_level != 'DEBUG':
            sys.tracebacklimit = 0
    # _log_config()

    @classmethod
    @abc.abstractmethod
    def parse(cls, params):
        """
        Method used to parse the state machines parameters provided by the
        user and return a dict with at least two keys 'resources' and
        'description' which are consumed by the scheduler.
        """
        raise NotImplementedError()
    # parse()

    @classmethod
    def prefilter(cls, params):
        """
        Method used to parse the state machines parameters provided by the
        user and return a similar object that would be relevant at the
        execution stage.
        This method can be used to remove or process secrets that should not
        be stored in the database.

        Args:
            params (str): state machine parameters

        Returns:
            Tuple[str, any]: state machine parameters and supplementary data
        """
        return (params, None)
    # prefilter()

    @classmethod
    def recombine(cls, params,
                  extra_vars=None         # pylint: disable=unused-argument
                 ):
        """
        Method used to restore the state machines parameters provided by the
        user and return a complete parmfile for execution stage.
        This method can be used to restore secrets that should not be stored
        in the database.

        Args:
            params (str): state machine parameters
            extra_vars (dict): additional variables extracted in prefilter

        Returns:
            str: final machine parameters
        """
        return params
    # recombine()

    @abc.abstractmethod
    def cleanup(self):
        """
        Called when the process receives a signal to terminate (SIGTERM,
        SIGHUP, SIGINT) in order to perform clean up before exiting.

        Should return 0 on successful cleanup, > 0 on failure.
        """
        raise NotImplementedError()
    # cleanup()

    @abc.abstractmethod
    def start(self):
        """
        Entry point to begin machine execution. Receives the same parameters as
        provided to parse so in most cases it makes sense to call parse() to
        validate and convert the parameters before starting execution.

        Should return 0 on successful execution, > 0 on failure.
        """
        raise NotImplementedError()
    # start()

# BaseMachine
