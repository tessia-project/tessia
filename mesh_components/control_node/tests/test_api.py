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
Tessia control node API unit tests
"""

#
# IMPORTS
#
import pytest

from flask import json
from control_node.api import create_app

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
    with app.test_client() as test_client:
        yield test_client
# client()


def test_api_info_responses_are_valid(client):
    """Query API version"""
    resp = client.get('/')
    api_info = json.loads(resp.data)
    resp = client.get(f"{api_info['apis'][0]['root']}/schema")
    schema_info = json.loads(resp.data)

    assert api_info['name'] == 'control_node'
    assert 'version' in api_info['apis'][0]
    assert 'min_version' in api_info['apis'][0]
    assert '/' in schema_info
# test_api_info_responses_are_valid()


class TestApiV1:
    """Tests for API v1"""

    def test_malformed_request_is_rejected(self, client):
        """Malformed (unparseable) requests are rejected"""
        resp = client.post('/v1/instances', data=r"{not a valid json}")

        assert resp.status_code == 400
    # test_malformed_request_is_rejected()

    def test_invalid_request_is_rejected(self, client):
        """Invalid (wrong schema) requests are rejected"""
        resp = client.post(
            '/v1/instances', json={'task': {'machine': 'invalid'}})

        assert resp.status_code == 400
    # test_invalid_request_is_rejected()

    def test_smallest_instance_startup_and_shutdown(self, client):
        """Shortest possible request is accepted"""
        resp_create = client.post('/v1/instances', json={
            'mode': 'detached', 'components': {}})
        created = json.loads(resp_create.data)

        resp_get = client.get(f'/v1/instances/{created["instance_id"]}')
        instance = json.loads(resp_get.data)

        resp_delete = client.delete(f'/v1/instances/{instance["instance_id"]}')

        assert resp_create.status_code == 201
        assert created['success']
        assert resp_get.status_code == 200
        assert instance['instance_id'] == created['instance_id']
        assert resp_delete.status_code == 204
    # test_smallest_instance_startup_and_shutdown()
