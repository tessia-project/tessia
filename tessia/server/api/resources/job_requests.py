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
from tessia.server.api import exceptions as api_exceptions
from tessia.server.db import exceptions as db_exceptions
from tessia.server.db.models import SchedulerRequest
from tessia.server.lib.mediator import MEDIATOR
from tessia.server.state_machines import MACHINES
from tessia.server.state_machines.base import BaseMachine

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

        Raises:
            BaseHttpError: bad arguments
            ItemNotFoundError: an associated item (e.g. owner) is not missing
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

        # Remove secrets from the request before putting it into the database.
        # Every state machine has its own way of parsing parameters,
        # so we rely on machine class to do the work
        extra_vars = None
        if properties['action_type'] == SchedulerRequest.ACTION_SUBMIT:
            machine: BaseMachine = MACHINES.classes[properties['job_type']]
            try:
                properties['parameters'], extra_vars = machine.prefilter(
                    properties['parameters'])
            except SyntaxError as exc:
                raise api_exceptions.BaseHttpError(code=400, msg=str(exc))
            # very special case: this machine type needs to know the
            # job requester, so we inject it over extra vars.
            # It's not nice to have an exception, but the alternative is
            # to provide all request parameters to prefilter, which
            # creates a dependency between the machines and the requests table.
            if machine.__name__ == 'BulkOperatorMachine':
                if not extra_vars:
                    extra_vars = dict()
                extra_vars.update({'requester': properties['requester']})

        try:
            # Note, we do not commit to avoid this object be picked up
            # by scheduler before we've passed extra vars to mediator'
            item = self.manager.create(properties, commit=False)
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

        # Pass extra vars over to mediator
        if extra_vars:
            # default expiration is 1 day, but we offset it against
            # requested start date; past start date has no effect on expiration
            expire = 86400
            if properties['start_date']:
                delta = (properties['start_date'].replace(tzinfo=None) -
                         properties['submit_date'])
                expire += max(0, int(delta.total_seconds()))
            token = 'job_requests:{}:vars'.format(item.id)
            try:
                MEDIATOR.set(token, extra_vars, expire=expire)
            except Exception as exc:
                if isinstance(extra_vars, dict):
                    msg = 'Cannot store secret keys {}'.format(
                        ','.join(extra_vars.keys()))
                else:
                    msg = 'Cannot store secrets'
                raise api_exceptions.BaseHttpError(code=400, msg=msg)

        try:
            # Finalize request creation
            self.manager.commit()
        except Exception as exc:
            # we really should not get these, as data is checked during flush,
            # but to be on the safe side we do a catch-all here
            self.manager.rollback()
            msg = 'Unable to submit request: {}'.format(str(exc))
            raise api_exceptions.BaseHttpError(code=400, msg=msg)

        return item.id
    # create()
    create.request_schema = Inline('self')
    create.response_schema = None

# JobRequestResource
