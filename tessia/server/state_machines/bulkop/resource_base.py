# Copyright 2019 IBM Corp.
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
Resource handler interface definition
"""

#
# IMPORTS
#
from tessia.server.lib.perm_manager import PermManager

import abc

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class ResourceHandlerBase(metaclass=abc.ABCMeta):
    """
    Interface definition for concrete resource handlers
    """
    def __init__(self, requester):
        self._requester = requester
        self._perman = PermManager()
    # __init__()

    @staticmethod
    @abc.abstractmethod
    def headers_match(headers):
        """
        Return True if the provided headers match the resource type
        """
        raise NotImplementedError()
    # headers_match()

    @abc.abstractmethod
    def render_item(self, entry):
        """
        Receive an entry in dict format with keys in the header format and
        produce the corresponding database object with the changes applied
        """
        raise NotImplementedError()
    # render_item()
# ResourceHandlerBase
