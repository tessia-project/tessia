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
from scheduler.scheduler import Scheduler

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


@pytest.fixture
def task_with_all_fields():
    return {
        'task': {
            'machine': 'autoinstall',
            'parameters': {},
            'resources': [
                {'resource_type': 'system', 'identifier': 'sys1', 'usage': 'exclusive'},
                {'resource_type': 'volume', 'identifier': 'vol1', 'usage': 'exclusive'},
                {'resource_type': 'ip', 'identifier': '10.9.8.7', 'usage': 'exclusive'},
            ]
        },
        'schedule': {
            'priority': 5,
        },
        'authorization': {
            'submitter': 'user@example.com'
        },
        'configuration': {
            'resource-manager': None,
            'permission-manager': None
        }
    }
# task_with_all_fields()


@pytest.fixture
def config_with_managers():
    return {
        'resource-manager': {'url': 'https://localhost:9854'},
        'permission-manager': {'url': 'https://localhost:9855'},
    }
# config_with_managers()


def test_can_add_jobs_without_managers(task_with_all_fields):
    """Add job when no managers are present"""
    sched = Scheduler()

    ret = sched.add_job(task_with_all_fields)

    assert ret == 0
# test_can_add_jobs_without_managers()


def test_can_add_jobs_with_override(task_with_all_fields, config_with_managers):
    """Add job when managers are present, but overriden by task config"""
    sched = Scheduler()
    sched.apply_config(config_with_managers)
    sched.apply_config(
        {'allow-overrides': ['resource-manager', 'permission-manager']})

    ret = sched.add_job(task_with_all_fields)

    assert ret == 0
# test_can_add_jobs_with_override()


def test_fail_on_misconfigured_task(task_with_all_fields):
    """Add job when no managers are present"""
    sched = Scheduler()
    task_with_all_fields.update({'task': {}})

    with pytest.raises(ValueError):
        sched.add_job(task_with_all_fields)
# test_fail_on_misconfigured_task()
