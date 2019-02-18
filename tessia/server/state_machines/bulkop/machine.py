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
Machine to perform bulk operations on resources
"""

#
# IMPORTS
#
from jsonschema import validate
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import User
from tessia.server.state_machines.base import BaseMachine
from tessia.server.state_machines.bulkop.resource_ip import \
    ResourceHandlerIpAddress
from tessia.server.state_machines.bulkop.resource_svol import \
    ResourceHandlerStorageVolume
from tessia.server.state_machines.bulkop.resource_system import \
    ResourceHandlerSystem

import csv
import io
import logging
import yaml

#
# CONSTANTS AND DEFINITIONS
#
HANDLERS = {
    'ip': {
        'type': 'IP addresses',
        'class': ResourceHandlerIpAddress,
    },
    'svol': {
        'type': 'storage volumes',
        'class': ResourceHandlerStorageVolume,
    },
    'system': {
        'type': 'systems',
        'class': ResourceHandlerSystem,
    }
}

# Schema to validate the job request
REQUEST_SCHEMA = {
    'type': 'object',
    'properties': {
        'commit': {
            'type': 'boolean',
        },
        'content': {
            'type': 'string'
        },
        'requester': {
            'type': 'string'
        },
        'resource_type': {
            'type': 'string',
            'enum': list(HANDLERS.keys())
        },
        'verbosity': {
            'type': 'string',
            'enum': list(BaseMachine._LOG_LEVELS),
        },
    },
    'required': [
        'content',
        'requester',
    ],
    'additionalProperties': False
}

#
# CODE
#
class BulkOperatorMachine(BaseMachine):
    """
    This machine is responsible for performing insert/update bulk operations
    based on a provided csv file
    """
    def __init__(self, params):
        """
        See base class docstring.

        Args:
            params (str): A string containing a json in the format defined by
                          the REQUEST_SCHEMA constant.

        Raises:
            ValueError: in case resource type is not supported
        """
        super().__init__(params)

        # open the db connection
        MANAGER.connect()

        # process params and fetch necessary data
        self._params = self.parse(params)['params']

        # apply custom log level if specified
        self._log_config(self._params.get('verbosity'))
        self._logger = logging.getLogger(__name__)

        self._handler = (HANDLERS[self._params['resource_type']]
                         ['class'](self._params['requester']))

        # convert field names to lowercase for easier handling
        self._params['content'].fieldnames = [
            field.lower() for field in self._params['content'].fieldnames]
    # __init__()

    @staticmethod
    def _get_res_type(headers):
        """
        Return the resource type based on the headers provided
        """
        headers = [header.upper() for header in headers]
        for res_type, handler_dict in HANDLERS.items():
            if handler_dict['class'].headers_match(headers):
                return res_type

        return None
    # _get_res_type()

    def _stage_apply(self):
        """
        Compare the input with the current database state to compute the
        necessary changes and apply them.
        """
        self._logger.info('bulk operation start')
        self._logger.info('detected resource type: %s',
                          HANDLERS[self._params['resource_type']]['type'])
        for entry in self._params['content']:
            self._handler.render_item(entry)

        if self._params.get('commit'):
            self._logger.info('committing database changes')
            MANAGER.session.commit()
        else:
            self._logger.info('rolling back database changes (dry-run)')
            MANAGER.session.rollback()
    # _stage_apply()

    def cleanup(self):
        """
        Cleanup process
        """
        pass
    # cleanup()

    @classmethod
    def parse(cls, params):
        """
        Method called by the scheduler to validate the user's request and
        collect the resources (usually systems) to be reserved for the job.

        Args:
            params(str): A string containing a json in a format validated by
                         the SCHEMA constant

        Returns:
            dict: Resources allocated for the installation.

        Raises:
            SyntaxError: if content is in wrong format.
            ValueError: if headers are in invalid format.
        """
        try:
            obj_params = yaml.safe_load(params)
            validate(obj_params, REQUEST_SCHEMA)
        except Exception as exc:
            raise SyntaxError(
                "Invalid request parameters: {}".format(str(exc))) from None

        # validate requester
        requester = obj_params['requester']
        obj_params['requester'] = User.query.filter_by(
            login=requester).one_or_none()
        if not obj_params['requester']:
            raise ValueError('Requester {} does not exist'.format(requester))

        try:
            csv_reader = csv.DictReader(
                io.StringIO(obj_params['content']), strict=True)
            headers = csv_reader.fieldnames
        except csv.Error as exc:
            raise ValueError(
                'Error trying to read input provided: {}'.format(exc))
        op_desc = None
        res_type = cls._get_res_type(headers)
        try:
            op_desc = 'Bulk operation for {}'.format(
                HANDLERS[res_type]['type'])
        except KeyError:
            raise ValueError(
                'Error trying to parse input header, invalid format') from None
        # client expects input to be of a certain type: verify if input
        # matches it
        if ('resource_type' in obj_params and
                obj_params['resource_type'].lower() != res_type):
            raise ValueError(
                'Input provided does not match requested resource type {}'
                .format(obj_params['resource_type'].upper()))
        obj_params['resource_type'] = res_type
        obj_params['content'] = csv_reader

        result = {
            'resources': {'shared': [], 'exclusive': []},
            'description': op_desc,
            'params': obj_params,
        }
        return result
    # parse()

    def start(self):
        """
        Start the machine execution.
        """
        self._logger.info('new stage: apply-changes')
        self._stage_apply()

        self._logger.info('operation finished successfully')
        return 0
    # start()
# BulkOperatorMachine
