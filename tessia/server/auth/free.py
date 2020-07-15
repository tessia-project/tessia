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
Implementation of a login manager that always allow access
"""

#
# IMPORTS
#
from tessia.server.auth.base import BaseLoginManager

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class FreeLoginManager(BaseLoginManager):
    """
    A simple login manager which allows any attempt to succeed. To be used for
    development/testing purposes.
    """

    def authenticate(self, username, password):
        """
        Always accept authentication and return a valid entry dynamically
        created. The special username 'fail' (without quotes) force the
        authentication to fail.

        Args:
            username (str): username
            password (str): password

        Returns:
            dict: user information
            None: if special username 'fail' is provided
        """
        if username == 'fail':
            return None

        resp = {
            'login': username,
            'fullname': username.upper(),
            'title': 'Job title',
        }
        return resp
    # authenticate()

# FreeLoginManager()


MANAGER = FreeLoginManager
