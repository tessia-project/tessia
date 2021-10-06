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

#
# IMPORTS
#
import logging

from .query import PermissionManagerQueryFactory, ResourceManagerQueryFactory
from .task import task_from_dict

#
# CONSTANTS AND DEFINITIONS
#

# Default configuration
DEFAULT_CONFIGURATION = {
    'resource-manager': None,
    'permission-manager': None,
    'allow-overrides': []
}

#
# CODE
#


class Scheduler:
    """
    Job scheduler

    Manages active job queue
    """

    def __init__(self) -> None:
        self._config = DEFAULT_CONFIGURATION.copy()
        self._logger = logging.getLogger('mesh-scheduler')
    # __init__()

    def _get_effective_configuration(self, overrides):
        """Apply configuration overrides, returning a new config"""
        if not overrides:
            return self._config

        config_update = {
            key: overrides[key]
            for key in self._config['allow-overrides']
        }
        return dict(self._config, **config_update)
    # _get_effective_configuration()

    # Pylint shows false positives on NewType and Factories
    # pylint:disable=no-member,unsubscriptable-object,unsupported-membership-test
    def add_job(self, task_definition):
        """
        Add a job to queue
        """
        # Check if a task is acceptable
        task = task_from_dict(task_definition)
        config = self._get_effective_configuration(task.get('configuration'))
        rm_query = ResourceManagerQueryFactory(config['resource-manager'])
        pm_query = PermissionManagerQueryFactory(config['permission-manager'])

        # TODO: ask machine instance if definition is ok
        # TODO: ask machine instance for resources and usage
        # Task machines do not have connection to resource manager,
        # so they can only provide information from task parameters
        # in a way that scheduler understand, e.g. with system name
        # and profile.

        # Here scheduler asks resource manager about what are the actual
        # resources to be used, so they can be appropriately queued.
        used_resources = rm_query.get_resources(
            task['task'].get('resources', []))

        # Ask resource manager about submitter identity
        if 'authorization' not in task:
            submitter = rm_query.get_user_info('')
        else:
            submitter = rm_query.get_user_info(
                task['authorization'].get('submitter', ''))

        # Ask permission manager if requested access is allowed
        # Will raise if use of resources is not allowed
        pm_query.assert_use_resources(submitter, used_resources)

        # Knowing resources, enqueue job
        # TODO: relay to queuer

        # TODO: Return job ID and queuer state, i.e. executing immediately
        # or waiting
        return 0
    # add_job()

    def cancel_job(self, job_id):
        """
        Cancel an active job
        """
        # Relay to queuer

        # Return new state of job, whether it is cancelling
        # or already completed (or not found)
    # cancel_job()

    def get_job(self, job_id):
        """
        Retrieve job information
        """
        # Return most complete information that is available:
        # - initial request parameters
        # - current queue position and state
        # - resources in use
    # get_job()

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
    # apply_config()

    def get_waiting_queues(self):
        """
        Report waiting queues
        """
        # Return queues current state:
        # - which queues are there
        # - items ready for release
        # - items waiting on conditions
        return ()
    # get_waiting_queues()

# Scheduler
