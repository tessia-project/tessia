# Copyright 2024, 2024 IBM Corp.
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
Interface definition for run environments
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
class EnvBase(metaclass=abc.ABCMeta):
    """
    Abstract class to define the environment interface to be implemented by
    specialized classes.
    """

    @abc.abstractmethod
    def build(self):
        """
        Build environment

        Raises:
            NotImplementedError: as it has to be implemented in concrete
                                 classes
        """
        raise NotImplementedError()
    # build()

    @abc.abstractmethod
    def run(self, repo_url, repo_dir, tests, runlocal, preexec, postexec):
        """
        Start execution using given directory

        Args:
            repo_url (str): URL to an git repository.
            repo_dir (str): TemporaryDirectory with configuration files which
                            are transferred to the run environment.
            tests (str): tests to be executed.
            runlocal (str): execute tela in docker or on remote
            preexec (dict): preexec script with optional arguments
            postexec (dict): postexec script with optional arguments

        Raises:
            NotImplementedError: as it has to be implemented in concrete
                                 classes
        """
        raise NotImplementedError()
    # run()

    @abc.abstractmethod
    def cleanup(self):
        """
        Cleanup environment

        Raises:
            NotImplementedError: as it has to be implemented in concrete
                                 classes
        """
        raise NotImplementedError()
    # cleanup()

# EnvBase()
