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
Task Runner class unit tests
"""

#
# IMPORTS
#

import pytest

from flask import json
from task_runner.api.flask_app import create_app

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    with app.test_client() as client:
        yield client
# client()


def test_api_info_responses_are_valid(client):
    """Query API version"""
    resp = client.get('/')
    api_info = json.loads(resp.data)
    resp = client.get(f"{api_info['apis'][0]['root']}/schema")
    schema_info = json.loads(resp.data)

    assert api_info['name'] == 'task_runner'
    assert 'version' in api_info['apis'][0]
    assert 'min_version' in api_info['apis'][0]
    assert '/' in schema_info
# test_api_info_responses_are_valid()


class TestApiV1:
    """Tests for API v1"""

    def test_invalid_request_is_rejected(self, client):
        """Invalid (wrong schema) requests are rejected"""
        resp = client.post(
            '/v1/tasks', 
            json={'without-machine-parameters': 'request-is-invalid'})

        assert resp.status_code == 400
    # test_invalid_request_is_rejected()

    def test_not_found_return_code_is_404(self, client):
        """API returns 404 for a task that is not existing"""
        resp = client.get('/v1/tasks/some-unspecified-id')

        assert resp.status_code == 404
    # test_not_found_return_code_is_404()

    def test_echo_machine_is_started_and_stopped(self, client):
        """Echo machine can be staeted and stopped"""
        resp_create = client.post('/v1/tasks', json={
            'machine': 'echo', 'parameters': """
                echo Machine starting
                sleep 5000
                echo Machine stopping
            """})
        task_created = json.loads(resp_create.data)

        resp_status = client.get(f'/v1/tasks/{task_created["taskId"]}')
        task_status = json.loads(resp_status.data)

        resp_stop = client.post(f'/v1/tasks/{task_created["taskId"]}/stop')
        stop_status = json.loads(resp_stop.data)

        assert resp_create.status_code == 201
        assert task_created['taskId']
        assert resp_status.status_code == 200
        assert task_status['taskId'] == task_created['taskId']
        assert task_status['status']    # just anything
        assert resp_stop.status_code == 200
        assert stop_status['taskId'] == task_created['taskId']
    # test_echo_machine_is_started_and_stopped()
