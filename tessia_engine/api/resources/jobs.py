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
from flask_potion import fields
from flask_potion.fields import Inline
from flask_potion.instances import Instances
from flask_potion.resource import ModelResource
from flask_potion.routes import Route
from flask_potion.schema import FieldSet
from tessia_engine.api.exceptions import BaseHttpError
from tessia_engine.config import CONF
from tessia_engine.db.models import SchedulerJob

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'requester': 'Request owner',
    'job_id': 'Job ID',
    'job_type': 'Machine type',
    'time_slot': 'Time slot',
    'state': 'State',
    'resources': 'Resources',
    'parameters': 'Machine parameters',
    'description': 'Description',
    'submit_date': 'Date submitted',
    'start_date': 'Start date',
    'end_date': 'End date',
    'priority': 'Priority',
    'result': 'Result',
    'timeout': 'Timeout (secs)',
}

#
# CODE
#
class JobResource(ModelResource):
    """
    Resource for jobs
    """
    class Meta:
        """
        Potion's meta section
        """
        exclude_routes = ['destroy', 'update', 'create']

        # the sqlalchemy model
        model = SchedulerJob

        # name of the resource in the url
        name = 'jobs'

        exclude_fields = ['pid']

        title = 'Execution jobs'
        description = 'Jobs executed by the scheduler'
        human_identifiers = ['job_id']
    # Meta

    class Schema:
        """
        Schema defining the resource fields and their properties
        """
        job_id = fields.Integer(
            title=DESC['job_id'], description=DESC['job_id'],
            attribute='id', io='r')
        requester = fields.String(
            title=DESC['requester'], description=DESC['requester'], io='r')
        priority = fields.Integer(
            title=DESC['priority'], description=DESC['priority'], io='r')
        job_type = fields.String(
            title=DESC['job_type'], description=DESC['job_type'], io='r')
        time_slot = fields.String(
            title=DESC['time_slot'], description=DESC['time_slot'],
            enum=SchedulerJob.SLOTS, io='r')
        state = fields.String(
            title=DESC['state'], description=DESC['state'], io='r')
        resources = fields.Any(
            title=DESC['resources'], description=DESC['resources'], io='r')
        parameters = fields.String(
            title=DESC['parameters'], description=DESC['parameters'], io='r')
        description = fields.String(
            title=DESC['description'], description=DESC['description'], io='r')
        submit_date = fields.DateTime(
            title=DESC['submit_date'], description=DESC['submit_date'], io='r')
        start_date = fields.DateTime(
            title=DESC['start_date'], description=DESC['start_date'], io='r')
        end_date = fields.DateTime(
            title=DESC['end_date'], description=DESC['end_date'], io='r')
        result = fields.String(
            title=DESC['result'], description=DESC['result'], io='r')
        timeout = fields.Integer(
            title=DESC['timeout'], description=DESC['timeout'], io='r')
    # Schema

    @Route.GET('', rel="instances")
    def instances(self, **kwargs):
        """
        Handler for the list items operation via GET method.

        Args:
            kwargs (dict): contains keys like 'where' (filtering) and
                           'per_page' (pagination), see potion doc for details
        Returns:
            json: json response as defined by response_schema property
        """
        instances = self.manager.paginated_instances(**kwargs)
        return instances
    instances.request_schema = instances.response_schema = Instances()

    @Route.GET('/<int:id>', rel="self", attribute="instance")
    def read(self, id):
        """
        Handler for the get item operation via GET method.

        Args:
            id (int): job id

        Returns:
            json: json response as defined by response_schema property
        """
        # pylint: disable=redefined-builtin,invalid-name
        item = self.manager.read(id)
        return item
    # read()
    read.request_schema = None
    read.response_schema = Inline('self')

    @Route.GET('/<int:id>/output', rel="output")
    def output(self, id, **kwargs):
        # pylint: disable=redefined-builtin,invalid-name
        """
        Handler to fetch the output of a job via GET method.
        """
        try:
            jobs_dir = CONF.get_config()['scheduler']['jobs_dir']
        except KeyError:
            msg = 'No scheduler job directory configured'
            raise BaseHttpError(500, msg=msg)
        offset = kwargs.get('offset')
        qty = kwargs.get('qty')

        # read the content of the file
        try:
            lines = open(
                '{}/{}/output'.format(jobs_dir, id), 'r').readlines()
        # perhaps the file was not created yet, so retrieve job to determine
        # if this is the case or if job id was wrong
        except FileNotFoundError:
            # read will raise exception in case job id is wrong
            self.manager.read(id)
            return ''
        # this means a misconfiguration in server
        except PermissionError:
            msg = 'Access to file forbidden'
            raise BaseHttpError(500, msg=msg)

        # -1 means retrieve the complete content starting at the offset
        if qty == -1:
            output = ''.join(lines[offset:])
        else:
            output = ''.join(lines[offset:offset+qty])

        return output
    # it's important to use FieldSet or Schema otherwise Potion will not parse
    # the parameters from the request query string to the view's arguments
    output.request_schema = FieldSet({
        'offset': fields.Raw(
            {
                "type": "integer",
                "minimum": 0,
            },
            default=0),
        'qty': fields.Raw(
            {
                "type": "integer",
                "minimum": -1,
            },
            default=-1),
    })
    output.response_schema = fields.Raw({'type': 'string'})

# JobResource
