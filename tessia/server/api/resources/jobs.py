# Copyright 2016, 2017, 2022 IBM Corp.
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
from flask import send_file
from flask_potion import fields
from flask_potion.fields import Inline
from flask_potion.instances import Instances
from flask_potion.resource import ModelResource
from flask_potion.routes import Route
from flask_potion.schema import FieldSet, SchemaImpl
from flask_potion.utils import unpack
from io import BytesIO
from itertools import islice
from pathlib import Path

import json
import tarfile

from tessia.server.api.exceptions import BaseHttpError
from tessia.server.config import CONF
from tessia.server.db.models import SchedulerJob
from tessia.server.lib.compression import GzipStreamWrapper

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


class FileSchema(SchemaImpl):
    """
    Response Schema that returns an octet stream instead of JSON
    """

    def format_response(self, response):
        """
        Format response to return an octet stream
        """
        data, code, headers = unpack(response)
        encoding = data.get('encoding', 'raw')

        if code != 200:
            return self.format(data), code, headers

        if encoding == 'gzip':
            def _enc_stream(filestream, filename):
                return GzipStreamWrapper(
                    filestream, data.get('timestamp'), filename)
        else:
            def _enc_stream(filestream, _filename):
                return filestream

        # Expect data to be a dictionary with:
        # 'files': list of files (or a str with single file for output)
        # 'encoding': response encoding (raw, gzip)
        # 'id': job id
        try:
            if isinstance(data['files'], str):
                # return the only file
                filename = f'output-{data["id"]}'
                # pylint: disable=consider-using-with
                response = send_file(
                    _enc_stream(open(data['files'], 'rb'), filename),
                    mimetype='text/plain;charset=UTF-8', as_attachment=True,
                    attachment_filename=filename)

                if encoding == 'gzip':
                    response.headers['Content-Encoding'] = 'gzip'
                return response

            # Create a tarball with all listed files
            # Tarball is stored in memory and not streamed,
            # so in order to conserve memory it will be always gzipped,
            # regardless of requested encoding
            tarbuf = BytesIO()
            with tarfile.open(fileobj=tarbuf, mode='w:gz',
                              compresslevel=1) as tar:
                for file in data['files']:
                    tar.add(file, arcname=Path(file).name)
                tar.close()
            tarbuf.seek(0)

            return send_file(
                tarbuf, mimetype='application/octet-stream',
                as_attachment=True,
                attachment_filename=f'job-{data["id"]}.tar.gz')

        # perhaps the file was not created yet, so retrieve job to determine
        # if this is the case or if job id was wrong
        except FileNotFoundError:
            # read will raise exception in case job id is wrong
            msg = '; '.join(data['files'])
            raise BaseHttpError(404, msg=msg)
        # this means a misconfiguration in server
        except PermissionError:
            msg = 'Access to file forbidden'
            raise BaseHttpError(500, msg=msg)

    # format_response()

# FileSchema


class CompressedJsonSchema(SchemaImpl):
    """
    Response Schema that returns a compressed JSON
    """

    def format_response(self, response):
        """
        Format response to return an octet stream
        """
        data, code, headers = unpack(response)

        # Expect data to be a string to send
        if code == 200:
            response = send_file(
                GzipStreamWrapper(
                    BytesIO(json.dumps(data).encode('utf-8'))),
                mimetype='application/json',
                as_attachment=False)
            response.headers['Content-Encoding'] = 'gzip'
            return response

        return self.format(data), code, headers
    # format_response()

# CompressedJsonSchema


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
    def read(self, id):  # pylint: disable=redefined-builtin,invalid-name
        """
        Handler for the get item operation via GET method.

        Args:
            id (int): job id

        Returns:
            json: json response as defined by response_schema property
        """
        item = self.manager.read(id)
        return item
    # read()
    read.request_schema = None
    read.response_schema = Inline('self')

    @Route.GET('/<int:id>/output', rel="output")
    def output(self, id, **kwargs):  # pylint: disable=redefined-builtin,invalid-name
        """
        Handler to fetch the output of a job via GET method.
        """
        try:
            jobs_dir = CONF.get_config().get('scheduler')['jobs_dir']
        except (TypeError, KeyError):
            msg = 'No scheduler job directory configured'
            raise BaseHttpError(500, msg=msg)
        offset = kwargs.get('offset')
        qty = kwargs.get('qty')

        # read the content of the file
        try:
            with open(f'{jobs_dir}/{id}/output', 'r',
                      encoding='utf-8') as file:
                # -1 means retrieve the complete content starting at the offset
                if qty == -1:
                    return ''.join(islice(file, offset, None))
                return ''.join(islice(file, offset, offset+qty))

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
    output.response_schema = CompressedJsonSchema(
        fields.Raw({'type': 'string'}).schema())

    # pylint: disable=redefined-builtin,invalid-name
    @Route.GET('/<int:id>/download', rel="download")
    def download(self, id, **kwargs):
        """
        Download job output
        """
        try:
            jobs_dir = CONF.get_config().get('scheduler')['jobs_dir']
        except (TypeError, KeyError):
            msg = 'No scheduler job directory configured'
            raise BaseHttpError(500, msg=msg)
        content = kwargs.get('content')
        encoding = kwargs.get('encoding')

        item = self.manager.read(id)

        # pull paths to requested content
        if content == 'output':
            return {
                'files': f'{jobs_dir}/{id}/output',
                'encoding': encoding,
                'id': id,
                'timestamp': item.submit_date.timestamp() or None,
            }
        return {
            'files': Path(f'{jobs_dir}/{id}').glob('*'),
            'encoding': encoding,
            'id': id,
        }

    # it's important to use FieldSet or Schema otherwise Potion will not parse
    # the parameters from the request query string to the view's arguments
    download.request_schema = FieldSet({
        'content': fields.Raw(
            {
                "enum": ["output", "all"],
            },
            default='output'),
        'encoding': fields.Raw(
            {
                "enum": ["raw", "gzip"],
            },
            default='gzip'),
    })
    download.response_schema = FileSchema(
        fields.Raw({'type': 'string'}).schema())

# JobResource
