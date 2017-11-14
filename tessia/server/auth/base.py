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
Interface definition for login managers
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
class BaseLoginManager(metaclass=abc.ABCMeta):
    """
    Abstract class to define the login manager interface to be implemented by
    specialized classes.
    """
    @abc.abstractmethod
    def authenticate(self, username, password):
        """
        Validate the provided credentials against the authentication base.
        Should return a dict containing the attributes defined in section
        user_attributes of config file.

        Args:
            username (str): username
            password (str): password

        Raises:
            NotImplementedError: as it has to be implemented in concrete
                                 classes
        """
        raise NotImplementedError()
    # authenticate()

# BaseLoginManager()
