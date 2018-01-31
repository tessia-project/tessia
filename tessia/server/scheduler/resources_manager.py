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
from tessia.server.db.models import SchedulerJob

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

GRACE_SECONDS = 300 # five minutes

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
        representation.append(str(self._wait_queues))

        representation.append('Active queues:')

        for mode in MODES:
            representation.append('Mode {}'.format(mode))
            representation.append(str(self._active_jobs[mode]))

        return '\n'.join(representation)
    # __str__()

    def _can_start_in_queue(self, job, resource, mode, queue):
        self._logger.debug(
            'Checking right position for job %s in queue of resource %s',
            job.id, resource)

        fits_before = False

        if not queue:
            self._logger.error(
                "Job %s not present in its own wait queue for resource %s",
                job.id,
                resource)
            return False

        first_job = queue[0][0]

        # Candidate job has no start date and can finish executing
        # before the start date of the first job (if any). It can also
        # execute withou conflict with any other jobs with start dates in
        # the queue since they are ordered by start date. We set a flag
        # to ignore these jobs as we traverse the queue. Jobs without a
        # start date still need to be checked.
        if job.start_date is None and first_job.start_date is not None:

            # Job has a finite timeout.
            if job.timeout > 0:
                end_date = (datetime.utcnow() +
                            timedelta(seconds=(job.timeout + GRACE_SECONDS)))

                # Job can finish before the first job.
                if end_date < first_job.start_date:
                    fits_before = True

        for other_job, other_mode in queue:

            # None of the jobs in the queue before the candidate job prevent
            # it from executing.
            if other_job.id == job.id:
                return True

            # We already decided that the candidate job
            # can start and finish before the earliest starting
            # job with a start date, check the next one in the queue.
            if fits_before and other_job.start_date is not None:
                continue

            # Modes do not conflict, check the next job in the queue.
            if mode == MODE_SHARED and other_mode == MODE_SHARED:
                continue

            return False

        # Should not happen, indicates can_start was called on an invalid job.
        self._logger.error(
            "Job %s not present in its own wait queue for resource %s",
            job.id,
            resource)
        return False

    @staticmethod
    def _check_overlap(start_a, start_b, timeout_a, timeout_b):
        """
        Check if two job intervals would overlap.

        Args:
            start_a, start_b (datetime.datetime): start times of the intervals
            timeout_a, timeout_b (int): duation in seconds of the intervals
                                        0 means an infinite interval

        Returns:
            bool: True if there is an overlap, False otherwise.
        Raises:
        """

        # Add grace seconds to account for processing time.
        end_a = start_a + timedelta(seconds=(timeout_a + GRACE_SECONDS))
        end_b = start_b + timedelta(seconds=(timeout_b + GRACE_SECONDS))

        # Both intervals are infinite, they must overlap.
        if timeout_a == 0 and timeout_b == 0:
            return True
        # Interval A is infinite, if it starts before B ends
        # there is an overlap.
        elif timeout_a == 0:
            if start_a <= end_b:
                return True
        # Interval B is infinite, if it starts before A ends
        # there is an overlap.
        elif timeout_b == 0:
            if start_b <= end_a:
                return True
        # Neither interval is infinite.
        # There is an overlap if A starts before B ends and ends after
        # B starts, since the end of A must be greater than the start of A.
        elif start_a <= end_b and end_a >= start_b:
            return True

        return False

    @staticmethod
    def _enqueue_job(queue, job, mode):
        """
        Enqueue the passed job in the provided resource queue at the correct
        position.

        Args:
            queue (list): the queue of the passed resource
            job (SchedulerJob): job to be enqueued
            mode (str): mode with which to insert this job in this queue

        Returns:
            int: position in queue where new job was added

        Raises:
            None
        """
        position = 0
        for position, queue_entry in enumerate(queue):

            queue_job = queue_entry[0]
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
        else:
            position = len(queue)

        queue.insert(position, (job, mode))

        return position
    # _enqueue_job()

    def _get_wait_queues(self, job, create=True):
        """
        Return the queues of the resources associated with the passed job

        Args:
            job (SchedulerJob): job's model instance
            create (bool): create queues if not already present

        Returns:
            list: all job queues of each resource in form
                  (resource_name, ressource_mode, job_queue),
                  if create is True, or
                  already existing queues if create is False
        """
        queues = []
        for res_mode in MODES:
            for resource in job.resources.get(res_mode, []):
                queue = self._wait_queues.get(resource)
                # no queue yet for this resource: create an empty one
                if queue is None and create:
                    self._wait_queues[resource] = []
                    queue = self._wait_queues[resource]

                if queue is not None:
                    queues.append((resource, res_mode, queue))

        return queues
    # _get_wait_queues()

    def active_pop(self, job):
        """
        Remove a given job from the active listing

        Args:
            job (SchedulerJob): job's model instance
        """
        for resource in job.resources.get(MODE_EXCLUSIVE, []):
            assert self._active_jobs[MODE_EXCLUSIVE][resource].id == job.id
            del self._active_jobs[MODE_EXCLUSIVE][resource]

        for resource in job.resources.get(MODE_SHARED, []):
            del self._active_jobs[MODE_SHARED][resource][job.id]

            if not self._active_jobs[MODE_SHARED][resource]:
                del self._active_jobs[MODE_SHARED][resource]

    # active_pop()

    def can_enqueue(self, job):
        """
        Check if the job can be inserted in the wait queues without
        overlapping with other jobs that have a start time.

        A job with no start time cannot conflict with other jobs since
        it will be started when possible.

        Args:
            job (SchedulerJob):  job to check

        Returns:
            bool: True if the job has no start date or if it has a start date
                 and doesn't conflict with other jobs with start dates.
                  False if the job has a start date and overlaps with other
                  jobs using the same resources (with non-shareable modes).
        Raises:
        """

        # Job has no start date, it cannot conflict with other jobs
        # with a start date.
        if job.start_date is None:
            return True

        # Job with a start date should not have an infinite timeout.
        if job.timeout == 0:
            return False

        now = datetime.utcnow()

        start_date = job.start_date

        # Expired start date, assume the job will be scheduled now.
        if job.start_date < now:
            start_date = now

        # Check if any active jobs would prevent this job from executing.
        for resource in job.resources.get(MODE_EXCLUSIVE, []):

            exclusive_job = self._active_jobs[MODE_EXCLUSIVE].get(resource)

            if exclusive_job is not None:
                if self._check_overlap(start_date, exclusive_job.start_date,
                                       job.timeout, exclusive_job.timeout):
                    return False

            shared_jobs = self._active_jobs[MODE_SHARED].get(resource)

            if shared_jobs is not None:
                for shared_job in shared_jobs.values():
                    if self._check_overlap(start_date, shared_job.start_date,
                                           job.timeout, shared_job.timeout):
                        return False

        for resource in job.resources.get(MODE_SHARED, []):
            exclusive_job = self._active_jobs[MODE_EXCLUSIVE].get(resource)

            if exclusive_job is not None:
                if self._check_overlap(start_date, exclusive_job.start_date,
                                       job.timeout, exclusive_job.timeout):
                    return False

        # Go through all of the resource queues of the candidate job
        # to check for overlaps with other waiting jobs that use the
        # same resources.
        for _, mode, queue in self._get_wait_queues(job, create=False):

            # Check all the jobs with starting times in this resource queue.
            for other_job, other_mode in queue:

                # No more jobs with start date on this queue, check the
                # next resource queue.
                if other_job.start_date is None:
                    break

                # No conflict because both jobs use the resource in
                # shared mode, check the next job in this queue.
                if other_mode == MODE_SHARED and mode == MODE_SHARED:
                    continue

                other_start_date = other_job.start_date

                if other_start_date < now:
                    other_start_date = now

                if self._check_overlap(start_date, other_start_date,
                                       job.timeout, other_job.timeout):
                    return False

        return True
    # can_enqueue()

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
            # Log as error since this should not be called on a job with an
            # invalid state.
            self._logger.error(
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

            exclusive_job = self._active_jobs[MODE_EXCLUSIVE].get(resource)

            if exclusive_job is not None:
                self._logger.debug(
                    'Job %s cannot start: needs exclusive use of resource '
                    '%s but in exclusive use by active job %s',
                    job.id,
                    resource,
                    exclusive_job.id)

                return False

            shared_jobs = self._active_jobs[MODE_SHARED].get(resource)

            if shared_jobs is not None:
                # the dict can't be empty since if it is we delete it in
                # active_pop
                self._logger.debug(
                    'Job %s cannot start: needs exclusive use of resource '
                    '%s but in shared use by active jobs',
                    job.id,
                    resource)

                return False

        # shared resources conflict with active jobs only in exclusive mode
        for resource in job.resources.get(MODE_SHARED, []):
            exclusive_job = self._active_jobs[MODE_EXCLUSIVE].get(resource)
            # a resource is in use: report conflict
            if exclusive_job is not None:
                self._logger.debug(
                    'Job %s cannot start: needs shared use of resource '
                    '%s but in exclusive use by active job %s',
                    job.id,
                    resource,
                    exclusive_job.id)
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

        # Check if candidate job has the right position on all resource queues.
        for resource, mode, queue in self._get_wait_queues(job):
            if not self._can_start_in_queue(job, resource, mode, queue):
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
        if job.state != SchedulerJob.STATE_WAITING:
            raise ValueError(
                "Job {} in invalid state '{}'".format(job.id, job.state))

        for _, mode, wait_queue in self._get_wait_queues(job):
            # enqueue job in the correct position
            self._enqueue_job(wait_queue, job, mode)
    # enqueue()

    def reset(self):
        """
        Reset all queues to empty state
        """
        self._wait_queues = {}

        # jobs that are currently running
        self._active_jobs = {MODE_EXCLUSIVE: {}, MODE_SHARED: {}}
    # reset()

    def set_active(self, job):
        """
        Set job as active. This prevents other jobs with conflicting
        resources from starting.

        Args:
            job (SchedulerJob)

        Raises:
            ValueError: in case job state is invalid
        """
        if job.state not in (SchedulerJob.STATE_CLEANINGUP,
                             SchedulerJob.STATE_RUNNING):
            raise ValueError(
                "Job {} in invalid state '{}'".format(job.id, job.state))

        for resource in job.resources.get(MODE_EXCLUSIVE, []):
            assert self._active_jobs[MODE_EXCLUSIVE].get(resource) is None
            self._active_jobs[MODE_EXCLUSIVE][resource] = job

        for resource in job.resources.get(MODE_SHARED, []):

            if self._active_jobs[MODE_SHARED].get(resource) is None:
                self._active_jobs[MODE_SHARED][resource] = {}

            self._active_jobs[MODE_SHARED][resource][job.id] = job
    # set_active()

    @staticmethod
    def validate_resources(resources):
        """
        Check if any resources appear twice (in the same mode
        or in two different modes).

        Some parts of the resource manager assume resources appear
        only once, so this needs to be checked before enqueuing jobs.

        Args:
            resources (dict): resources dictionary
        Returns:
            bool: True if there are no duplicates in all the mode lists
                  False otherwise (indicates unsafe dictionary)
        Raises:
        """
        all_resources = set()

        for mode in MODES:
            for resource in resources.get(mode, []):
                if resource in all_resources:
                    return False
                all_resources.add(resource)

        return True
    # validate_resources()

    def wait_pop(self, job):
        """
        Remove a given job from the wait queues

        Args:
            job (SchedulerJob): job's model instance
        """
        for resource, _, wait_queue in self._get_wait_queues(job):

            i = 0
            while (i < len(wait_queue)
                   and wait_queue[i][0].id != job.id):
                i += 1

            # i must be such that i != len(wait_queue) since we obtained
            # the wait_queue from _get_wait_queues, which implies the
            # job must be present.
            wait_queue.pop(i)
            if not wait_queue:
                del self._wait_queues[resource]

    # wait_pop()

# ResourcesManager
