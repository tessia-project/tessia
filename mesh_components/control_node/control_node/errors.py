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
Custom service layer errors that should be differentiated
"""

#
# IMPORTS
#


#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


class StartInstanceError(RuntimeError):
    """Instance could not be started"""
# StartInstanceError

class ComponentProbeError(RuntimeError):
    """Component returned an erroneous response"""
# ComponentProbeError

class ConfigurationError(ValueError):
    """Invalid configuration values"""
# ConfigurationError

class ValidationError(ValueError):
    """JSON Schema validation error"""

    def __init__(self, error_iterator) -> None:
        errors = [f'{"/".join(map(str, item.path))}: {item.message}'
                  for item in error_iterator]
        super().__init__(f'Task validation failed: {", ".join(errors)}')
    # __init__()
# ValidationError
