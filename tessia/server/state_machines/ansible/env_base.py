# Copyright 2018 IBM Corp.
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
    def run(self, repo_dir):
        """
        Start ansible execution using given directory as ansible config

        Args:
            repo_dir (str): ansible repository directory

        Raises:
            NotImplementedError: as it has to be implemented in concrete
                                 classes
        """
        raise NotImplementedError()
    # exec()
# EnvBase()
