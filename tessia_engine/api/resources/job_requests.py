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
Resource definition
"""

#
# IMPORTS
#
from datetime import datetime
from flask import g as flask_global
from flask_potion import fields
from flask_potion import exceptions as potion_exceptions
from flask_potion.fields import Inline
from flask_potion.resource import ModelResource
from flask_potion.routes import Route
from tessia_engine.api import exceptions as api_exceptions
from tessia_engine.db import exceptions as db_exceptions
from tessia_engine.db.models import SchedulerRequest
from tessia_engine.state_machines import MACHINES

import re

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'request_id': 'Request ID',
    'requester': 'Request owner',
    'action_type': 'Action type',
    'job_id': 'Target job ID',
    'job_type': 'Machine type',
    'time_slot': 'Job time slot',
    'timeout': 'Allowed job duration',
    'start_date': 'Start date',
    'parameters': 'Machine parameters',
    'priority': 'Job priority',
    'submit_date': 'Date submitted',
    'state': 'Request state',
    'result': 'Request result',
}

#
# CODE
#
class JobRequestResource(ModelResource):
    """
    Resource for job requests
    """
    class Meta:
        """
        Potion's meta section
        """
        exclude_routes = ['destroy', 'update']

        # the sqlalchemy model
        model = SchedulerRequest

        # name of the resource in the url
        name = 'job-requests'

        title = 'Job requests'
        description = 'Requests to submit or cancel jobs'
        human_identifiers = ['request_id']
    # Meta

    class Schema:
        """
        Schema defining the resource fields and their properties
        """
        request_id = fields.Integer(
            title=DESC['request_id'], description=DESC['request_id'],
            attribute='id', io='r')
        requester = fields.String(
            title=DESC['requester'], description=DESC['requester'], io='r')
        action_type = fields.String(
            title=DESC['action_type'], description=DESC['action_type'],
            enum=SchedulerRequest.ACTIONS)
        job_id = fields.Integer(
            title=DESC['job_id'], description=DESC['job_id'], nullable=True)
        job_type = fields.String(
            title=DESC['job_type'], description=DESC['job_type'],
            nullable=True, enum=MACHINES.names)
        time_slot = fields.String(
            title=DESC['time_slot'], description=DESC['time_slot'],
            enum=SchedulerRequest.SLOTS, default=SchedulerRequest.SLOT_DEFAULT)
        timeout = fields.Integer(
            title=DESC['timeout'], description=DESC['timeout'], minimum=0,
            default=0)
        start_date = fields.DateTime(
            title=DESC['start_date'], description=DESC['start_date'],
            nullable=True)
        submit_date = fields.DateTime(
            title=DESC['submit_date'], description=DESC['submit_date'], io='r')
        parameters = fields.String(
            title=DESC['parameters'], description=DESC['parameters'],
            default='')
        priority = fields.Integer(
            title=DESC['priority'], description=DESC['priority'], default=0)
        state = fields.String(
            title=DESC['state'], description=DESC['state'], io='r')
        result = fields.String(
            title=DESC['result'], description=DESC['result'], io='r')
    # Schema

    @Route.POST('', rel="create")
    def create(self, properties):
        """
        Handler for the create item via POST operation.

        Args:
            properties (dict): field=value combination for the item to be
                               created

        Returns:
            json: json response as defined by response_schema property
        """
        # cancel operations must have a job id as target
        if properties['action_type'] == SchedulerRequest.ACTION_CANCEL:
            if properties['job_id'] is None:
                msg = 'Cancel operation must have a job id as target'
                raise api_exceptions.BaseHttpError(code=400, msg=msg)

            # job type is not necessary since job is already in place
            properties['job_type'] = ''

        # submit operations must specify a machine type
        if (properties['action_type'] == SchedulerRequest.ACTION_SUBMIT and
                properties['job_type'] is None):
            msg = 'Submit operation must specify a machine type'
            raise api_exceptions.BaseHttpError(code=400, msg=msg)

        # TODO: fix date creation directly in database
        properties['submit_date'] = datetime.utcnow()
        properties['requester'] = flask_global.auth_user.login

        try:
            item = self.manager.create(properties)
        # TODO: here we assume it's the job id fk (user provided a job id that
        # does not exist), improve the api's IntegrityError to deal with this
        # and use it to extract precise data from exception.
        except potion_exceptions.BackendConflict as exc:
            msg = 'Job id provided does not exist'
            raise api_exceptions.BaseHttpError(code=404, msg=msg)
        # this might happen for example in case requester does not exist
        except db_exceptions.AssociationError as exc:
            raise api_exceptions.ItemNotFoundError(
                exc.column, exc.value, self)
        # raised by one the sa's field validators
        except ValueError as exc:
            msg_match = re.match(r'^.*<\((.*)\)=\((.*)\)>.*$', str(exc))
            try:
                field = msg_match.group(1)
                value = msg_match.group(2)
            except (AttributeError, IndexError):
                msg = 'A value specified is invalid, check the data entered.'
            else:
                msg = "The value '{}={}' is invalid".format(field, value)
            raise api_exceptions.BaseHttpError(code=400, msg=msg)

        return item.id
    # create()
    create.request_schema = Inline('self')
    create.response_schema = None

# JobRequestResource
