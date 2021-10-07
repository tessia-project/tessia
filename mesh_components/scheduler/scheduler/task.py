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
Scheduler task
"""

#
# IMPORTS
#
from typing import NewType
from jsonschema import Draft7Validator  # TODO: update to 2020 validator

#
# CONSTANTS AND DEFINITIONS
#


SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object',
    'title': 'Scheduler task',
    '$defs': {},
    'properties': {
        'task': {
            'type': 'object',
            'title': 'Task machine and its parameters',
            'properties': {
                'machine': {
                    'type': 'string'
                },
                'parameters': {
                    # unchecked - parameters are passed as-is to machine
                },
                'resources': {
                    'type': 'array',
                    'title': 'Resources to be used by machine',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'resource_type': {
                                'enum': ['system', 'volume', 'ip', 'custom']
                            },
                            'identifier': {
                                'type': 'string'
                            },
                            'usage': {
                                'enum': ['shared', 'exclusive']
                            }
                        }
                    }
                },
            },
            'required': ['machine', 'parameters'],
            'additionalProperties': False
        },
        'schedule': {
            'type': 'object',
            'title': 'Scheduling paramters',
            'properties': {
                'priority': {
                    'type': 'integer',
                    'title': 'Job priority (0 is highest)',
                    'minimum': 0,
                    'maximum': 9,
                }
            },
            'additionalProperties': False
        },
        'authorization': {
            'type': 'object',
            'title': 'Authorization information',
            'properties': {
                'submitter': {
                    'type': 'string'
                }
            },
            'required': ['submitter'],
            'additionalProperties': False
        },
        'configuration': {
            'type': 'object',
            'title': 'Configuration overrides',
            'properties': {
                'resource-manager': {
                    "oneOf": [
                        {'type': 'object'},
                        {'type': 'null'},
                    ]
                },
                'permission-manager': {
                    "oneOf": [
                        {'type': 'object'},
                        {'type': 'null'},
                    ]
                }
            },
            'additionalProperties': False
        }
    },
    'required': ['task'],
    'additionalProperties': True
}


Task = NewType('Task', dict)

#
# CODE
#


_VALIDATOR = Draft7Validator(SCHEMA)


class ValidationError(ValueError):
    """Validation error"""

    def __init__(self, error_iterator) -> None:
        errors = [f'{"/".join(map(str, item.path))}: {item.message}'
                  for item in error_iterator]
        super().__init__(f'Task validation failed: {", ".join(errors)}')
    # __init__()
# ValidationError


def task_from_dict(in_task: dict) -> Task:
    """
    Create a task from json representation

    Raises:
        ValidationError: input does not correspond to schema
    """
    if _VALIDATOR.is_valid(in_task):
        return Task(in_task)

    raise ValidationError(_VALIDATOR.iter_errors(in_task))
# task_from_dict()


def __main__():
    """Sanity check"""
    _VALIDATOR.check_schema(SCHEMA)
# __main__()
