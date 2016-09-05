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
import abc

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
    NAME = 'base'

    @abc.abstractmethod
    def __init__(self, params):
        """
        Receives the same parameters as the one provided to parse method so in
        most cases it makes sense to call parse() to validate and convert the
        parameters here.
        """
        pass
    # __init__()

    @staticmethod
    @abc.abstractmethod
    def parse(params):
        """
        Method used to parse the state machines parameters provided by the
        user and return a dict with at least two keys 'resources' and
        'description' which are consumed by the scheduler.
        """
        raise NotImplementedError()
    # parse()

    @abc.abstractmethod
    def cleanup(self):
        """
        Called when the process receives a signal to terminate (SIGTERM,
        SIGHUP, SIGINT) in order to perform clean up before exiting.
        """
        raise NotImplementedError()
    # cleanup()

    @abc.abstractmethod
    def start(self):
        """
        Entry point to begin machine execution. Receives the same parameters as
        provided to parse so in most cases it makes sense to call parse() to
        validate and convert the parameters before starting execution.
        """
        raise NotImplementedError()
    # start()

# BaseMachine
