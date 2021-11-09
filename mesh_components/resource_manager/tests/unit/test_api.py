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
Resource Manager class unit tests
"""

import pytest

from flask import json
from resource_manager.src.application.api.flask_app import create_app


@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    with app.test_client() as client:
        yield client
# client()


def test_api_info_responses_are_valid(client):
    """Get API info"""
    resp = client.get('/')
    api_info = json.loads(resp.data)
    resp = client.get('{}/schema'.format(api_info['apis'][0]['root']))
    schema_info = json.loads(resp.data)

    assert api_info['name'] == 'resource_manager'
    assert '/' in schema_info
# test_api_info_responses_are_valid()
