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
from jsonschema import Draft7Validator  # TODO: update to 2020 validator

#
# CONSTANTS AND DEFINITIONS
#


SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object',
    'title': 'Task machine and its parameters',
    '$defs': {},
    'properties': {
        'machine': {
            'type': 'string'
        },
        'parameters': {
            # unchecked - parameters are passed as-is to machine
        },
    },
    'required': ['machine', 'parameters'],
    'additionalProperties': False,
}


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


class Task:
    """
    A state machine task

    Contains an opaque representation of a task that can be processed further
    by environment preparation and task runner
    """

    def __init__(self, fields: dict) -> None:
        """Initialize a task from dictionary"""
        for key, value in fields.items():
            self.__setattr__(key, value)
    # __init__()
# Task


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
