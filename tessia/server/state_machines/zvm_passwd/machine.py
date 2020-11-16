# Copyright 2020 IBM Corp.
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
Machine to perform z/VM guests passwords updates
"""

#
# IMPORTS
#
from jsonschema import validate
from tessia.baselib.hypervisors import Hypervisor
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import System
from tessia.server.state_machines.base import BaseMachine

import json
import logging

# Schema to validate the job request
REQUEST_SCHEMA = {
    'type': 'object',
    'properties': {
        'systems': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string'
                    },
                },
                'required': [
                    'name',
                ],
                'additionalProperties': False
            },
            # at lest one system must be specified
            'minItems': 1,
        },
        'current_passwd': {
            'type': 'string'
        },
        'new_passwd': {
            'type': 'string'
        },
        'requester': {
            'type': 'string'
        },
        'verbosity': {
            'type': 'string',
            'enum': list(BaseMachine._LOG_LEVELS),
        },
        'verify': {
            'type': 'boolean'
        },
    },
    'required': [
        'systems', 'current_passwd', 'new_passwd',
    ],
    'additionalProperties': False
}

#
# CODE
#
class ZVMPasswdMachine(BaseMachine):
    """
    This machine is responsible for performing z/VM guest updates.
    """
    def __init__(self, params):
        """
        See base class docstring.

        Args:
            params (str): A string containing a json in the format defined by
                          the REQUEST_SCHEMA constant.
        """
        super().__init__(params)

        # make sure query attribute is available on the models by explicitly
        # connecting to db
        MANAGER.connect()

        # process params and fetch necessary data
        self._params = self._load_data(params)

        self._logger = logging.getLogger(__name__)

    # __init__()

    @staticmethod
    def _load_data(user_params):
        """
        Load all the necessary data for the machine to work.

        Args:
            user_params (str): request params according to REQUEST_SCHEMA

        Returns:
            dict: containing data required by the machine to run

        Raises:
            SyntaxError: in case request is in wrong format
            ValueError: if any system data is inconsistent for the operation
        """
        try:
            params = json.loads(user_params)
            validate(params, REQUEST_SCHEMA)
        # this exception should never happen as the request was already
        # validated by parse()
        except Exception as exc:
            raise SyntaxError(
                "Invalid request parameters: {}".format(repr(exc))
            ) from None

        for system in params['systems']:
            system_obj = System.query.filter_by(
                name=system['name']).one_or_none()

            # system does not exist in db: report error
            if system_obj is None:
                raise ValueError("System '{}' does not exist.".format(
                    system['name']))
            # sanity check, without hypervisor it's not possible to manage
            # system
            if not system_obj.hypervisor_id:
                raise ValueError(
                    'System {} cannot be managed because it has no '
                    'hypervisor defined'.format(system_obj.name))
        return params
    # _load_data()

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
        """
        try:
            obj_params = json.loads(params)
            validate(obj_params, REQUEST_SCHEMA)
        except Exception as exc:
            raise SyntaxError(
                "Invalid request parameters: {}".format(str(exc))) from None

        # make sure query attribute is available on the models by explicitly
        # connecting to db
        MANAGER.connect()

        # resources used in this job
        used_resources = cls._get_resources(obj_params['systems'])

        systems_list = ', '.join(used_resources['exclusive'][:3])
        if len(used_resources['exclusive']) > 3:
            systems_list += ' and {} more'.format(
                len(used_resources['exclusive']) - 3)
        result = {
            'resources': used_resources,
            'description': 'Change passwords for z/VM guests {}'.format(
                systems_list)
        }
        return result
    # parse()

    @classmethod
    def _get_resources(cls, systems):
        """
        Return the map of resources to be used in this job.

        Args:
            systems (list): list of dicts with the systems to be used.

        Returns:
            dict: {'shared': ['resource1'], 'exclusive': ['resource2,
                  'resource3']}

        Raises:
            ValueError: if validation of parameters fails
        """
        shared_res = set()
        exclusive_res = set()

        for system in systems:
            system_obj = System.query.filter_by(
                name=system['name']).one_or_none()

            # system does not exist in db: report error
            if system_obj is None:
                raise ValueError("System '{}' does not exist.".format(
                    system['name']))

            if not system_obj.hypervisor_id:
                raise ValueError(
                    'System {} cannot be managed because it has no '
                    'hypervisor defined'.format(system_obj.name)
                )

            exclusive_res.add(system_obj.name)

            # the hypervisor hierarchy is a shared resource
            system_obj = system_obj.hypervisor_rel
            while system_obj:
                shared_res.add(system_obj.name)
                system_obj = system_obj.hypervisor_rel

        resources = {
            'shared': list(shared_res),
            'exclusive': list(exclusive_res)
        }

        return resources
    # _get_resources()

    def cleanup(self):
        """
        Clean up in case of cancelation.
        """
        # When the job is canceled during a cleanup the routine
        # is not executed again by the scheduler.
        self.cleaning_up = True
        # make sure any profile overrides are discarded and not committed to
        # the db
        MANAGER.session.rollback()
    # cleanup()

    @classmethod
    def prefilter(cls, params):
        """
        Parse state machine parmfile and remove secrets to avoid storing them
        in the database.

        Args:
            params (str): state machine parameters

        Returns:
            Tuple[str, any]: state machine parameters and supplementary data

        Raises:
            SyntaxError: if content is in wrong format.
        """
        try:
            obj_params = json.loads(params)
            validate(obj_params, REQUEST_SCHEMA)
        except Exception as exc:
            raise SyntaxError(
                "Invalid request parameters: {}".format(str(exc)))
        if not isinstance(obj_params, dict):
            return (params, None)
        passwords = dict(
            {
                "current_passwd": obj_params.pop('current_passwd'),
                "new_passwd": obj_params.pop('new_passwd')
            }
        )

        return (json.dumps(obj_params), passwords)
    # prefilter()

    @classmethod
    def recombine(cls, params, extra_vars=None):
        """
        Update params with the password information passed in extra_vars

        Args:
            params (str): state machine parameters
            extra_vars (dict): password information

        Returns:
            str: final machine parameters
        """
        if not extra_vars:
            return params

        obj_params = json.loads(params)
        obj_params.update(extra_vars)

        return json.dumps(obj_params)
    # recombine()

    @staticmethod
    def _change_zvm_passwd(system_obj, passwd, new_passwd):
        """
        Args:
            system_obj (object): z/VM guest.
            passwd (str): current z/VM guest password.
            new_passwd (str): new z/VM guest password.
        """
        additional_params = {'new_zvm_passwd': new_passwd}

        baselib_hyp = Hypervisor(
            'zvm',
            system_obj.hypervisor_rel.name,
            system_obj.hypervisor_rel.hostname,
            system_obj.name,
            passwd,
            additional_params)
        baselib_hyp.login()
        baselib_hyp.logoff()

    # _change_zvm_passwd()

    def _stage_exec(self):
        """
        Perform password changing for each system specified.
        """
        for system in self._params['systems']:
            system_obj = System.query.filter_by(
                name=system['name']).one_or_none()
            self._logger.info('Сhanging the password on the system %s ...'
                              , system_obj.name)
            self._change_zvm_passwd(
                system_obj,
                self._params['current_passwd'],
                self._params['new_passwd'],
            )
    # _stage_exec()

    def start(self):
        """
        Start the machine execution.
        """
        self._logger.info('new stage: execute-action')
        self._stage_exec()

        self._logger.info('Task finished successfully')
        return 0

    # start()
