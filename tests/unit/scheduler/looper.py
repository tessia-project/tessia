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

# because this is a test case
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-many-public-methods
# this one is because it's hard to make short test function names
# pylint: disable=invalid-name
# because of the coding guidelines
# pylint: disable=ungrouped-imports

from datetime import datetime
from tessia_engine.db import connection
from tessia_engine.db.models import SchedulerRequest
from tessia_engine.db.models import SchedulerJob
from tessia_engine.db.models import User
from tessia_engine.scheduler import looper
from tessia_engine.scheduler import resources_manager
from tessia_engine.scheduler import wrapper
from tests.unit.db.models import DbUnit
from unittest import mock

import os
import unittest

#
# CONSTANTS AND DEFINITIONS
#
FAKE_JOBS_DIR = '/tmp/test-looper/jobs-dir'

#
# CODE
#
class TestLooper(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        DbUnit.create_db()

    def setUp(self):

        patcher = mock.patch('tessia_engine.scheduler.looper.CONF',
                             autospec=True)

        patcher.start()

        self.addCleanup(patcher.stop)

        looper.CONF.get_config.return_value = (
            {'scheduler': {'jobs_dir': FAKE_JOBS_DIR}})

        patcher = mock.patch(
            'tessia_engine.scheduler.looper.resources_manager.ResourcesManager',
            autospec=True)

        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch(
            'tessia_engine.scheduler.looper.logging',
            autospect=True)

        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch(
            'tessia_engine.scheduler.looper.signal',
            autospect=True)

        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch(
            'tessia_engine.scheduler.looper.os',
            autospect=True)

        os_mock = patcher.start()
        self.addCleanup(patcher.stop)

        os_mock.getcwd.return_value = "/tmp/looper-test-cwd"

        patcher = mock.patch(
            'tessia_engine.scheduler.looper.multiprocessing',
            autospect=True)

        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch(
            'builtins.open',
            autospect=True)

        patcher.start()
        self.addCleanup(patcher.stop)

        looper.multiprocessing.get_start_method.return_value = 'forkserver'

        looper.multiprocessing.Process.return_value.pid = 100000

        self._session = connection.MANAGER.session

        self.addCleanup(self._session.close)

        self._requester = self._session.query(User).first()

        self._session.commit()

        self._looper = looper.Looper()

        self._looper_iterations = 0
        self._max_looper_iterations = 1

        def should_stop():
            if self._looper_iterations == self._max_looper_iterations:
                return True
            else:
                self._looper_iterations += 1
                return False

        self._looper.should_stop = should_stop

    def tearDown(self):
        self._session.query(SchedulerJob).delete()
        self._session.query(SchedulerRequest).delete()
        self._session.commit()

    @staticmethod
    def _make_echo_parameters(resources, sleep_time):
        parameters = []
        for mode in resources_manager.MODES:
            if (resources.get(mode) is not None
                    and len(resources.get(mode)) > 0):
                mode_directive = []
                mode_directive.append('USE')
                mode_directive.append(mode.upper())

                for resource in resources[mode]:
                    mode_directive.append(resource)

                parameters.append(' '.join(mode_directive))


        parameters.append('ECHO STARTING TO SLEEP')
        parameters.append('SLEEP {}'.format(sleep_time))
        parameters.append('ECHO DONE')

        return '\n'.join(parameters)

    def _make_request(self, resources, requester, sleep_time=1,
                      priority=1, timeout=0,
                      action_type=SchedulerRequest.ACTION_SUBMIT,
                      job_type='echo'):

        request = SchedulerRequest(
            requester_id=requester.id,
            action_type=action_type,
            job_type=job_type,
            submit_date=datetime.utcnow(),
            priority=priority,
            timeout=timeout,
            parameters=self._make_echo_parameters(resources, sleep_time)
        )

        return request

    @staticmethod
    def _make_resources(exclusive, shared=None):
        if shared is None:
            shared = []
        return {resources_manager.MODE_EXCLUSIVE: exclusive,
                resources_manager.MODE_SHARED: shared}

    def _make_job(self, resources_ex, resources_sh,
                  requester, priority=1, sleep_time=1,
                  state=SchedulerJob.STATE_WAITING,
                  pid=2):

        resources = self._make_resources(resources_ex, resources_sh)

        return SchedulerJob(
            requester_id=requester.id,
            priority=priority,
            job_type='echo',
            time_slot=SchedulerJob.SLOT_DEFAULT,
            state=state,
            resources=resources,
            parameters=self._make_echo_parameters(resources, sleep_time),
            description='test',
            submit_date=datetime.utcnow(),
            pid=pid
        )

    def test_should_stop(self):
        loop = looper.Looper()
        self.assertFalse(loop.should_stop())

    def test_init_bad_jobs_dir(self):
        looper.CONF.get_config.return_value = {'scheduler': {}}

        with self.assertRaises(RuntimeError):
            looper.Looper()

    def test_init_bad_mp_config(self):
        looper.multiprocessing.get_start_method.return_value = 'fork'

        with self.assertRaises(RuntimeError):
            looper.Looper()

    def test_init_manager_waiting_jobs(self):
        self._looper._resources_man.can_start.return_value = False

        jobs_with_resources = [
            self._make_job([], ['B'], self._requester),
            self._make_job(['A'], ['B'], self._requester)
        ]

        job_no_res = self._make_job([], [], self._requester)

        all_jobs = jobs_with_resources + [job_no_res]

        for job in all_jobs:
            self._session.add(job)

        self._session.commit()

        self._looper._init_manager()

        self._looper._resources_man.reset.assert_called_with()

        enqueued_job_ids = [
            call[0][0].id for call
            in self._looper._resources_man.enqueue.call_args_list
        ]

        self.assertEqual(enqueued_job_ids,
                         [job.id for job in jobs_with_resources])

    def test_init_manager_dead_job(self):
        self._looper._resources_man.can_start.return_value = False

        dead_job = self._make_job([], [], self._requester,
                                  state=SchedulerJob.STATE_RUNNING)

        self._session.add(dead_job)
        self._session.commit()

        now = datetime.utcnow()

        ret_code = 0

        self._mock_for_dead_job_no_comm(ret_code, now)

        self._looper._init_manager()

        self._looper._resources_man.reset.assert_called_with()

        self._looper._resources_man.enqueue.assert_not_called()

        # check if post_process did its job
        self.assertEqual(dead_job.state, SchedulerJob.STATE_COMPLETED)

    @staticmethod
    def _mock_for_dead_job_no_comm(ret_code, end_time):
        open.side_effect = [FileNotFoundError, open.return_value]

        open.return_value.__enter__.return_value.readlines.return_value = (
            [str(ret_code), end_time.strftime(wrapper.DATE_FORMAT)])

    @staticmethod
    def _mock_for_dead_job_no_cwd(ret_code, end_time):
        open.return_value.__enter__.return_value.read.return_value = (
            wrapper.WORKER_COMM + "\n"
        )

        looper.os.readlink.side_effect = FileNotFoundError

        open.return_value.__enter__.return_value.readlines.return_value = (
            [str(ret_code), end_time.strftime(wrapper.DATE_FORMAT)])

    def _mock_for_dead_job_bad_cwd(self, ret_code, end_time):
        open.return_value.__enter__.return_value.read.return_value = (
            wrapper.WORKER_COMM + "\n"
        )

        looper.os.readlink.return_value = self._looper._cwd + "#"

        looper.os.path.basename.side_effect = os.path.basename

        open.return_value.__enter__.return_value.readlines.return_value = (
            [str(ret_code), end_time.strftime(wrapper.DATE_FORMAT)])

    @staticmethod
    def _mock_for_running_job(job):

        open.return_value.__enter__.return_value.read.return_value = (
            wrapper.WORKER_COMM + "\n"
        )

        looper.os.readlink.return_value = '{}/{}'.format(FAKE_JOBS_DIR, job.id)

        looper.os.path.basename.side_effect = os.path.basename

    @staticmethod
    def _mock_for_unknown_job(job):

        open.return_value.__enter__.return_value.read.return_value = (
            "some-process"
        )

        looper.os.readlink.return_value = '{}/{}'.format(FAKE_JOBS_DIR, job.id)

        looper.os.path.basename.side_effect = os.path.basename

    def _test_init_manager_with_living_job(self, resources_ex, resources_sh):
        job = self._make_job(resources_ex, resources_sh, self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._session.add(job)
        self._session.commit()

        self._mock_for_running_job(job)

        self._looper._init_manager()

        if len(resources_ex) + len(resources_sh) > 0:
            self._looper._resources_man.enqueue.assert_called_with(job)
        else:
            self._looper._resources_man.enqueue.assert_not_called()

        self.assertEqual(job.state, SchedulerJob.STATE_RUNNING)

    def test_init_manager_living_job_with_res(self):
        self._test_init_manager_with_living_job(['A'], ['B'])

    def test_init_manager_living_job_with_shared_res(self):
        self._test_init_manager_with_living_job([], ['B'])

    def test_init_manager_living_job_no_res(self):
        self._test_init_manager_with_living_job([], [])

    def test_finish_jobs_living_job(self):
        job = self._make_job([], [], self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._session.add(job)
        self._session.commit()

        self._mock_for_running_job(job)

        self._looper._finish_jobs()

        self.assertEqual(job.state, SchedulerJob.STATE_RUNNING)

    def _test_finish_jobs_dead_job(self, job, _validate_pid_mock, ret_code):
        self._session.add(job)
        self._session.commit()

        now = datetime.utcnow()

        _validate_pid_mock(ret_code, now)

        self._looper._finish_jobs()

    def test_finish_jobs_dead_job_no_cwd_no_res_completed_2(self):
        job = self._make_job([], [], self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._test_finish_jobs_dead_job(job, self._mock_for_dead_job_no_cwd, 0)

        self.assertEqual(job.state, job.STATE_COMPLETED)

    def test_finish_jobs_dead_job_no_comm_with_res_failed(self):
        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._test_finish_jobs_dead_job(job,
                                        self._mock_for_dead_job_no_comm, 1)

        self.assertEqual(job.state, job.STATE_FAILED)

    def test_finish_jobs_dead_job_bad_cwd_with_res_failed_bad_ret(self):
        job = self._make_job([], ['B'], self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._test_finish_jobs_dead_job(job, self._mock_for_dead_job_bad_cwd,
                                        "not_a_number")

        self.assertEqual(job.state, job.STATE_FAILED)

    def test_finish_jobs_dead_job_bad_cwd_with_res_canceled(self):
        job = self._make_job([], ['B'], self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._test_finish_jobs_dead_job(job, self._mock_for_dead_job_bad_cwd,
                                        wrapper.RESULT_CANCELED)

        self.assertEqual(job.state, job.STATE_CANCELED)

    def test_finish_jobs_dead_job_bad_cwd_with_res_cancel_timeout(self):
        job = self._make_job([], ['B'], self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._test_finish_jobs_dead_job(job, self._mock_for_dead_job_bad_cwd,
                                        wrapper.RESULT_CANCELED_TIMEOUT)

        self.assertEqual(job.state, job.STATE_CANCELED)

    def test_start_jobs_can_start(self):
        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_WAITING)

        self._session.add(job)

        self._session.commit()

        self._looper._resources_man.can_start.return_value = True

        # cover the full start function here
        self._looper.start()

        (looper.multiprocessing.Process
         .return_value.start.assert_called_once_with())

        self.assertEqual(job.state, SchedulerJob.STATE_RUNNING)

    def test_start_jobs_cant_start(self):
        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_WAITING)

        self._session.add(job)

        self._session.commit()

        self._looper._resources_man.can_start.return_value = False

        self._looper._start_jobs()

        (looper.multiprocessing.Process
         .assert_not_called())

        (looper.multiprocessing.Process
         .return_value.start.assert_not_called())

        self.assertEqual(job.state, SchedulerJob.STATE_WAITING)

    def test_start_jobs_start_error(self):

        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_WAITING)

        self._session.add(job)

        self._session.commit()

        self._looper._resources_man.can_start.return_value = True

        looper.multiprocessing.ProcessError = RuntimeError

        (looper.multiprocessing.Process.return_value
         .start.side_effect) = looper.multiprocessing.ProcessError

        self._looper._start_jobs()

        self.assertEqual(job.state, SchedulerJob.STATE_WAITING)

    def test_start_exception(self):
        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_WAITING)

        self._session.add(job)

        self._session.commit()

        self._looper._resources_man.can_start.side_effect = RuntimeError

        with self.assertRaises(RuntimeError):
            self._looper.start()

        self.assertEqual(job.state, SchedulerJob.STATE_WAITING)

    def test_process_request_bad_action(self):
        request = self._make_request(self._make_resources(['A'], []),
                                     self._requester, action_type="#")

        self._session.add(request)
        self._session.commit()

        self._looper._process_pending_requests()

        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)

    def test_process_request_submit(self):
        request = self._make_request(self._make_resources(['A'], []),
                                     self._requester)

        self._session.add(request)
        self._session.commit()

        self._looper._process_pending_requests()

        job = self._session.query(SchedulerJob).one()

        self.assertEqual(job.state, SchedulerJob.STATE_WAITING)

        self.assertEqual(request.state, SchedulerRequest.STATE_COMPLETED)

    def test_process_request_submit_bad_job_type(self):
        request = self._make_request(self._make_resources(['A'], []),
                                     self._requester, job_type="#")

        self._session.add(request)
        self._session.commit()

        self._looper._process_pending_requests()

        self.assertEqual(self._session.query(SchedulerJob).count(),
                         0)

        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)

    def test_process_request_submit_parse_error(self):

        self._looper._machines['echo'] = mock.MagicMock()

        self._looper._machines['echo'].parse = mock.MagicMock(
            side_effect=RuntimeError)

        request = self._make_request(self._make_resources(['A'], []),
                                     self._requester)

        self._session.add(request)
        self._session.commit()

        self._looper._process_pending_requests()

        self.assertEqual(self._session.query(SchedulerJob).count(),
                         0)

        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)

    def test_cancel_request_waiting_job(self):
        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_WAITING)

        self._session.add(job)

        self._session.flush()

        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)

        request.job_id = job.id

        self._session.add(request)

        self._session.commit()

        self._looper._process_pending_requests()

        self.assertEqual(job.state, SchedulerJob.STATE_CANCELED)

    def _test_cancel_request_started_job(self, job):
        self._session.add(job)

        self._session.flush()

        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)

        request.job_id = job.id

        self._session.add(request)

        self._session.commit()

        self._mock_for_running_job(job)

        self._looper._init_manager()
        self._looper._process_pending_requests()

    def test_cancel_request_running_job(self):
        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._test_cancel_request_started_job(job)

        self.assertEqual(job.state, SchedulerJob.STATE_CLEANINGUP)

    def test_cancel_request_cleaning_up_job(self):
        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_CLEANINGUP)

        self._test_cancel_request_started_job(job)

        self.assertEqual(job.state, SchedulerJob.STATE_CANCELED)

    def test_cancel_request_running_job_dead_success(self):
        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._session.add(job)

        self._session.flush()

        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)

        request.job_id = job.id

        self._session.add(request)

        self._session.commit()

        self._mock_for_dead_job_no_cwd(0, datetime.utcnow())

        self._looper._process_pending_requests()

        self.assertEqual(job.state, SchedulerJob.STATE_COMPLETED)
        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)

    def test_cancel_request_running_job_unknown(self):

        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_RUNNING)

        self._session.add(job)

        self._session.flush()

        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)

        request.job_id = job.id

        self._session.add(request)

        self._session.commit()

        self._mock_for_unknown_job(job)

        self._looper._process_pending_requests()

        self.assertEqual(job.state, SchedulerJob.STATE_RUNNING)
        self.assertEqual(request.state, SchedulerRequest.STATE_PENDING)

        looper.os.kill.assert_not_called()

    def test_cancel_request_no_job(self):
        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)

        request.job_id = 1

        self._session.add(request)

        self._session.commit()

        self._looper._process_pending_requests()

        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)

    def test_cancel_request_finished_job(self):

        job = self._make_job(['A'], [], self._requester,
                             state=SchedulerJob.STATE_COMPLETED)

        self._session.add(job)

        self._session.flush()

        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)

        request.job_id = 1

        self._session.add(request)

        self._session.commit()

        self._looper._process_pending_requests()

        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)

if __name__ == '__main__':
    unittest.main()
