# Copyright 2017 IBM Corp.
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
Define a requests Session to be used throughout the client
"""

#
# IMPORTS
#
from tessia_cli.config import CONF
import requests

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
def get_session():
    """
    Create a pre-configured Session object
    """
    session = requests.Session()
    ca_file = CONF.get_cacert_path()
    if ca_file:
        session.verify = ca_file

    return session
# get_session()

SESSION = get_session()
