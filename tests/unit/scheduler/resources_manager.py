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
Unit test for the scheduler's looper module
"""

#
# IMPORTS
#
from datetime import datetime
from datetime import timedelta
from tessia_engine.db.models import SchedulerJob
from tessia_engine.scheduler import resources_manager
from unittest import TestCase
from unittest.mock import patch

import unittest

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
# pylint: disable=protected-access
class TestResourceManager(TestCase):
    """
    Unit test for the resource manager module
    """
    def setUp(self):
        """
        Prepare the necessary mocks at the beginning of each testcase.
        """
        # logging module
        patcher = patch.object(resources_manager, 'logging', spec_set=True)
        mock_logging = patcher.start()
        self._mock_logger = mock_logging.getLogger.return_value
        self.addCleanup(patcher.stop)

        self._res_man = resources_manager.ResourcesManager()

        patcher = patch.object(resources_manager,
                               'datetime', autospect=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self._fixed_now = datetime.utcnow()

        resources_manager.datetime.utcnow.return_value = self._fixed_now

        self._curr_job_id = 0

    def _make_job(self, resources_ex=None, resources_sh=None,
                  state=SchedulerJob.STATE_WAITING, timeout=0):
        """
        Build a job with sane defaults.
        """
        now = datetime.utcnow()

        if resources_ex is None:
            resources_ex = []

        if resources_sh is None:
            resources_sh = []

        resources = {
            resources_manager.MODE_EXCLUSIVE: resources_ex,
            resources_manager.MODE_SHARED: resources_sh
        }

        # We don't use session-managed instances, so we manually
        # set and increment the job ids.
        job = SchedulerJob(
            id=self._curr_job_id,
            requester_id=1,
            priority=3,
            time_slot=SchedulerJob.SLOT_DEFAULT,
            submit_date=now,
            state=state,
            job_type='test',
            resources=resources,
            description="test job",
            parameters="",
            result='Waiting for resources',
            timeout=timeout
        )

        self._curr_job_id += 1

        return job

    def test_validate_resources(self):
        """
        Test resource validator, once with a valid resource and once
        with bad resources.
        """

        valid_resources = {
            resources_manager.MODE_SHARED: ['A'],
            resources_manager.MODE_EXCLUSIVE: ['B']
        }

        self.assertTrue(self._res_man.validate_resources(valid_resources))

        bad_resources = {
            resources_manager.MODE_SHARED: ['A'],
            resources_manager.MODE_EXCLUSIVE: ['A']
        }

        self.assertFalse(self._res_man.validate_resources(bad_resources))

    def test_can_enqueue_empty(self):
        """
        Test can_enqueue function with empty waiting queues.
        """

        # Test a job with no start date
        job = self._make_job(['A'], ['B'])

        self.assertTrue(self._res_man.can_enqueue(job))

        # Test a job with a start date, should work since
        # there is no other job in the queues.
        job.start_date = self._fixed_now + timedelta(minutes=5)

        job.timeout = 1

        self.assertTrue(self._res_man.can_enqueue(job))

    def test_can_enqueue_no_start_date(self):
        """
        Test can_enqueue when the job in the queue has no start date.
        """

        # No start date, won't block the next job we check.
        job = self._make_job(['A'], ['B'])

        self._res_man.enqueue(job)

        job = self._make_job(['A'], ['B'], timeout=10)

        job.start_date = self._fixed_now

        self.assertTrue(self._res_man.can_enqueue(job))

    def test_can_enqueue_start_date_infinite(self):
        """
        Test that a job with a start date and infinite timeout
        causes can_enqueue to return false.
        """

        job = self._make_job(['A'], ['B'])
        job.start_date = self._fixed_now

        self.assertFalse(self._res_man.can_enqueue(job))

    def test_can_enqueue_shared(self):
        """
        Test can_enqueue when the job in the queue has a start date
        but the common resource is reserved in shared mode.
        """

        job = self._make_job([], ['B'], timeout=10)

        job.start_date = self._fixed_now

        self._res_man.enqueue(job)

        job = self._make_job([], ['B'], timeout=10)

        # Exercise the path that fixes the start date to now
        # if it expired.
        job.start_date = self._fixed_now - timedelta(seconds=1)

        self.assertTrue(self._res_man.can_enqueue(job))

    def test_can_enqueue_overlap(self):
        """
        Test can_enqueue with various time interval overlap scenarios.
        """

        future_start_date = self._fixed_now + timedelta(
            minutes=5, seconds=resources_manager.GRACE_SECONDS)

        timeout = 10

        # Add one job with a timeout and one infinite job.
        # It shouldn't be possible for a waiting job with a
        # start date and infinite timeout to be in the queues,
        # but it will help us check some branches and if the resource
        # manager still works in these cases.
        job = self._make_job(['A'], ['B'])

        job.start_date = future_start_date

        job.timeout = timeout

        self._res_man.enqueue(job)

        job = self._make_job(['C'], ['D'])

        job.start_date = future_start_date

        self._res_man.enqueue(job)

        # Fits before
        job = self._make_job(['A'], [], timeout=10)

        job.start_date = self._fixed_now

        self.assertTrue(self._res_man.can_enqueue(job))

        # Overlaps
        job.timeout = ((future_start_date - self._fixed_now).total_seconds())

        self.assertFalse(self._res_man.can_enqueue(job))

        # Fits after
        job.start_date = future_start_date + timedelta(
            seconds=(resources_manager.GRACE_SECONDS + timeout + 5))

        job.timeout = 5

        self.assertTrue(self._res_man.can_enqueue(job))

        # Check against the infinite job in the queue.
        job = self._make_job(['C'], [])

        # Overlaps
        job.start_date = future_start_date

        job.timeout = 5

        self.assertFalse(self._res_man.can_enqueue(job))

        # Finishes before

        job.start_date = self._fixed_now

        job.timeout = 10

        self.assertTrue(self._res_man.can_enqueue(job))

        # Add a job in the queue with an expired start date
        job = self._make_job(['E'], [], timeout=10)

        job.start_date = self._fixed_now - timedelta(seconds=1)

        self._res_man.enqueue(job)

        job = self._make_job(['E'], [], timeout=10)

        job.start_date = self._fixed_now

        # Overlap
        self.assertFalse(self._res_man.can_enqueue(job))

    def test_can_enqueue_with_active_jobs(self):
        """
        Test can_enqueue with various states of the active job sets.

        Also test set_active/active_pop for the jobs in these sets.
        """
        future_start_date = self._fixed_now + timedelta(
            minutes=5, seconds=resources_manager.GRACE_SECONDS)

        # Add a job to the active lists to check against.
        active_job = self._make_job(['A'], ['B'], SchedulerJob.STATE_RUNNING)

        active_job.start_date = self._fixed_now

        active_job.timeout = 10

        self._res_man.set_active(active_job)

        self.assertEqual(
            active_job,
            self._res_man._active_jobs[resources_manager.MODE_EXCLUSIVE]['A'])

        self.assertIn(
            active_job.id,
            self._res_man._active_jobs[resources_manager.MODE_SHARED]['B'])

        # Check overlapping jobs

        # Exclusive-Exclusive
        job = self._make_job(['A'], [], timeout=10)

        job.start_date = self._fixed_now

        self.assertFalse(self._res_man.can_enqueue(job))

        # Exclusive-Shared
        job = self._make_job([], ['A'], timeout=10)

        job.start_date = self._fixed_now

        self.assertFalse(self._res_man.can_enqueue(job))

        # Shared-Exclusive
        job = self._make_job(['B'], [], timeout=10)

        job.start_date = self._fixed_now

        self.assertFalse(self._res_man.can_enqueue(job))

        # Check non-overlapping jobs

        # Exclusive-Exclusive
        job = self._make_job(['A'], [], timeout=10)

        job.start_date = future_start_date

        self.assertTrue(self._res_man.can_enqueue(job))

        # Exclusive-Shared
        job = self._make_job([], ['A'], timeout=10)

        job.start_date = future_start_date

        self.assertTrue(self._res_man.can_enqueue(job))

        # Shared-Exclusive
        job = self._make_job(['B'], [], timeout=10)

        job.start_date = future_start_date

        self.assertTrue(self._res_man.can_enqueue(job))

        # Add another job to shared active to test set_active/active_pop
        # with more than one sharing job.
        other_active_job = self._make_job(
            [], ['B'], SchedulerJob.STATE_RUNNING)

        self._res_man.set_active(other_active_job)

        self._res_man.active_pop(other_active_job)

        self._res_man.active_pop(active_job)

    def test_enqueue_not_waiting(self):
        """
        Test enqueueing a job not in the waiting state.
        """

        job = self._make_job(['B'], [])
        job.state = SchedulerJob.STATE_COMPLETED

        with self.assertRaises(ValueError):
            self._res_man.enqueue(job)

    def test_enqueue(self):
        """
        Test enqueuing a job in various scenarios.
        """

        # We don't have to worry about grace seconds since they are not
        # used when enqueueing, only in can_enqueue/can_start

        future_start_date = self._fixed_now + timedelta(seconds=10)

        job_no_start_date_hi_prio = self._make_job(['A'], [])

        self._res_man.enqueue(job_no_start_date_hi_prio)

        middle_job = self._make_job(['A'], [])

        middle_job.start_date = future_start_date

        self._res_man.enqueue(middle_job)

        first_job = self._make_job(['A'], [])

        first_job.start_date = future_start_date - timedelta(seconds=5)

        self._res_man.enqueue(first_job)

        last_job = self._make_job(['A'], [])

        last_job.start_date = future_start_date + timedelta(seconds=5)

        self._res_man.enqueue(last_job)

        # We also test jobs with the same start date as last_job
        # but different priorities/submission dates

        last_job_hi_prio = self._make_job(['A'], [])

        last_job_hi_prio.start_date = last_job.start_date

        last_job_hi_prio.priority = last_job.priority - 1

        self._res_man.enqueue(last_job_hi_prio)

        last_job_lo_prio = self._make_job(['A'], [])

        last_job_lo_prio.start_date = last_job.start_date

        last_job_lo_prio.priority = last_job.priority + 1

        self._res_man.enqueue(last_job_lo_prio)

        last_job_submitted_before = self._make_job(['A'], [])

        last_job_submitted_before.start_date = last_job.start_date

        last_job_submitted_before.submit_date = (
            last_job.submit_date - timedelta(seconds=1))

        self._res_man.enqueue(last_job_submitted_before)

        last_job_submitted_after = self._make_job(['A'], [])

        last_job_submitted_after.start_date = last_job.start_date

        last_job_submitted_after.submit_date = (
            last_job.submit_date + timedelta(seconds=1))

        self._res_man.enqueue(last_job_submitted_after)

        job_no_start_date_lo_prio = self._make_job(['A'], [])

        self._res_man.enqueue(job_no_start_date_lo_prio)

        wait_queue = [job for job, mode in self._res_man._wait_queues['A']]

        expected_wait_queue = [
            first_job,
            middle_job,
            last_job_hi_prio,
            last_job_submitted_before,
            last_job,
            last_job_submitted_after,
            last_job_lo_prio,
            job_no_start_date_hi_prio,
            job_no_start_date_lo_prio
            ]

        self.assertEqual(wait_queue, expected_wait_queue)

        # Cover the __str__ method, there isn't anything really smart
        # to do with the result other than ensuring it doesn't crash.

        self.assertTrue(len(str(self._res_man)) > 0)

        # Test wait_pop by popping all the jobs we enqueued.
        # Do it in reverse order otherwise the wait pop function
        # will immediately find the correct job to pop
        for job in reversed(wait_queue):
            self._res_man.wait_pop(job)

        for queue in self._res_man._wait_queues.values():
            self.assertEqual(len(queue), 0)

    def test_set_active_not_running(self):
        """
        Test setting a job with an invalid state as active.
        """
        job = self._make_job(['A'], [])

        job.state = SchedulerJob.STATE_WAITING

        with self.assertRaises(ValueError):
            self._res_man.set_active(job)

    def test_set_active_shared(self):
        """
        Test setting two jobs with the same shared resource to
        exercise all paths for shared active sets.

        set_active with jobs with exclusive resources is already covered
        by other tests.
        """

        job_1 = self._make_job([], ['A'], SchedulerJob.STATE_RUNNING)

        self._res_man.set_active(job_1)

        job_2 = self._make_job([], ['A'], SchedulerJob.STATE_RUNNING)

        self._res_man.set_active(job_2)

        active_jobs = set(
            self._res_man._active_jobs[resources_manager.MODE_SHARED]
            ['A'].keys()
        )

        expected_active_jobs = set([job.id for job in [job_1, job_2]])

        self.assertEqual(active_jobs,
                         expected_active_jobs)

    def test_can_start(self):
        """
        Test can_start in various scenarios.
        """

        # Job in invalid state.
        job = self._make_job(['A'], ['B'], SchedulerJob.STATE_COMPLETED)

        self.assertFalse(self._res_man.can_start(job))

        job = self._make_job(['A'], ['B'])

        # Job has not reached start date.
        job.start_date = self._fixed_now + timedelta(seconds=1)

        self._res_man.enqueue(job)

        self.assertFalse(self._res_man.can_start(job))

        self._res_man.wait_pop(job)

        # Test active set checks

        other_job = self._make_job(['A'], ['B'], SchedulerJob.STATE_RUNNING)

        self._res_man.set_active(other_job)

        # Exclusive-Shared conflict
        job = self._make_job(['B'], [])

        self._res_man.enqueue(job)

        self.assertFalse(self._res_man.can_start(job))

        self._res_man.wait_pop(job)

        # Exclusive-Exclusive conflict
        job = self._make_job(['A'], [])

        self._res_man.enqueue(job)

        self.assertFalse(self._res_man.can_start(job))

        self._res_man.wait_pop(job)

        # Shared-Exclusive conflict
        job = self._make_job([], ['A'])

        self._res_man.enqueue(job)

        self.assertFalse(self._res_man.can_start(job))

        self._res_man.wait_pop(job)

        # No conflict, first in all queues
        job = self._make_job(['C'], ['D'])

        self._res_man.enqueue(job)

        self.assertTrue(self._res_man.can_start(job))

        # Test with a timeslot that is not current.
        job.time_slot = SchedulerJob.SLOT_NIGHT

        self.assertFalse(self._res_man.can_start(job))

        self._res_man.wait_pop(job)

        # Test wait queue checks

        self._res_man.active_pop(other_job)

        job = self._make_job(['A'], ['B'])

        # Check if can_start reported an error (calling can_start
        # with a job that wasn't enqueued).
        logger_error_call_count = self._mock_logger.error.call_count

        self.assertFalse(self._res_man.can_start(job))

        self.assertEqual(self._mock_logger.error.call_count,
                         logger_error_call_count + 1)

        # Test another path that detects that the job wasn't enqueued,
        # when another job is in the queue.

        other_job.state = SchedulerJob.STATE_WAITING

        seconds_after_now = 10

        other_job.start_date = self._fixed_now + timedelta(
            seconds=(resources_manager.GRACE_SECONDS
                     + seconds_after_now))

        self._res_man.enqueue(other_job)

        self.assertFalse(self._res_man.can_start(job))

        self.assertEqual(self._mock_logger.error.call_count,
                         logger_error_call_count + 2)

        # Now properly enqueue the job, and test the checks against
        # other_job.

        self._res_man.enqueue(job)

        # job has na infinite timeout, so it cannot start before
        # other job.
        self.assertFalse(self._res_man.can_start(job))

        # job has a finite timeout but doesn't end before other_job
        # has to start
        job.timeout = seconds_after_now + 5

        self.assertFalse(self._res_man.can_start(job))

        # job has a finite timeout and ends before other_job

        job.timeout = seconds_after_now - 5

        self.assertTrue(self._res_man.can_start(job))

    def test_check_overlap(self):
        """
        Test cases not previously covered for the _check_overlap function.

        The function has to be tested directly since some cases cannot
        happen through public interfaces (because jobs with start time
        and an infinte timeout are detected before this function can
        be called).

        It is still useful for the function to work correctly in this cases.
        """

        # both timeouts are infinite
        self.assertTrue(
            self._res_man._check_overlap(self._fixed_now, self._fixed_now,
                                         0, 0))

        # timeout a is infinite and overlaps
        self.assertTrue(
            self._res_man._check_overlap(self._fixed_now, self._fixed_now,
                                         0, 1))

        # timeout a is infinte but starts after interval b ends
        self.assertFalse(
            self._res_man._check_overlap(
                self._fixed_now
                + timedelta(seconds=(2 + resources_manager.GRACE_SECONDS)),
                self._fixed_now, 0, 1))

if __name__ == '__main__':
    unittest.main()
