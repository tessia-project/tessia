# Copyright 2017 IBM Corp.
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
spawner.py unit test
"""
from tessia_engine.scheduler import spawner
from tessia_engine.scheduler import wrapper
from unittest import TestCase
from unittest.mock import patch

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestSpawner(TestCase):
    """
    A simple test to cover the process spawner.
    """
    def setUp(self):
        # Mock the MachineWrapper class inside the module since the spawner
        # only imports the module inside the spawn function.
        patcher = patch.object(wrapper, 'MachineWrapper', autospec=True)
        patcher.start()
        self.addCleanup(patcher.stop)
    # setUp()

    @staticmethod
    def test_spawner():
        """
        Only checks if no excpetion is raised by spawn.
        """
        # We can pass bogus parameters since they are only actually used by
        # MachineWrapper, which is mocked.
        spawner.spawn("", "", "", 0)
    # test_spawner()
# TestSpawner
