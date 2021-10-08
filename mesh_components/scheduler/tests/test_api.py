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
Scheduler class unit tests
"""

#
# IMPORTS
#
import pytest

from flask import json
from scheduler.api import create_app

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
    resp = client.get('{}/schema'.format(api_info['apis'][0]['root']))
    schema_info = json.loads(resp.data)

    assert api_info['name'] == 'scheduler'
    assert '/' in schema_info
# test_api_info_responses_are_valid()


class TestApiV1:
    """Tests for API v1"""

    def test_malformed_request_is_rejected(self, client):
        """Malformed (unparseable) requests are rejected"""
        resp = client.post('/v1/jobs', data=r"{not a valid json}")

        assert resp.status_code == 400
    # test_malformed_request_is_rejected()

    def test_invalid_request_is_rejected(self, client):
        """Invalid (wrong schema) requests are rejected"""
        resp = client.post('/v1/jobs', json={'task': {'machine': 'invalid'}})

        assert resp.status_code == 400
    # test_invalid_request_is_rejected()

    def test_shortest_request_is_accepted(self, client):
        """Shortest possible request is accepted"""
        resp = client.post('/v1/jobs', json={
            'task': {'machine': 'echo', 'parameters': 'echo test message'}})
        job_data = json.loads(resp.data)

        assert resp.status_code == 201
        assert 'job_id' in job_data
    # test_shortest_request_is_accepted()
