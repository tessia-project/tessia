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
Scheduler mesh component
"""

import logging

# Default configuration
DEFAULT_CONFIGURATION = {
    'resource-manager': None,
    'permission-manager': None
}


class Scheduler:
    """
    Job scheduler

    Manages active job queue
    """

    def __init__(self) -> None:
        self._config = dict(**DEFAULT_CONFIGURATION)
        self._logger = logging.getLogger('mesh-scheduler')

    def add_job(self, task, prio=None, run_at=None):
        """
        Add a job to queue
        """
        # Check if it is acceptable
        # - ask machine instance if definition is ok
        # - ask machine instance for resources and usage
        # - ask resource manager for additional information
        # - ask permission manager if requested access is allowed
        # Return respective error if something is wrong

        # Knowing resources, enqueue job
        # -> relay to queuer

        # Return job ID and queuer state (executing immediately or waiting)

    def cancel_job(self, job_id):
        """
        Cancel an active job
        """
        # Relay to queuer

        # Return new state of job, whether it is cancelling
        # or already completed (or not found)

    def get_job(self, job_id):
        """
        Retrieve job information
        """
        # Return most complete information that is available:
        # - initial request parameters
        # - current queue position and state
        # - resources in use

    def apply_config(self, configuration):
        """
        Apply and reapply component configuration
        """
        # Verify configuration
        if not isinstance(configuration, dict):
            return

        # Apply configuration
        self._logger.info("Configuration applied: %s", configuration)
        self._config.update(configuration)

    def get_waiting_queues(self):
        """
        Report waiting queues
        """
        # Return queues current state:
        # - which queues are there
        # - items ready for release
        # - items waiting on conditions
        return ()

# Scheduler
