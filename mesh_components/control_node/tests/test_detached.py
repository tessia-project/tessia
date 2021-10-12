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
Tessia control node class unit tests
"""

#
# IMPORTS
#
import pytest
import requests

from control_node.control_node.factory import InstanceFactory

#
# CONSTANTS AND DEFINITIONS
#
INSTANCE_CONFIGURATION = {
    "mode": "detached",
    "components": {
        "control_node": {
            "listen": "localhost",
            "port": 8450,
            "configuration": {}
        },
        "permission_manager": {
            "listen": "localhost",
            "port": 8451,
            "configuration": {}
        },
        "resource_manager": {
            "listen": "localhost",
            "port": 8452,
            "configuration": {}
        },
        "scheduler": {
            "listen": "localhost",
            "port": 8454,
            "configuration": {
                "scheduler": {
                    "permission-manager": {
                        "url": "http://localhost:8451"
                    },
                    "resource-manager": {
                        "url": "http://localhost:8452"
                    }
                }
            }
        }
    }
}


#
# CODE
#
@pytest.fixture
def instance():
    """Create a default instance"""
    factory = InstanceFactory()
    with factory.create_instance(INSTANCE_CONFIGURATION) as default_instance:
        yield default_instance
# instance()

def test_instance_can_be_launched(instance):
    """Run an instance and verify responses from components"""
    instance.setup()
    instance.run()

    req_control_node = requests.get('http://localhost:8450').json()
    req_perman = requests.get('http://localhost:8451').json()
    req_resman = requests.get('http://localhost:8452').json()
    req_scheduler = requests.get('http://localhost:8454').json()

    assert req_control_node['name'] == 'control_node'
    assert req_perman['name'] == 'permission_manager'
    assert req_resman['name'] == 'resource_manager'
    assert req_scheduler['name'] == 'scheduler'
# test_instance_can_be_launched()
