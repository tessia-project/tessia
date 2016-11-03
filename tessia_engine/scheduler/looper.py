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
from datetime import datetime
from jsonschema import validate
from tessia_engine.config import CONF
from tessia_engine.db.connection import MANAGER
from tessia_engine.db.models import SchedulerRequest
from tessia_engine.db.models import SchedulerJob
from tessia_engine.scheduler import resources_manager
from tessia_engine.scheduler import spawner
from tessia_engine.scheduler import wrapper
from tessia_engine import state_machines

import logging
import multiprocessing
import os
import signal
import time

#
# CONSTANTS AND DEFINITIONS
#
PROCESS_RUNNING = 0
PROCESS_DEAD = 1
PROCESS_UNKNOWN = 2

#
# CODE
#
class Looper(object):
    """
    The scheduling algorithm works in the following way:
    - create a job queue for each resource in a hash table (for constant time
      access)
    - jobs get added to the queue based on start date and priority. Jobs with
      start date stay always in front, ordered by start date. If no start date
      is specified, order by priority.
    - at all times, the first entry in the queue is the next job to be
      started. To determine if a given job can be started it has to be the
      first entry in each of its resources queues. For jobs with start date
      the scheduler first checks if the current date matches, otherwise it
      looks for the first job in the queue which has no date specified.
    """
    def __init__(self):
        """
        Constructor
        """

        # Ensure that the startup script properly set up the
        # start method in the main module.
        if multiprocessing.get_start_method() != 'forkserver':
            raise RuntimeError(
                'Multiprocessing start method was not properly setup')

        try:
            self._jobs_dir = CONF.get_config()['scheduler']['jobs_dir']
        except KeyError:
            raise RuntimeError('No scheduler job directory configured')

        self._logger = logging.getLogger(__name__)
        # resources manager keeps track of resource allocation to determine
        # which job can execute next
        self._resources_man = resources_manager.ResourcesManager()
        # dict with state machine parsers keyed by name
        self._machines = state_machines.MACHINES

        self._cwd = os.getcwd()

        self._session = MANAGER.session

        self.should_stop = lambda: False
    # __init__()

    def _check_process_and_kill(self, request, job):
        # pid ended or does not belong to this job: post process job and
        # mark request as failed since job already ended
        process_state = self._validate_pid(job)
        if process_state == PROCESS_DEAD:
            self._post_process_job(job)
            request.state = SchedulerRequest.STATE_FAILED
            request.result = 'Job has ended while processing request'
            self._session.commit()
            return
        elif process_state == PROCESS_UNKNOWN:
            # we don't know if the process is still alive, and the pid
            # could belong to a process not related to a tessia job
            # so we don't send signal, and keep trying the request until
            # the real state of the process is known
            self._logger.info(
                "Job in process in unknown state, waiting to execute request")
            self._session.commit()
            return

        # This is slightly unsafe since between checking the pid and this
        # call the pid could have been recycled.

        # job is running: stop state machine first
        if job.state == SchedulerJob.STATE_RUNNING:
            # ask state machine process to die gracefully. Later we collect all
            # jobs in clean up state that pid has finished and mark them as
            # failed.
            os.kill(job.pid, signal.SIGTERM)
            request.state = SchedulerRequest.STATE_COMPLETED
            request.result = 'OK'
            job.state = SchedulerJob.STATE_CLEANINGUP
            job.result = 'Job canceled by user; cleaning up'
        # job is in clean up phase: force kill it
        # we might consider in future to use a FORCECANCEL request type
        # to be more explicit
        else:
            assert job.state == SchedulerJob.STATE_CLEANINGUP
            # there is a slight chance that the process does not die after a
            # sigkill, this can happen if it is in the middle of a syscall that
            # never ends (uninterruptible sleep) possibly due to some buggy io
            # operation. The only solution to these cases is a reboot, which is
            # not an option here. Since the process is actually doing nothing
            # and if the syscall completes the signal will be caught and
            # process will die immediately we ignore this scenario and just
            # finish the job.
            os.kill(job.pid, signal.SIGKILL)
            request.state = SchedulerRequest.STATE_COMPLETED
            request.result = 'OK'
            job.state = SchedulerJob.STATE_CANCELED
            job.result = 'Job forcefully canceled by user while in cleanup'
            job.end_date = datetime.utcnow()
            # remove job from resources manager
            self._resources_man.active_pop(job)

        self._session.commit()

    def _cancel_job(self, request):
        """
        Cancel the job specified in the request. If the job is running, stop it
        first.
        """
        job = self._session.query(SchedulerJob).filter(
            SchedulerJob.id == request.job_id).one_or_none()

        if job is None:
            request.state = SchedulerRequest.STATE_FAILED
            request.result = 'Specified job not found'
            self._session.commit()
            return

        if job.state in (SchedulerJob.STATE_RUNNING,
                         SchedulerJob.STATE_CLEANINGUP):
            self._check_process_and_kill(request, job)
        # job already over: mark request as invalid
        elif job.state in (SchedulerJob.STATE_FAILED,
                           SchedulerJob.STATE_COMPLETED):
            request.state = SchedulerRequest.STATE_FAILED
            request.result = 'Cannot cancel job because it already ended'
            self._session.commit()
        # job is still waiting for execution: just update entry in database
        else:
            assert job.state == SchedulerJob.STATE_WAITING
            request.state = SchedulerRequest.STATE_COMPLETED
            request.result = 'OK'
            job.state = SchedulerJob.STATE_CANCELED
            job.result = 'Job canceled by user while waiting for execution'
            self._session.commit()
            # remove job from resources manager
            self._resources_man.wait_pop(job)

    # _cancel_job()

    @staticmethod
    def _has_resources(job):
        """
        Helper function to easily verify if a job has resources associated

        Args:
            job (SchedulerJob): model instance

        Returns:
            bool: True if job has resources, False otherwise

        Raises:
            None
        """
        for res_mode in resources_manager.MODES:
            if len(job.resources.get(res_mode, [])) > 0:
                return True

        return False
    # _has_resources()

    def _submit_job(self, request):
        """
        Process a request and register a new job for execution
        """
        # get the appropriate machine parser based on specified job type
        try:
            parser = self._machines[request.job_type].parse
        except KeyError:
            request.state = SchedulerRequest.STATE_FAILED
            request.result = "Invalid job type '{}'".format(request.job_type)
            self._session.commit()
            return

        # call the parser to define:
        # 1- resources to be used by this state machine
        # 2- job description
        try:
            parsed_content = parser(request.parameters)
            resources = parsed_content['resources']
            # validate against schema
            validate(resources, resources_manager.RESOURCES_SCHEMA)
            description = parsed_content['description']
        # whatever error happened we don't want the scheduler to stop so we
        # catch all exceptions and mark the request as failed
        except Exception as exc: # pylint: disable=broad-except
            request.state = SchedulerRequest.STATE_FAILED
            request.result = (
                'Parsing of parameters failed with: {}'.format(str(exc)))
            self._session.commit()
            return

        # create job object
        new_job = SchedulerJob(
            requester_id=request.requester_id,
            priority=request.priority,
            time_slot=request.time_slot,
            submit_date=request.submit_date,
            start_date=request.start_date,
            state=SchedulerJob.STATE_WAITING,
            job_type=request.job_type,
            resources=resources,
            description=description,
            parameters=request.parameters,
            result='Waiting for resources',
            timeout=request.timeout
        )

        # enqueue job
        self._resources_man.enqueue(new_job)

        # save to job table
        self._session.add(new_job)

        # flush so that the job id becomes available
        self._session.flush()

        # update request in table with success
        request.job_id = new_job.id
        request.state = SchedulerRequest.STATE_COMPLETED
        request.result = 'OK'

        self._session.commit()

    # _submit_job()

    def _init_manager(self):
        """
        Reflect current database state and populate the manager accordingly
        """
        self._resources_man.reset()

        # get the list of jobs still waiting for execution
        waiting_jobs = self._session.query(SchedulerJob).filter(
            SchedulerJob.state == SchedulerJob.STATE_WAITING
        ).order_by(
            SchedulerJob.submit_date.asc()
        ).all()

        for job in waiting_jobs:
            if not self._has_resources(job):
                self._logger.warning(
                    'Job %s has no resources associated', job.id)
                continue

            self._resources_man.enqueue(job)

        # get the list of active jobs
        active_jobs = self._session.query(SchedulerJob).filter(
            SchedulerJob.state.in_(
                [SchedulerJob.STATE_CLEANINGUP, SchedulerJob.STATE_RUNNING])
        ).all()

        for job in active_jobs:
            # validate pid to determine if job is still executing (in a reboot
            # scenario all processes died)
            # job has ended: post process job to update its state
            if self._validate_pid(job) == PROCESS_DEAD:
                self._post_process_job(job)
                continue

            if self._has_resources(job):
                self._resources_man.enqueue(job)

        self._session.commit()
    # _init_manager()

    def _finish_jobs(self):
        """
        Update state of all jobs finished
        """
        # get the list of active jobs
        active_jobs = self._session.query(SchedulerJob).filter(
            SchedulerJob.state.in_(
                [SchedulerJob.STATE_CLEANINGUP, SchedulerJob.STATE_RUNNING])
        ).all()

        for job in active_jobs:
            # validate pid to determine if job is still executing
            # job still running: nothing to do
            if self._validate_pid(job) != PROCESS_DEAD:
                continue

            # job has ended: post process job to update its state
            self._post_process_job(job)
            # remove job from queue
            if self._has_resources(job):
                self._resources_man.active_pop(job)

        self._session.commit()

    # _finish_jobs()

    def _post_process_job(self, job):
        """
        Update job entry according to the result of its process
        """
        job_dir = '{}/{}'.format(self._jobs_dir, job.id)
        results_file_name = '{}/.{}'.format(job_dir, job.id)

        try:
            with open(results_file_name, 'r') as results_file:
                results = results_file.readlines()
                ret_code = int(results[0].strip())
                end_date = datetime.strptime(results[1].strip(),
                                             wrapper.DATE_FORMAT)
        except Exception as exc:
            self._logger.warning('Reading of result file for job %s: %s',
                                 job.id, str(exc))
            job.state = SchedulerJob.STATE_FAILED
            job.result = 'Job ended in unknown state'
            job.end_date = datetime.utcnow()
            self._session.commit()
            return

        # 0 return code: mark job as finished successfully
        if ret_code == 0:
            job.state = SchedulerJob.STATE_COMPLETED
            job.result = 'Job finished successfully'
        elif ret_code == wrapper.RESULT_CANCELED:
            job.state = SchedulerJob.STATE_CANCELED
            job.result = 'Job canceled'
        elif ret_code == wrapper.RESULT_CANCELED_TIMEOUT:
            job.state = SchedulerJob.STATE_CANCELED
            job.result = 'Job canceled and cleanup timed out'
        else:
            job.state = SchedulerJob.STATE_FAILED
            job.result = 'Job ended with error exit code'

        job.end_date = end_date
        self._session.commit()

    # _post_process_job()

    def _start_jobs(self):
        """
        Loop on waiting jobs and try to start them
        """
        self._logger.info('Trying to start waiting jobs')

        # get the list of jobs still waiting for execution
        pending_jobs = self._session.query(SchedulerJob).filter(
            SchedulerJob.state == SchedulerJob.STATE_WAITING
        ).all()

        for job in pending_jobs:
            if not self._resources_man.can_start(job):
                continue

            self._logger.info('Starting job %s', job.id)

            # start job's state machine
            job_dir = '{}/{}'.format(self._jobs_dir, job.id)
            try:
                process = multiprocessing.Process(
                    target=spawner.spawn,
                    args=(
                        job_dir, job.job_type, job.parameters))

                process.start()

            except multiprocessing.ProcessError as exc:
                self._logger.warning(
                    'Failed to start job %s: %s', job.id, str(exc))
                continue

            # update job in database to reflect new state
            job.pid = process.pid
            job.state = SchedulerJob.STATE_RUNNING
            job.result = 'Job is running'
            job.start_date = datetime.utcnow()

            self._resources_man.enqueue(job)

            self._session.commit()

            self._resources_man.wait_pop(job)

        self._session.commit()

    # _start_jobs()

    def _validate_pid(self, job):
        # True is running, False is dead

        self._logger.info('Checking pid of job %s', job.id)

        inexistent_pid_msg = 'Job {} has inexistent pid {}'.format(
            job.id, job.pid)

        try:
            # the read comm will include a newline, so strip it
            with open('/proc/{}/comm'.format(job.pid), 'r') as comm_file:
                proc_comm = comm_file.read().strip()

        # permission error in case the pid is recycled and
        # the file is created with unaccessible permissions
        except (FileNotFoundError, PermissionError):
            self._logger.warning(inexistent_pid_msg)
            return PROCESS_DEAD

        self._logger.info('Process comm is %s', proc_comm)

        proc_cwd_file = '/proc/{}/cwd'.format(job.pid)

        try:
            proc_cwd = os.readlink(proc_cwd_file)
        except (FileNotFoundError, PermissionError):
            self._logger.warning(inexistent_pid_msg)
            return PROCESS_DEAD

        self._logger.info('Process cwd is %s', proc_cwd)

        comm_ok = False

        if proc_comm == wrapper.WORKER_COMM:
            comm_ok = True

        cwd_ok = False

        if os.path.basename(proc_cwd) == str(job.id):
            cwd_ok = True

        # Process had time to change its comm and cwd, and they are
        # both correct, process seems to be running
        if comm_ok and cwd_ok:
            self._logger.info('Process is running with cwd and comm correct.')
            return PROCESS_RUNNING

        # cwd was set correctly but not the comm, this can't happen
        # since the worker processes set the comm first.
        if not comm_ok and cwd_ok:
            self._logger.warning(
                'Process set cwd before comm, something is wrong!')

        # At this point we don't know if the process is correct, it might not
        # had had time to change it's comm, and then its cwd

        # The starting cwd of the worker process is the same as the looper's
        # cwd, so if the cwd is neither the final worker process cwd nor the
        # looper cwd, it must be another process
        if not cwd_ok and proc_cwd != self._cwd:
            self._logger.info(
                'Process did not start with looper cwd, assuming dead')
            return PROCESS_DEAD

        # In any other case we can't be sure, so assume the process is running,
        # and it will eventually either die or change its cwd/comm
        self._logger.info(
            'Process has not yet set comm and cwd: unknown state.')
        return PROCESS_UNKNOWN

    def _process_pending_requests(self):
        request_methods = {
            SchedulerRequest.ACTION_CANCEL: self._cancel_job,
            SchedulerRequest.ACTION_SUBMIT: self._submit_job,
        }

        pending_requests = (
            self._session.query(SchedulerRequest).filter(
                SchedulerRequest.state == SchedulerRequest.STATE_PENDING)
            .order_by(
                SchedulerRequest.submit_date.asc()
            )).all()

        for request in pending_requests:
            try:
                method = request_methods[request.action_type]
            # request is invalid: mark it as failed
            except KeyError:
                self._logger.warning(
                    "Invalid operation '%s', ignoring", request.action_type)
                request.state = SchedulerRequest.STATE_FAILED
                request.result = 'Invalid operation specified'
                self._session.commit()
            # valid request: execute the specified action
            else:
                method(request)

        self._session.commit()

    def start(self, sleep_time=0.1):
        """
        Starts the main scheduling loop.
        """
        with open('/proc/self/comm', 'w') as comm_file:
            # comm file gets truncated to 15-bytes + null terminator
            comm_file.write('tessia-looper')

        try:
            # init resources manager with information from jobs
            self._init_manager()

            while not self.should_stop():
                # TODO: scheduler is running too fast
                time.sleep(sleep_time)

                self._process_pending_requests()

                self._finish_jobs()

                self._start_jobs()

                self._logger.info(self._resources_man)

        except:
            self._session.rollback()
            self._logger.warning(
                "Caught exception in scheduler, exiting...", exc_info=True)
            raise

    # start()

# Looper
