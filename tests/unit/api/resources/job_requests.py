# Copyright 2020 IBM Corp.
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
Unit test for job requests module
"""

#
# IMPORTS
#
from datetime import datetime, timedelta, timezone
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia.server.api.resources.job_requests import JobRequestResource
from tessia.server.db import models
from tessia.server.lib.mediator import MEDIATOR

import os
import secrets
import yaml

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestJobRequest(TestSecureResource):
    """
    Validates the Job request
    """
    # entry point for resource in api
    RESOURCE_URL = '/job-requests'
    # model associated with this resource
    RESOURCE_MODEL = models.SchedulerRequest
    # api object associated with the resource
    RESOURCE_API = JobRequestResource

    @classmethod
    def _entry_gen(cls):
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'action_type': 'SUBMIT',
                'job_type': 'echo',
                'parameters': 'echo Job {} submit successful'.format(index)
            }
            index += 1
            yield data
    # _entry_gen()

    @classmethod
    def setUpClass(cls):
        """
        Called once before any test in this test class run.
        """
        url = os.environ.get('TESSIA_MEDIATOR_URI')
        if not url:
            raise RuntimeError('env variable TESSIA_MEDIATOR_URI not set')

        # switch to test database
        MEDIATOR._mediator_uri = url.replace('/0', '/1')
        cls._mediator = MEDIATOR

        super(TestJobRequest, cls).setUpClass()
    # setUpClass(cls):

    def test_delayed_job_request(self):
        """
        Test that delayed jobs have correct ttl for secrets
        """
        login = 'user_privileged@domain.com'
        secret = {'TOKEN': secrets.token_urlsafe()}
        data = {
            'action_type': 'SUBMIT',
            'job_type': 'ansible',
            'start_date': {
                '$date': int(
                    (datetime.utcnow() + timedelta(1)).replace(
                        tzinfo=timezone.utc).timestamp() * 1000)
            },
            'parameters': {
                'source': 'https://oauth:${TOKEN}@example.com/ansible/'
                          'ansible-example.tgz',
                'playbook': 'workload1/site.yaml',
                'systems': [
                    {
                        'name': 'kvm054',
                        'groups': ['webservers', 'dbservers'],
                    }
                ],
                'secrets': secret,
                'verbosity': 'DEBUG'
            }
        }
        data['parameters'] = yaml.dump(data['parameters'],
                                       default_flow_style=False)
        resp = self._do_request('create', '{}:a'.format(login), data)
        self.assertEqual(200, resp.status_code, resp.data)

        # check ttl on our variables, should be about 2 days
        mediator_key = 'job_requests:{}:vars'.format(
            resp.get_data(as_text=True))
        self.assertEqual(MEDIATOR.get(mediator_key), secret)
        ttl = MEDIATOR._conn.ttl(mediator_key)
        MEDIATOR.set(mediator_key, None)
        self.assertGreater(ttl, 2*86400-120)
        self.assertLess(ttl, 2*86400+120)
    # test_delayed_job_request()
# TestJobRequest
