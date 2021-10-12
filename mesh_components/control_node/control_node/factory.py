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
Tessia instance factory component
"""

#
# IMPORTS
#

# TODO: update to 2020 validator
from jsonschema import Draft7Validator

from .detached import DetachedInstance
from .errors import ValidationError
from .supervisord import SupervisordInstance

#
# CONSTANTS AND DEFINITIONS
#

SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object',
    'title': 'Tessia instance configuration',
    'properties': {
        'mode': {
            'enum': ['detached', 'supervisord']
        },
        'components': {
            'type': 'object'
        }
    },
    'required': ['mode', 'components'],
    'additionalProperties': True
}


#
# CODE
#


# Schema validator
_VALIDATOR = Draft7Validator(SCHEMA)


class InstanceFactory:
    """Configures and launched an instance of tessia"""

    @staticmethod
    def create_instance(configuration: dict):
        """Create an instance from configuration"""
        if not _VALIDATOR.is_valid(configuration):
            raise ValidationError(_VALIDATOR.iter_errors(configuration))

        if configuration['mode'] == 'detached':
            return DetachedInstance(configuration['components'])

        if configuration['mode'] == 'supervisord':
            return SupervisordInstance(configuration['components'])

        raise ValueError("Unknown instance mode requested")
    # create_instance()
# InstanceFactory
