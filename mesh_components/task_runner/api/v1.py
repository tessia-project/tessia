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
Task Runner API v1
"""

#
# IMPORTS
#

from flask import current_app, Blueprint, jsonify, request

from ..service_layer import NotFound

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
# err_invalid_value()


@api.errorhandler(NotFound)
def err_not_found(exc):
    """Handle value errors from service layer"""
    return jsonify(error=str(exc)), 404
# err_not_found()


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
        '/': 'api root'
    }
# schema()


@api.post('/tasks')
def create_task():
    """Create a new task"""
    service = current_app.service_layer
    task = request.get_json()
    add_result = service.add_task(task)
    return jsonify({
        'taskId': add_result['id']
    }), 201
# create_task()


@api.get('/tasks/<task_id>')
def get_task(task_id):
    """Retrieve task status"""
    service = current_app.service_layer
    task_status = service.get_task_status(task_id)

    return jsonify({
        'taskId': task_status['id'],
        'status': task_status['status']
    })
# get_task()


@api.post('/tasks/<task_id>/stop')
def stop_task(task_id):
    """Stop task"""
    service = current_app.service_layer
    result = service.stop_task(task_id)
    return jsonify({
        'taskId': result['id'],
    })
# stop_task()
