# Copyright 2021 IBM Corp.
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
Permission Manager mesh component
"""

#
# IMPORTS
#
import logging

#
# CONSTANTS AND DEFINITIONS
#

# Current version of the component
CURRENT_VERSION = "0.0.1"

# Default configuration
DEFAULT_CONFIGURATION = {

}

#
# CODE
#


class PermissionManager:
    """
    Permission Manager

    Manages access to resources based on prescribed rules and policies
    """

    def __init__(self) -> None:
        self.version = CURRENT_VERSION
        self._config = dict(**DEFAULT_CONFIGURATION)
        self._logger = logging.getLogger('mesh-permission-manager')
    # __init__()

    def apply_config(self, configuration):
        """
        Apply and reapply component configuration
        """
        # Verify configuration
        if not isinstance(configuration, dict):
            self._logger.warning("Failed to apply configuration: "
                                 "invalid format")
            return

        # Apply configuration
        self._logger.info("Configuration applied: %s", configuration)
        self._config.update(configuration)
    # apply_config()

# PermissionManager
