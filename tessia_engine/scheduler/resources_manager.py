# Copyright 2016, 2017 IBM Corp.
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
The main module containing the daemon processing the job requests
"""

#
# IMPORTS
#
from datetime import datetime, timedelta
from tessia_engine.db.models import SchedulerJob

import datetime
import logging

#
# CONSTANTS AND DEFINITIONS
#
MODE_SHARED = 'shared'
MODE_EXCLUSIVE = 'exclusive'
MODES = (MODE_SHARED, MODE_EXCLUSIVE)

# TODO: specific string for type of list element
# i.e. {'exclusive': ['system.guest01', 'volume.disk01'], 'shared':
# ['system.lpar01']}
RESOURCES_SCHEMA = {
    'type': 'object',
    'properties': {
        MODE_EXCLUSIVE: {'type': 'array'},
        MODE_SHARED: {'type': 'array'},
    }
}

#
# CODE
#
class ResourcesManager(object):
    """
    A helper class to manage operations related to the queues of resources
    used by jobs
    """
    def __init__(self):
        """
        """
        self._logger = logging.getLogger(__name__)
        self.reset()
    # __init__()

    @staticmethod
    def _job_should_go_first(job, other_job):

        # job has a start date, check the start date of the
        # other job
        if job.start_date is not None:

            # job has an earlier start date, it should go first
            if job.start_date < other_job.start_date:
                return True
            # job has a later start date, it should go later
            elif job.start_date > other_job.start_date:
                return False

            # the else case means both jobs have the same
            # start date, more checks will be done below

        # job has no start date, but the other one has,
        # it should go later
        elif other_job.start_date is not None:
            return False

        # at this point, either both jobs have no start date or both jobs
        # have the same start date, so we have to check other parameters
        # to decide who goes first

        # job has higher priority, it should go first
        if job.priority < other_job.priority:
            return True
        # job has lower priority, it should go later
        elif job.priority > other_job.priority:
            return False

        # jobs have same priority but new job was submitted first: comes
        # first
        if job.submit_date < other_job.submit_date:
            return True

        return False

    def _enqueue_job(self, queue, job):
        """
        Enqueue the passed job in the provided resource queue at the correct
        position.

        Args:
            queue (list): the queue of the passed resource
            job (RunnerJob): job to be enqueued

        Returns:
            None

        Raises:
            None
        """
        queue_length = len(queue)

        i = 0
        while i < queue_length:

            if self._job_should_go_first(job, queue[i]):
                break

            # check the next position in queue
            i += 1

        queue.insert(i, job)

        return i
    # _enqueue_job()

    def _get_wait_queues(self, job):
        """
        Return the queues of the resources associated with the passed job
        """
        queues = []
        for res_mode in MODES:
            for resource in job.resources.get(res_mode, []):
                queue = self._wait_queues[job.time_slot].get(resource)
                # no queue yet for this resource: create an empty one
                if queue is None:
                    self._wait_queues[job.time_slot][resource] = []
                    queue = self._wait_queues[job.time_slot][resource]

                queues.append(queue)

        return queues
    # _get_wait_queues()

    def can_start(self, job):
        """
        Verify if a given job meet the requirements to be the next to be
        started.
        """
        if job.state != SchedulerJob.STATE_WAITING:
            return False

        # start time not reached yet
        if (job.start_date is not None
                and job.start_date > datetime.datetime.utcnow()):
            self._logger.debug("start date not reached")
            return False

        # check if any active job is using a resource needed by the
        # candidate job

        # exclusive resources conflict with active jobs in exclusive and shared
        # modes
        for resource in job.resources.get(MODE_EXCLUSIVE, []):
            for mode in MODES:
                active_job = self._active_jobs[mode].get(resource)
                # a resource is in use: report conflict
                if active_job is not None:
                    self._logger.debug(
                        'Job %s cannot start: needs exclusive use of resource '
                        '%s while in %s use by active job %s',
                        job.id,
                        resource,
                        mode,
                        active_job.id)
                    return False

        # shared resources conflict with active jobs only in exclusive mode
        for resource in job.resources.get(MODE_SHARED, []):
            active_job = self._active_jobs[MODE_EXCLUSIVE].get(resource)
            # a resource is in use: report conflict
            if active_job is not None:
                self._logger.debug(
                    'Job %s cannot start: needs shared use of resource '
                    '%s while in exclusive use by active job %s',
                    job.id,
                    resource,
                    active_job.id)
                return False

        # TODO: add support to nightslots
        cur_time_slot = SchedulerJob.SLOT_DEFAULT

        if job.time_slot != cur_time_slot:
            self._logger.debug(
                'Job %s cannot start: current time slot is %s but job has %s',
                job.id,
                cur_time_slot,
                job.time_slot)
            return False

        # job has start time which was not reached yet: cannot run
        if (job.start_date is not None and
                job.start_date > datetime.datetime.utcnow()):
            self._logger.debug(
                'Job %s cannot start: start date not reached yet')
            return False

        # check if candidate job is in first position on all resource queues
        for wait_queue in self._get_wait_queues(job):

            for other_job in wait_queue:

                if other_job.id == job.id:
                    # it's this job's turn for this resource,
                    # check the next resource queue
                    break

                if other_job.start_date is not None:

                    if job.timeout == 0:
                        return False

                    end_date = (datetime.datetime.utcnow()
                                + timedelta(minutes=job.timeout+5))

                    if end_date >= wait_queue[0].start_date:
                        return False
                # the other job has no start date that so it will have to
                # be scheduled before this one
                else:
                    return False

        return True
    # can_start()

    def enqueue(self, job):
        """
        Add a given job to the queues of its resources.
        """
        if job.state in (SchedulerJob.STATE_CLEANINGUP,
                         SchedulerJob.STATE_RUNNING):
            for res_mode in MODES:
                for resource in job.resources.get(res_mode, []):
                    self._active_jobs[res_mode][resource] = job

        elif job.state == SchedulerJob.STATE_WAITING:
            for wait_queue in self._get_wait_queues(job):
                # enqueue job in the correct position
                self._enqueue_job(wait_queue, job)
        else:
            raise ValueError(
                "Job {} in invalid state '{}'".format(job.id, job.state))
    # enqueue()

    def active_pop(self, job):
        """
        Remove a given job from the active listing
        """
        for mode in MODES:
            for resource in job.resources.get(mode, []):
                active_job = self._active_jobs[mode].get(resource)
                if active_job is not None and active_job.id == job.id:
                    self._active_jobs[mode].pop(resource)

    # active_pop()

    def wait_pop(self, job):
        """
        Remove a given job from the wait queues
        """
        for wait_queue in self._get_wait_queues(job):
            found = None
            for i in range(0, len(wait_queue)):
                if wait_queue[i].id == job.id:
                    found = i
                    break
            if found is not None:
                wait_queue.pop(found)
                # TODO: remove queue if empty!!

    # wait_pop()

    def __str__(self):
        representation = []

        representation.append('Wait queues :')
        for time_slot in SchedulerJob.SLOTS:
            representation.append('slot {}'.format(time_slot))
            representation.append(str(self._wait_queues[time_slot]))

        representation.append('Active queues:')

        for mode in MODES:
            representation.append('Mode {}'.format(mode))
            representation.append(str(self._active_jobs[mode]))

        return '\n'.join(representation)
    # __str__

    def reset(self):
        """
        Reset all queues to empty state
        """
        self._wait_queues = {}
        # keep one set of queues for each type of time slot
        for time_slot in SchedulerJob.SLOTS:
            self._wait_queues[time_slot] = {}

        # jobs that are currently running
        self._active_jobs = {MODE_EXCLUSIVE: {}, MODE_SHARED: {}}
    # reset()

# ResourcesManager
