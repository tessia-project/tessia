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
Scheduler API v1
"""

#
# IMPORTS
#
from flask import current_app, Blueprint, jsonify, request

from ..scheduler.errors import NotAuthorized

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


api = Blueprint('v1', __name__, url_prefix='/v1')

api_v1 = {
    'blueprint': api,
    'root': '/v1',
    'min_version': '0.0.0',
    'version': '0.0.1'
}


@api.errorhandler(ValueError)
def err_invalid_value(exc):
    """Handle value errors from service layer"""
    return jsonify(error=str(exc)), 400


@api.errorhandler(NotAuthorized)
def err_not_authorized(exc):
    """Handle value errors from service layer"""
    return jsonify(error=str(exc)), 401


@api.route('/')
def root():
    """
    API root

    Verify that request is authorized and succeeds
    """
    return {
        'success': True
    }
# root()


@api.route('/schema')
def schema():
    """API schema"""
    return {
        '/': 'api root',
        '/jobs': 'list jobs',
        '/job/:id': 'get job id',
        '/queues': 'list queues'
    }
# schema()


@api.post('/jobs')
def create_job():
    """Create a scheduler job"""
    scheduler = current_app.scheduler
    task = request.get_json()
    job_id = scheduler.add_job(task)
    return {'job_id': job_id}, 201
# create_job()


@api.get('/queues')
def queues_list():
    """Return waiting queues"""
    scheduler = current_app.scheduler
    queues = scheduler.get_waiting_queues()
    return jsonify(queues)
# queues_list()
