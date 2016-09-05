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
    def _enqueue_job(queue, job):
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
        if queue == 0:
            queue.append(job)
            return

        i = 0
        while i < queue_length:

            # a job in the queue has start date: compare them
            if queue[i].start_time is not None:
                # new job has no date or date greater than existing one: move
                # to next position
                if (job.start_time is not None and
                        job.start_time < queue[i].start_time):
                    break
            # new job has a start time and queued job doesn't: new job comes
            # first
            elif job.start_time is not None:
                break

            # new job has higher priority: make it come before existing job
            if job.priority < queue[i].priority:
                break

            # jobs have same priority but new job was submitted first: comes
            # first
            if job.submit_date < queue[i].submit_date:
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
        for res_mode in ('exclusive', 'shared'):
            for resource in job.resources.get(res_mode, []):
                queue = self._wait_queues[job.time_slot].get(resource)
                # no queue yet for this resource: create an empty one
                if queue is None:
                    self._queues[job.time_slot][res_key] = []
                    queue = self._queues[job.time_slot][resource]

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

        # check if any active job is using a resource needed by the
        # candidate job

        # exclusive resources conflict with active jobs in exclusive and shared
        # modes
        for resource in job.resources.get('exclusive', []):
            for mode in ('exclusive', 'shared'):
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
        for resource in job.resources.get('shared', []):
            active_job = self._active_jobs['exclusive'].get(resource)
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
        if (job.start_time is not None and
                job.start_time < datetime.now() - timedelta(minutes=1)):
            self._logger.debug(
                'Job %s cannot start: start date not reached yet')
            return False

        # check if candidate job is in first position on all resource queues
        for wait_queue in self._get_wait_queues(job):
            queue_len = len(queue)
            # this is not expected to happen but in case a queue is empty it
            # means no conflicts with any other job would occur
            if queue_len == 0:
                continue

            # candidate job is the in first position: verify the next queue
            if wait_queue[0].id == job.id:
                continue

            # next job has a start date: check if the timeout of the
            # candidate job would fit a time slot before the start time of the
            # next job in the queue
            if wait_queue[0].start_time is not None:
                # job has no timeout: it cannot be started since we don't know
                # when it will end
                if job.timeout == 0:
                    return False

                end_date = datetime.now() + timedelta(minutes=job.timeout+5)
                if end_date >= queue[i].start_time:
                    return False

            # timeout of candidate job fits before first job with start time,
            # now check if there isn't another job without start time that
            # comes first
            i = 1
            while i <= queue_len and wait_queue[i].start_time is not None:
                i += 1

            # another job without start time comes first: candidate cannot run
            if wait_queue[i].id != job.id:
                return False

        return True
    # can_start()

    def enqueue(self, job):
        """
        Add a given job to the queues of its resources.
        """
        if job.state in (SchedulerJob.STATE_CLEANINGUP,
                         SchedulerJob.STATE_RUNNING):
            for res_mode in ('exclusive', 'shared'):
                for resource in job.resources.get(res_mode, []):
                    self._active_jobs[res_mode][resource] = job

        elif job.state == SchedulerJob.STATE_WAITING:
            for wait_queue in self._get_wait_queues(job):
                # enqueue job in the correct position
                position = self._enqueue_job(wait_queue, job)

        else:
            raise ValueError(
                "Job {} in invalid state '{}'".format(job.id, job.state))
    # enqueue()

    def active_pop(self, job):
        """
        Remove a given job from the active listing
        """
        for mode in ('exclusive', 'shared'):
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
                wait_queue.pop(i)

    # wait_pop()

    def reset(self):
        """
        Reset all queues to empty state
        """
        self._wait_queues = {}
        # keep one set of queues for each type of time slot
        for time_slot in SchedulerJob.SLOTS:
            self._wait_queues[time_slot] = {}

        # jobs that are currently running
        self._active_jobs = {'exclusive': {}, 'shared': {}}
    # reset()

# ResourcesManager
