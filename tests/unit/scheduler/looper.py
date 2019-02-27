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
from tessia.server.db import connection
from tessia.server.db.models import SchedulerRequest
from tessia.server.db.models import SchedulerJob
from tessia.server.db.models import System, SystemState
from tessia.server.db.models import User
from tessia.server.scheduler import looper
from tessia.server.scheduler import resources_manager
from tessia.server.scheduler import wrapper
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch
from unittest.mock import sentinel

import os

#
# CONSTANTS AND DEFINITIONS
#
FAKE_JOBS_DIR = '/tmp/test-looper/jobs-dir'

#
# CODE
#
# pylint: disable=too-many-public-methods
class TestLooper(TestCase):
    """
    Unit test for the looper module
    """
    @classmethod
    def setUpClass(cls):
        """
        Create the test database once at the beginning of the test module
        usage
        """
        DbUnit.create_db()
    # setUpClass()

    def setUp(self):
        """
        Prepare the necessary mocks at the beginning of each testcase.
        """
        # mock config file for a fake jobs' directory
        patcher = patch.object(looper, 'CONF', autospec=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        looper.CONF.get_config.return_value = (
            {'scheduler': {'jobs_dir': FAKE_JOBS_DIR}})

        # resources manager
        patcher = patch.object(
            looper.resources_manager, 'ResourcesManager', autospec=True)
        mock_resources_man_constructor = patcher.start()
        self._mock_resources_man = MagicMock()
        mock_resources_man_constructor.return_value = self._mock_resources_man
        self.addCleanup(patcher.stop)

        # logging module
        patcher = patch.object(looper, 'logging', autospect=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        # signal module
        patcher = patch.object(looper, 'signal', autospect=True)
        self._mock_signal = patcher.start()
        self._mock_signal.SIGTERM = sentinel.SIGTERM
        self._mock_signal.SIGKILL = sentinel.SIGKILL
        self.addCleanup(patcher.stop)

        # os module
        patcher = patch.object(looper, 'os', autospect=True)
        self._mock_os = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_os.getcwd.return_value = "/tmp/looper-test-cwd"
        self._mock_os.path.basename = os.path.basename

        # multiprocessing module
        patcher = patch.object(looper, 'multiprocessing', autospec=True)
        self._mock_mp = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_mp.get_start_method.return_value = 'forkserver'
        self._mock_mp.Process.return_value.pid = 100000

        # make should_run flag alternate between True and False so that loop()
        # will always run 1 iteration only
        def custom_getattr(self, name):
            """Revert flag when _should_run is retrieved"""
            attr = object.__getattribute__(self, name)
            if name == '_should_run':
                self._should_run = not attr
            return attr
        looper.Looper.__getattribute__ = custom_getattr

        # mock sleep to speed up loop()
        patcher = patch.object(looper.time, 'sleep')
        patcher.start()
        self.addCleanup(patcher.stop)

        # open built-in function
        patcher = patch.object(looper, 'open', autospect=True)
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)

        # db session
        self._session = connection.MANAGER.session
        self.addCleanup(self._session.close)

        # the user login for creating requests
        self._requester = self._session.query(User).first()

        # create the instance for convenient usage by testcases
        self._looper = looper.Looper()
    # setUp()

    def tearDown(self):
        """
        Remove all request and jobs entries at the end of each testcase.
        """
        self._session.query(SchedulerRequest).delete()
        self._session.query(SchedulerJob).delete()
        self._session.commit()
    # tearDown()

    @staticmethod
    def _make_echo_parameters(resources, sleep_time):
        """
        Generate input to be used as parameters when submitting a request to
        start an echo state machine.

        Args:
            resources (dict): resources to be used by the job
            sleep_time (str): time in seconds to be used in echo instructions

        Returns:
            str: the machine parameters
        """
        parameters = []
        for mode in resources_manager.MODES:
            if resources.get(mode):
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
                      job_type='echo', commit=False):
        """
        Create an instance of a scheduler's request to start an echo state
        machine using the passed parameters

        Args:
            resources (dict): resources allocated to the job
            requester (User): User's model instance
            sleep_time (int): to be used in creating machine parameters
            priority (int): job's priority
            timeout (int): job's timeout in seconds
            action_type (str): one of the ACTION_* constants
            job_type (str): state machine type
            commit (bool): whether to commit entry to db

        Returns:
            SchedulerRequest: the scheduler's request
        """
        request = SchedulerRequest(
            requester_id=requester.id,
            action_type=action_type,
            job_type=job_type,
            submit_date=datetime.utcnow(),
            priority=priority,
            timeout=timeout,
            parameters=self._make_echo_parameters(resources, sleep_time)
        )

        if commit is True:
            self._session.add(request)
            self._session.commit()

        return request
    # _make_request()

    @staticmethod
    def _make_resources(exclusive, shared=None):
        """
        Generate a dict containing job resources allocated in the different
        modes.

        Args:
            exclusive (list): resources allocated in exclusive mode
            shared (list): resources allocated in shared mode

        Returns:
            dict: resources to be allocated in a job
        """
        if shared is None:
            shared = []
        return {resources_manager.MODE_EXCLUSIVE: exclusive,
                resources_manager.MODE_SHARED: shared}
    # _make_resources()

    def _make_job(self, resources_ex, resources_sh, requester, priority=1,
                  sleep_time=1, state=SchedulerJob.STATE_WAITING, pid=2,
                  commit=False):
        """
        Create a new job instance with the passed parameters and return it

        Args:
            resources_ex (list): exclusive resources allocated to the job
            resources_sh (list): shared resources allocated to the job
            requester (User): User's model instance
            priority (int): job's priority
            sleep_time (int): to be used in creating machine parameters
            state (str): one of the STATE_* constants
            pid (int): pid of the process associated with the job
            commit (bool): whether to commit job to db

        Returns:
            SchedulerJob: the scheduler's job entry
        """
        resources = self._make_resources(resources_ex, resources_sh)

        new_job = SchedulerJob(
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

        if commit is True:
            self._session.add(new_job)
            self._session.commit()

        return new_job
    # _make_job()

    def _make_alive_job(self, res_exc=None, res_shared=None):
        """
        Create and validate a running job by performing the normal flow of
        execution: request submission, loop to create job, loop to get
        job running.

        Args:
            res_exc (list): resources allocated in exclusive mode
            res_shared (list): resources allocated in shared mode

        Returns:
            SchedulerJob: model's instance
        """
        if res_exc is None:
            res_exc = ['lpar0']
        if res_shared is None:
            res_shared = ['cpc0']

        request = self._make_request(
            self._make_resources(res_exc, res_shared),
            self._requester,
            commit=True)

        # force the job not to be started yet
        self._mock_resources_man.can_start.return_value = False

        # run one loop to get the request turned to job
        self._looper.loop()

        # confirm states
        job = SchedulerJob.query.filter_by(id=request.job_id).one()
        self.assertEqual(job.state, job.STATE_WAITING, job.result)
        self.assertEqual(request.state, SchedulerRequest.STATE_COMPLETED)

        # run one loop to get the job started
        self._mock_resources_man.can_start.return_value = True
        self._patch_alive_process(job)
        self._looper.loop()
        self.assertEqual(job.state, job.STATE_RUNNING, job.result)

        return job
    # _make_alive_job()

    def _patch_dead_process_bad_cwd(self, ret_code, end_time):
        """
        Patch with mocks to simulate the case where job's process is alive but
        has a wrong cwd

        Args:
            ret_code (int): return code to include in results file
            end_time (str): end date to include in results file
        """
        # make sure mock is clean
        self._mock_open.side_effect = None

        # contents of comm file
        self._mock_open.return_value.__enter__.return_value.read. \
        return_value = wrapper.WORKER_COMM + "\n"

        # cwd has a wrong path
        self._mock_os.readlink.return_value = '/some/wrong/path'

        # contents of result file
        self._mock_open.return_value.__enter__.return_value.readlines. \
        return_value = (
            [str(ret_code), end_time.strftime(wrapper.DATE_FORMAT)])
    # _patch_dead_process_bad_cwd()

    def _patch_dead_process_no_comm(
            self, ret_code, end_time, cleanup_code=None):
        """
        Patch with mocks to simulate the case where job's process died because
        /proc/$pid/comm does not exist.

        Args:
            ret_code (int): return code to include in results file
            end_time (str): end date to include in results file
            cleanup_code (int): cleanup code to include in results file
        """
        # contents of result file

        if cleanup_code is not None:
            readlines_return = (
                [str(ret_code), str(cleanup_code),
                 end_time.strftime(wrapper.DATE_FORMAT)])
        else:
            readlines_return = (
                [str(ret_code), end_time.strftime(wrapper.DATE_FORMAT)])

        self._mock_open.return_value.__enter__.return_value.readlines. \
        return_value = readlines_return

        # mock the open function to failed on first call (no /proc/$pid/comm)
        # and return a result file on second call.
        self._mock_open.side_effect = [
            FileNotFoundError, self._mock_open.return_value]
    # _patch_dead_process_no_comm()

    def _patch_dead_process_noread_comm(self, ret_code, end_time):
        """
        Patch with mocks to simulate the case where job's process died because
        /proc/$pid/comm cannot be read (process belongs to another user).

        Args:
            ret_code (int): return code to include in results file
            end_time (str): end date to include in results file
        """
        # contents of result file
        self._mock_open.return_value.__enter__.return_value.readlines. \
        return_value = (
            [str(ret_code), end_time.strftime(wrapper.DATE_FORMAT)])

        # mock the open function to failed on first call (no /proc/$pid/comm)
        # and return a result file on second call.
        self._mock_open.side_effect = [
            PermissionError, self._mock_open.return_value]
    # _patch_dead_process_noread_comm()

    def _patch_dead_process_no_cwd(self, ret_code, end_time):
        """
        Patch with mocks to simulate the case where job's process died because
        /proc/$pid/cwd points to inexistent directory

        Args:
            ret_code (int): return code to include in results file
            end_time (str): end date to include in results file
        """
        # make sure mock is clean
        self._mock_open.side_effect = None

        # return a valid content for reading /proc/$pid/comm
        self._mock_open.return_value.__enter__.return_value.read. \
        return_value = wrapper.WORKER_COMM + "\n"

        # fail the call to open /proc/$pid/cwd file
        self._mock_os.readlink.side_effect = FileNotFoundError

        # return content of results file
        self._mock_open.return_value.__enter__.return_value.readlines.\
        return_value = (
            [str(ret_code), end_time.strftime(wrapper.DATE_FORMAT)]
        )
    # _patch_dead_process_no_cwd()

    def _patch_dead_process_noread_cwd(self, ret_code, end_time):
        """
        Patch with mocks to simulate the case where job's process died because
        /proc/$pid/cwd is unreadable (process belongs to another user)

        Args:
            ret_code (int): return code to include in results file
            end_time (str): end date to include in results file
        """
        # make sure mock is clean
        self._mock_open.side_effect = None

        # return a valid content for reading /proc/$pid/comm
        self._mock_open.return_value.__enter__.return_value.read. \
        return_value = wrapper.WORKER_COMM + "\n"

        # fail the call to open /proc/$pid/cwd file
        self._mock_os.readlink.side_effect = PermissionError

        # return content of results file
        self._mock_open.return_value.__enter__.return_value.readlines.\
        return_value = (
            [str(ret_code), end_time.strftime(wrapper.DATE_FORMAT)]
        )
    # _patch_dead_process_noread_cwd()

    def _patch_alive_process(self, job):
        """
        Prepare mocks to simulate that the passed job's process is still
        running.

        Args:
            job (SchedulerJob): model's instance
        """
        self._mock_open.return_value.__enter__.return_value.read. \
        return_value = wrapper.WORKER_COMM + "\n"

        self._mock_os.readlink.return_value = '{}/{}'.format(
            FAKE_JOBS_DIR, job.id)
    # _patch_alive_process()

    def _patch_unknown_process(self, job):
        """
        Simulate the scenario where the pid of a job belongs to a non tessia
        job.

        Args:
            job (SchedulerJob): model's instance
        """
        self._mock_open.return_value.__enter__.return_value.read. \
        return_value = "some-process"

        self._mock_os.readlink.return_value = (
            '{}/{}'.format(FAKE_JOBS_DIR, job.id)
        )
    # _patch_unknown_process()

    def test_db_exception(self):
        """
        Simulate a scenario where some db exception occurs
        """
        patcher = patch.object(looper, 'SchedulerJob')
        patcher.start()
        self.addCleanup(patcher.stop)
        looper.SchedulerJob.query.filter.side_effect = RuntimeError

        with self.assertRaises(RuntimeError):
            self._looper.loop()
    # test_db_exception()

    def test_init_alive_process(self):
        """
        Verify if upon initialization correctly enqueues a job in running
        state whose process is still alive
        """
        # job with exclusive and shared resources allocated
        job = self._make_alive_job(['lpar0'], ['cpc0'])
        self._mock_resources_man.set_active.reset_mock()
        self._looper = looper.Looper()

        self.assertEqual(
            self._mock_resources_man.set_active.call_args[0][0].id,
            job.id)

        # job with only exclusive resource allocated
        job = self._make_alive_job(['lpar0'], [])
        self._mock_resources_man.set_active.reset_mock()
        self._looper = looper.Looper()

        self.assertEqual(
            self._mock_resources_man.set_active.call_args[0][0].id,
            job.id)

        # job with only shared resource allocated
        job = self._make_alive_job([], ['cpc0'])
        self._mock_resources_man.set_active.reset_mock()
        self._looper = looper.Looper()

        self.assertEqual(
            self._mock_resources_man.set_active.call_args[0][0].id,
            job.id)

        # job with no resource allocated
        job = self._make_alive_job([], [])
        self._mock_resources_man.set_active.reset_mock()
        self._looper = looper.Looper()
        self._mock_resources_man.set_active.assert_not_called()

    # test_init_alive_process()

    def test_init_bad_conf(self):
        """
        Exercise bad configuration scenarios
        """
        # verify if Looper raises exception when no job dir is configured.
        looper.CONF.get_config.return_value = {'scheduler': {}}
        with self.assertRaises(RuntimeError):
            looper.Looper()

        # verify the scenario where multiprocessing was previously set with the
        # wrong mode.
        self._mock_mp.set_start_method.side_effect = RuntimeError
        self._mock_mp.get_start_method.return_value = 'fork'
        with self.assertRaises(RuntimeError):
            looper.Looper()

    # test_init_bad_conf()

    def test_init_waiting_jobs(self):
        """
        Test if jobs in waiting state are correctly added to the queues in
        resource manager upon Looper initialization.
        """
        self._mock_resources_man.can_start.return_value = False

        # create two jobs with resources and one without and add them to the db
        jobs_with_resources = [
            self._make_job([], ['cpc0'], self._requester),
            self._make_job(['lpar0'], ['cpc0'], self._requester)
        ]
        job_no_res = self._make_job([], [], self._requester)
        all_jobs = jobs_with_resources + [job_no_res]
        for job in all_jobs:
            self._session.add(job)
        self._session.commit()

        # initialize looper
        self._looper = looper.Looper()

        # validate behavior
        # queues were initialized
        self._mock_resources_man.reset.assert_called_with()

        # get the list of jobs queued and check if they are the ones we
        # created
        enqueued_job_ids = [
            call[0][0].id for call
            in self._mock_resources_man.enqueue.call_args_list
        ]
        self.assertEqual(enqueued_job_ids,
                         [job.id for job in jobs_with_resources])
    # test_init_waiting_jobs()

    def test_init_dead_process(self):
        """
        Verify if Looper upon initialization correctly finishes a job in
        running state whose process has already died
        """
        # create the running job and add to db
        dead_job = self._make_job([], [], self._requester,
                                  state=SchedulerJob.STATE_RUNNING)
        self._session.add(dead_job)
        self._session.commit()

        # adjust mocks
        self._patch_dead_process_no_comm(0, datetime.utcnow())

        # initialize Looper
        self._looper = looper.Looper()

        # check that queues were initialized
        self._mock_resources_man.reset.assert_called_with()
        # check that nothing was queued since job is dead
        self._mock_resources_man.enqueue.assert_not_called()
        # check if job is correctly marked as completed
        self.assertEqual(dead_job.state, SchedulerJob.STATE_COMPLETED)
    # test_init_dead_process()

    def test_finish_jobs_dead_process(self):
        """
        Exercise scenarios where a job is running and its process died.
        """
        # process died by seeing comm does not exist and result is job failed
        job = self._make_alive_job()
        self._patch_dead_process_no_comm(1, datetime.utcnow())
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_FAILED)

        # process died by seeing comm cannot be read and result is job failed
        job = self._make_alive_job()
        self._patch_dead_process_noread_comm(1, datetime.utcnow())
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_FAILED)

        # process died by seeing comm cannot be read and result job failed
        # with an exception
        job = self._make_alive_job()
        self._patch_dead_process_noread_comm(
            wrapper.RESULT_EXCEPTION, datetime.utcnow())
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_FAILED)

        # process died by seeing cwd points to inexistent directory and result
        # is job completed
        job = self._make_alive_job()
        self._patch_dead_process_no_cwd(0, datetime.utcnow())
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_COMPLETED)

        # process died by seeing cwd is wrong and result has invalid exit code
        job = self._make_alive_job()
        self._patch_dead_process_bad_cwd("not_a_number", datetime.utcnow())
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_FAILED)

        # process died by seeing cwd cannot be read and result has job was
        # canceled
        job = self._make_alive_job()
        self._patch_dead_process_noread_cwd(
            wrapper.RESULT_CANCELED, datetime.utcnow())
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_CANCELED)

        # process died by seeing cwd is wrong and the job was in
        # the process of a normal cleanup
        job = self._make_alive_job()
        self._patch_dead_process_bad_cwd(
            wrapper.RESULT_CANCELED, datetime.utcnow())
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_CANCELED)

        # process died by seeing /proc/comm was not there, the job was
        # canceled and the cleanup routine timed out
        job = self._make_alive_job()
        self._patch_dead_process_no_comm(
            wrapper.RESULT_CANCELED, datetime.utcnow(),
            cleanup_code=wrapper.RESULT_TIMEOUT)
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_CANCELED)

        # process died by seeing /proc/comm was not there, the job was
        # canceled and the cleanup routine failed with an exit code
        job = self._make_alive_job()
        self._patch_dead_process_no_comm(
            wrapper.RESULT_CANCELED, datetime.utcnow(),
            cleanup_code=2)
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_CANCELED)

        # process died by seeing /proc/comm was not there, the job was
        # canceled and the cleanup routine failed with an exception
        job = self._make_alive_job()
        self._patch_dead_process_no_comm(
            wrapper.RESULT_CANCELED, datetime.utcnow(),
            cleanup_code=wrapper.RESULT_EXCEPTION)
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_CANCELED)

        # process died by seeing /proc/comm was not there, the job
        # timed out and the cleanup routine was successful
        job = self._make_alive_job()
        self._patch_dead_process_no_comm(
            wrapper.RESULT_TIMEOUT, datetime.utcnow(),
            cleanup_code=wrapper.RESULT_SUCCESS)
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        self.assertEqual(job.state, job.STATE_CANCELED)
    # test_finish_jobs_dead_process()

    def test_start_jobs_cant_start(self):
        """
        Validate scenario where a job stays in pending state because resources
        are not available.
        """
        request = self._make_request(
            self._make_resources(['lpar0'], []),
            self._requester,
            commit=True)

        # force the job not to be started
        self._mock_resources_man.can_start.return_value = False

        # run one loop to get the request turned to a job
        self._looper.loop()

        # run one more loop to confirm job stays as waiting
        self._looper.loop()

        # validate state
        job = SchedulerJob.query.filter_by(id=request.job_id).one()
        self.assertEqual(job.state, job.STATE_WAITING, job.result)

        # validate behavior
        self._mock_mp.Process.assert_not_called()
        self._mock_mp.Process.return_value.start.assert_not_called()
    # test_start_job_cant_start()

    def test_start_job_process_start_fail(self):
        """
        Verify if job correctly goes to failed state when there are failures
        to start its process.
        """
        request = self._make_request(
            self._make_resources(['lpar0'], []),
            self._requester,
            commit=True)

        self._mock_resources_man.can_start.return_value = True

        # simulate error to spawn process
        self._mock_mp.ProcessError = RuntimeError
        (self._mock_mp.Process.return_value
         .start.side_effect) = self._mock_mp.ProcessError

        # run one loop to go through the routine
        self._looper.loop()

        # validate state
        job = SchedulerJob.query.filter_by(id=request.job_id).one()
        self.assertEqual(job.state, SchedulerJob.STATE_FAILED)
        self.assertEqual(job.result, 'Job failed to start')
        self._mock_mp.Process.return_value.start.assert_called_with()

    # test_start_job_process_start_fail()

    def test_process_request_bad(self):
        """
        Exercises scenarios where a malformed request moves to the failed state
        correctly.
        """
        # invalid action type
        with self.assertRaises(ValueError):
            self._make_request(
                self._make_resources(['lpar0'], []),
                self._requester, action_type="#", commit=True)

        # request with invalid job type
        request = self._make_request(
            self._make_resources(['lpar0'], []),
            self._requester, job_type="#", commit=True)
        self._looper.loop()

        # validate no job created, request state and result
        self.assertEqual(SchedulerJob.query.count(), 0)
        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)
        self.assertEqual(request.result, "Invalid job type '#'")

        # request with malformed parameters which lead to parse error
        # use a mock for the echo machine
        old_echo = self._looper._machines['echo']
        self._looper._machines['echo'] = MagicMock()
        self._looper._machines['echo'].__name__ = MagicMock(
            return_value=old_echo.__name__)

        self._looper._machines['echo'].parse = MagicMock(
            side_effect=RuntimeError)

        request = self._make_request(
            self._make_resources(['lpar0'], []), self._requester, commit=True)

        # run loop and restore original echo machine
        self._looper.loop()
        self._looper._machines['echo'] = old_echo

        # validate no job created, request state and result
        self.assertEqual(SchedulerJob.query.count(), 0)
        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)
        self.assertRegex(
            request.result, "^Parsing of parameters failed with: ")
    # test_process_request_bad()

    def test_cancel_waiting_job(self):
        """
        Submit a request to cancel a job that is still in waiting state.
        """
        # submit a new job request
        request = self._make_request(
            self._make_resources(['lpar0'], []),
            self._requester,
            commit=True)

        # force the job not to be started
        self._mock_resources_man.can_start.return_value = False

        # run one loop to get the request turned to a job
        self._looper.loop()

        # confirm job was created
        job = SchedulerJob.query.filter_by(id=request.job_id).one()
        self.assertEqual(job.state, job.STATE_WAITING, job.result)
        self.assertEqual(request.state, SchedulerRequest.STATE_COMPLETED)

        # create the cancel request
        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)
        request.job_id = job.id
        self._session.add(request)
        self._session.commit()

        # have the request processed
        self._looper.loop()

        self.assertEqual(job.state, SchedulerJob.STATE_CANCELED)
        self.assertEqual(
            job.result, 'Job canceled by user while waiting for execution')

    # test_cancel_waiting_job()

    def test_cancel_running_process(self):
        """
        Submit a request to cancel a job that is running state.
        """
        # create a running job
        job = self._make_alive_job(['lpar0'], ['cpc0'])

        # create the cancel request
        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)
        request.job_id = job.id
        self._session.add(request)
        self._session.commit()

        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)

        # validate request and job states/results
        self.assertEqual(job.state, SchedulerJob.STATE_CLEANINGUP)
        self.assertEqual(job.result, 'Job canceled by user; cleaning up')
        self.assertEqual(request.state, SchedulerRequest.STATE_COMPLETED)
        self.assertEqual(request.result, 'OK')
        # validate that looper sent signal to process
        self._mock_os.kill.assert_called_with(
            job.pid, sentinel.SIGTERM)

        # simulate process died
        self._patch_dead_process_no_comm(
            wrapper.RESULT_CANCELED, datetime.now())

        self._looper.loop()

        self.assertEqual(job.state, SchedulerJob.STATE_CANCELED)
    # test_cancel_running_process()

    def test_cancel_force(self):
        """
        Exercise submitting a cancel request while job is in clean up phase.
        """
        # create a running job
        job = self._make_alive_job(['lpar0'], ['cpc0'])

        # create the cancel request
        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)
        request.job_id = job.id
        self._session.add(request)
        self._session.commit()

        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        # validate request and job states/results
        self.assertEqual(job.state, SchedulerJob.STATE_CLEANINGUP)

        # now submit another request
        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)
        request.job_id = job.id
        self._session.add(request)
        self._session.commit()

        # have looper process the request and force kill process
        self._looper.loop()

        # validate states and results
        self.assertEqual(request.state, SchedulerJob.STATE_COMPLETED)
        self.assertEqual(request.result, 'OK')
        self.assertEqual(job.state, SchedulerJob.STATE_CANCELED)
        self.assertEqual(
            job.result,
            'Job forcefully canceled by user while in cleanup')
        # validate that looper sent signal to process
        self._mock_os.kill.assert_called_with(
            job.pid, sentinel.SIGKILL)

    # test_cancel_force()

    def test_cancel_meantime_dead_process(self):
        """
        Submit a request to cancel a job that died in the meantime.
        """
        # create a running job
        job = self._make_alive_job(['lpar0'], ['cpc0'])

        # create the cancel request
        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)
        request.job_id = job.id
        self._session.add(request)
        self._session.commit()

        # prepare the mocks to simulate that process died in the meantime by
        # making first call return process is alive and second that process
        # died.
        self._mock_open.return_value.__enter__.return_value.read. \
        side_effect = [
            wrapper.WORKER_COMM + "\n", # process alive
            FileNotFoundError # process died
        ]
        # mock for to make process still alive in first pass
        self._mock_os.readlink.return_value = '{}/{}'.format(
            FAKE_JOBS_DIR, job.id)
        # contents of result file
        self._mock_open.return_value.__enter__.return_value.readlines. \
        return_value = (
            [str(0), datetime.utcnow().strftime(wrapper.DATE_FORMAT)])

        # have the request processed
        self._looper.loop()

        job = self._session.query(SchedulerJob).get(job.id)
        # validate states and results
        self.assertEqual(job.state, SchedulerJob.STATE_COMPLETED)
        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)
        self.assertEqual(
            request.result, 'Job has ended while processing request')
    # test_cancel_meantime_dead_process()

    def test_cancel_unknown_process(self):
        """
        Submit a request to cancel a job whose state is unknown
        """
        # create a running job
        job = self._make_alive_job(['lpar0'], ['cpc0'])

        # create the cancel request
        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)
        request.job_id = job.id
        self._session.add(request)
        self._session.commit()

        # prepare the mocks to simulate that process' state is unknown
        self._patch_unknown_process(job)

        # have the request processed
        self._looper.loop()

        # validate states and results
        self.assertEqual(job.state, SchedulerJob.STATE_RUNNING)
        self.assertEqual(request.state, SchedulerRequest.STATE_PENDING)
        self._mock_os.kill.assert_not_called()
    # test_cancel_unknown_process()

    def test_cancel_finished_job(self):
        """
        Submit a request to cancel a job that has already finished
        """
        job = self._make_job(['lpar0'], [], self._requester,
                             state=SchedulerJob.STATE_COMPLETED)
        self._session.add(job)
        self._session.flush()

        # create cancel request
        request = self._make_request(
            self._make_resources([], []),
            self._requester, action_type=SchedulerRequest.ACTION_CANCEL)
        request.job_id = job.id
        self._session.add(request)
        self._session.commit()

        # let looper process request
        self._looper.loop()

        # validate state and result
        self.assertEqual(job.state, SchedulerJob.STATE_COMPLETED)
        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)
        self.assertEqual(
            request.result, 'Cannot cancel job because it already ended')
    # test_cancel_finished_job()

    def test_submit_invalid_resources(self):
        """
        Submit a job that causes the resource manager to fail when validating
        the resources.
        """

        self._mock_resources_man.validate_resources.return_value = False

        request = self._make_request(
            self._make_resources(['lpar0'], []),
            self._requester,
            commit=True)

        self._looper.loop()

        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)

    def test_submit_cant_enqueue(self):
        """
        Submit a job that cannot be enqueued by the resources manager.
        """

        self._mock_resources_man.can_enqueue.return_value = False

        request = self._make_request(
            self._make_resources(['lpar0'], []),
            self._requester,
            commit=True)

        self._looper.loop()

        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)

    def test_submit_bad_attribute(self):
        """
        Submit a job with a state machine without a parse attribute.
        """
        request = self._make_request(
            self._make_resources([], []),
            self._requester,
            commit=True)

        # Patch the returned state machine to None, which will cause
        # None.parse to raise an AttributeError
        echo_patcher = patch.dict(
            looper.MACHINES.classes, {'echo': None})
        echo_patcher.start()
        self.addCleanup(echo_patcher.stop)

        self._looper.loop()

        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)
        self.assertRegex(request.result.lower(), 'parser not found')

    def test_submit_no_permission(self):
        """
        Submit a job with a user without permission to update a system
        """
        requester = User()
        requester.login = 'no_permission@domain.com'
        requester.name = 'User without permission'
        requester.restricted = False
        requester.admin = False
        self._session.add(requester)
        self._session.commit()

        error_msg = (
            'Permission validation for resource lpar0 failed: User has no '
            'UPDATE permission for the specified system')
        try:
            request = self._make_request(
                self._make_resources(['lpar0'], ['cpc0']),
                requester,
                commit=True)
            self._looper.loop()
        finally:
            self._session.delete(request)
            self._session.delete(requester)
            self._session.commit()

        self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)
        self.assertRegex(request.result, error_msg)
    # test_submit_no_permission()

    def test_submit_system_invalid_state(self):
        """
        Submit a job for a system which is not in a state which allows actions
        """
        error_msg = (
            'System {} must be switched to a valid state before '
            'actions can be performed (current state: {})')

        sys_states = [st_obj.name for st_obj in SystemState.query.all()
                      if st_obj.name != 'AVAILABLE']
        sys_obj = System.query.filter_by(name='lpar0').one()
        orig_state = sys_obj.state
        for state in sys_states:
            sys_obj.state = state
            self._session.add(sys_obj)
            self._session.commit()
            try:
                request = self._make_request(
                    self._make_resources(['lpar0'], ['cpc0']),
                    self._requester,
                    commit=True)
                self._looper.loop()
            finally:
                sys_obj.state = orig_state
                self._session.add(sys_obj)
                self._session.delete(request)
                self._session.commit()

            self.assertEqual(request.state, SchedulerRequest.STATE_FAILED)
            self.assertEqual(
                request.result, error_msg.format(sys_obj.name, state))
    # test_submit_invalid_state()

    def test_signal_handler(self):
        """
        Exercise the looper's signal handler.
        """

        # Manually call the handler set for the signal,
        # since ther is no public interface that eventually calls it.
        call = self._mock_signal.signal.call_args

        self.assertIsNotNone(call)

        # signal should have been called with e.g. signal(SIGINT, handler),
        signum = call[0][0]
        handler = call[0][1]

        # According to the doc the stack frame can be None in a signal handler.
        # The looper handler doesn't use the stack frame anyways.
        handler(signum, None)

        # Check if the looper was asked to stop by the signal handler.
        self.assertFalse(self._looper._should_run)

# TestLooper
