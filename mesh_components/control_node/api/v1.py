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
from flask import abort, current_app, Blueprint, jsonify, request

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


@api.errorhandler(RuntimeError)
def err_start_instance(exc):
    """Handle runtime errors from service layer"""
    return jsonify(error=str(exc)), 400
# Ferr_start_instance()


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
        '/instances': 'Create or show instance',
    }
# schema()


@api.post('/instances')
def create_instance():
    """Start a tessia instance"""
    factory = current_app.instance_factory
    configuration = request.get_json()

    instance = factory.create_instance(configuration)
    instance.setup()
    try:
        instance.run()
    except RuntimeError:
        instance.cleanup()
        raise

    token = current_app.instance_manager.register_instance(instance)

    return jsonify({"success": True, "instance_id": token}), 201
# create_instance()


@api.get('/instances')
def list_instances():
    """List active instances"""
    tokens = list(current_app.instance_manager.keys())

    return jsonify(tokens)
# list_instances()


@api.get('/instances/<instance_id>')
def get_instance_status(instance_id: str):
    """Get status of a registered instance"""
    instance = current_app.instance_manager.get(instance_id)
    if not instance:
        abort(404)

    result = {
        'instance_id': instance_id,
        'status': instance.verify()
    }
    return result
# get_instance_status()


@api.delete('/instances/<instance_id>')
def remove_instance(instance_id: str):
    """Get status of a registered instance"""
    instance = current_app.instance_manager.pop(instance_id, None)
    if not instance:
        abort(404)

    instance.cleanup()
    return "", "204 Deleted"
# remove_instance()
