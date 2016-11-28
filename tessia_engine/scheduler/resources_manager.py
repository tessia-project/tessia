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

import logging

#
# CONSTANTS AND DEFINITIONS
#
MODE_SHARED = 'shared'
MODE_EXCLUSIVE = 'exclusive'
MODES = (MODE_SHARED, MODE_EXCLUSIVE)

# TODO: specific string for type of list element
# example of entry accepted by schema:
# {'exclusive': ['system.guest01', 'volume.disk01'], 'shared':
#  ['system.lpar01']}
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
        Constructor, creates logger instance and initialize queues to empty
        state.
        """
        self._logger = logging.getLogger(__name__)
        self.reset()
    # __init__()

    def __str__(self):
        """
        String representation of the manager, useful for debugging purposes.
        """
        representation = []

        representation.append('Wait queues:')
        for time_slot in SchedulerJob.SLOTS:
            representation.append('slot {}'.format(time_slot))
            representation.append(str(self._wait_queues[time_slot]))

        representation.append('Active queues:')

        for mode in MODES:
            representation.append('Mode {}'.format(mode))
            representation.append(str(self._active_jobs[mode]))

        return '\n'.join(representation)
    # __str__()

    @staticmethod
    def _enqueue_job(queue, job):
        """
        Enqueue the passed job in the provided resource queue at the correct
        position.

        Args:
            queue (list): the queue of the passed resource
            job (SchedulerJob): job to be enqueued

        Returns:
            int: position in queue where new job was added

        Raises:
            None
        """
        position = 0
        for position in range(0, len(queue)+1):

            try:
                queue_job = queue[position]
            # means the job has no precedence and comes last in the queue
            except IndexError:
                break

            # new job has a start date: check the start date of the queued job
            if job.start_date is not None:

                # queued job has no start date: new job should go first as jobs
                # with start date take precedence
                if queue_job.start_date is None:
                    break
                # job has an earlier start date: it comes first
                elif job.start_date < queue_job.start_date:
                    break
                # job has a later start date: it comes later
                elif job.start_date > queue_job.start_date:
                    continue

                # the else case means both jobs have the same start date, more
                # checks will be done below

            # job has no start date but queued job has: queued job takes
            # precedence
            elif queue_job.start_date is not None:
                continue

            # at this point, either both jobs have no start date or both jobs
            # have the same start date, so we have to check other parameters
            # to decide who comes first

            # new job has higher priority: it comes first
            if job.priority < queue_job.priority:
                break
            # new job has lower priority: it comes later
            elif job.priority > queue_job.priority:
                continue

            # jobs have same priority but new job was submitted first: comes
            # first
            if job.submit_date < queue_job.submit_date:
                break

        queue.insert(position, job)

        return position
    # _enqueue_job()

    def _get_wait_queues(self, job):
        """
        Return the queues of the resources associated with the passed job

        Args:
            job (SchedulerJob): job's model instance

        Returns:
            list: job queues of each resource in form
                  [resource_name, job_queue]
        """
        queues = []
        for res_mode in MODES:
            for resource in job.resources.get(res_mode, []):
                queue = self._wait_queues[job.time_slot].get(resource)
                # no queue yet for this resource: create an empty one
                if queue is None:
                    self._wait_queues[job.time_slot][resource] = []
                    queue = self._wait_queues[job.time_slot][resource]

                queues.append((resource, queue))

        return queues
    # _get_wait_queues()

    def can_start(self, job):
        """
        Verify if a given job meets the requirements to be the next to be
        started.

        Args:
            job (SchedulerJob): job's model instance

        Returns:
            bool: True if job is the next, False otherwise
        """
        if job.state != SchedulerJob.STATE_WAITING:
            self._logger.debug(
                'Job %s cannot start: has wrong state %s', job.id, job.state)
            return False

        # job has start time which was not reached yet: cannot run
        if (job.start_date is not None and
                job.start_date > datetime.utcnow()):
            self._logger.debug(
                'Job %s cannot start: start date not reached yet')
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
                        '%s but in %s use by active job %s',
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
                    '%s but in exclusive use by active job %s',
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

        # check if candidate job has the right position on all resource queues
        for resource, wait_queue in self._get_wait_queues(job):

            self._logger.debug(
                'Checking right position for job %s in queue of resource %s',
                job.id, resource)

            # candidate job is in first position: it has the right to go, now
            # verify the next queue
            if wait_queue[0].id == job.id:
                self._logger.debug('Job can start: it is first in queue')
                continue

            # candidate job has no start date but first job does: allowable
            # situation as long as the timeout of the candidate job would
            # fit in a time slot before the start time of the next job, so
            # we check it
            if job.start_date is None and wait_queue[0].start_date is not None:
                # job has no timeout: it cannot be started since we don't know
                # when it will end
                if job.timeout == 0:
                    self._logger.debug(
                        'Job cannot start: has no timeout to determine end '
                        'date')
                    return False

                end_date = datetime.utcnow() + timedelta(minutes=job.timeout+5)
                # candidate job would finish after the start of first job:
                # cannot execute
                if end_date >= wait_queue[0].start_date:
                    self._logger.debug(
                        'Job cannot start: end date would overlap with start '
                        'date of first job in queue')
                    return False

                # timeout of candidate job fits before first job with start
                # date,
                # now check if there isn't another job with no start date that
                # comes first
                i = 0
                for i in range(0, len(wait_queue)):
                    if wait_queue[i].start_date is None:
                        break
                if wait_queue[i].id == job.id:
                    self._logger.debug(
                        'Job can start: it fits before first job with start '
                        'date')
                    continue

            # any other case means job does not have the right position yet in
            # this queue
            self._logger.debug(
                'Job cannot start: does not have right position')
            return False

        self._logger.debug(
            'Job %s can start: has right position in all queues', job.id)
        return True
    # can_start()

    def enqueue(self, job):
        """
        Add a given job to the queues of its resources.

        Args:
            job (SchedulerJob): job's model instance

        Raises:
            ValueError: in case job has a unknown state
        """
        if job.state in (SchedulerJob.STATE_CLEANINGUP,
                         SchedulerJob.STATE_RUNNING):
            for res_mode in MODES:
                for resource in job.resources.get(res_mode, []):
                    self._active_jobs[res_mode][resource] = job

        elif job.state == SchedulerJob.STATE_WAITING:
            for _, wait_queue in self._get_wait_queues(job):
                # enqueue job in the correct position
                self._enqueue_job(wait_queue, job)
        else:
            raise ValueError(
                "Job {} in invalid state '{}'".format(job.id, job.state))
    # enqueue()

    def active_pop(self, job):
        """
        Remove a given job from the active listing

        Args:
            job (SchedulerJob): job's model instance
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

        Args:
            job (SchedulerJob): job's model instance
        """
        for _, wait_queue in self._get_wait_queues(job):
            found = None
            for i in range(0, len(wait_queue)):
                if wait_queue[i].id == job.id:
                    found = i
                    break
            if found is not None:
                wait_queue.pop(found)
                # TODO: remove queue if empty!!

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
        self._active_jobs = {MODE_EXCLUSIVE: {}, MODE_SHARED: {}}
    # reset()

# ResourcesManager
