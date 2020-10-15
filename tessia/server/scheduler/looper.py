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
from tessia.server.config import CONF
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import SchedulerJob, SchedulerRequest, System
from tessia.server.lib.mediator import MEDIATOR
from tessia.server.lib.perm_manager import PermManager
from tessia.server.scheduler import resources_manager
from tessia.server.scheduler import spawner
from tessia.server.scheduler import wrapper
from tessia.server.state_machines import MACHINES

import logging
import multiprocessing
import signal
import time

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class Looper:
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
        Constructor, sets the fork method for the jobs (workers) and internal
        variables.
        """
        try:
            multiprocessing.set_start_method('forkserver')
        except RuntimeError:
            # start method might have been already used: ensure it was set to
            # the correct mode
            start_method = multiprocessing.get_start_method()
            if start_method != 'forkserver':
                raise RuntimeError(
                    'Multiprocessing mode must be forkserver but was set to '
                    '{}'.format(start_method))

        self._jobs_dir = ''
        self._logger = None
        # manager to validate user permissions on resources allocated to jobs
        self._perman = None
        # resources manager keeps track of resource allocation to determine
        # which job can execute next
        self._resources_man = None
        # dict with state machine parsers keyed by name
        self._machines = None
        # db session
        self._session = None
        # spawn strategy instance
        self._spawner = None
        # mapping of allowed request actions and their methods
        self._request_methods = None

        # signal handler will set flag to False to make looper gracefully stop
        self._should_run = False
    # __init__()

    def _refresh_and_expunge(self, job):
        self._session.refresh(job)
        self._session.expunge(job)
        return job

    def _cancel_active_job(self, request, job):
        """
        Receive a request to stop a job that is still active (running or
        cleanup state) and update the job and request entries accordingly.

        Args:
            request (SchedulerRequest): request's model instance
            job (SchedulerJob): job's model instance with state RUNNING or
                                CLEANINGUP
        """
        # pid ended or does not belong to this job: post process job and
        # mark request as failed since job had already ended
        process_state = self._validate_pid(job)
        if process_state == spawner.PROCESS_DEAD:
            self._post_process_job(job)
            request.state = SchedulerRequest.STATE_FAILED
            request.result = 'Job has ended while processing request'
            self._session.commit()
            return
        # we don't know if the process is still alive or belong to a non tessia
        # job: don't send signal, and keep trying the request until the real
        # state of the process is known
        if process_state == spawner.PROCESS_UNKNOWN:
            self._logger.warning(
                "Job %s process is in unknown state, delaying request "
                "execution", job.id)
            self._session.commit()
            return

        # This is slightly unsafe since between checking the pid and this
        # call the pid could have been recycled.

        # job is running: send a signal to stop state machine
        if job.state == SchedulerJob.STATE_RUNNING:
            # ask state machine process to die gracefully. Later we collect all
            # jobs in clean up state that pid has finished and mark them as
            # failed.
            self._spawner.terminate(job)
            request.state = SchedulerRequest.STATE_COMPLETED
            request.result = 'OK'
            job.state = SchedulerJob.STATE_CLEANINGUP
            job.result = 'Job canceled by user; cleaning up'
            self._session.commit()
        # job is in clean up phase: force kill it
        # we might consider in future to use a FORCECANCEL request type
        # to be more explicit
        else:
            # state must be CLEANINGUP here
            # there is a slight chance that the process does not die after a
            # sigkill, this can happen if it is in the middle of a syscall that
            # never ends (uninterruptible sleep) possibly due to some buggy io
            # operation. The only solution to these cases is a reboot, which is
            # not an option here. Since the process is actually doing nothing
            # and if the syscall completes the signal will be caught and
            # process will die immediately we ignore this scenario and just
            # finish the job.
            self._spawner.terminate(job, force=True)
            request.state = SchedulerRequest.STATE_COMPLETED
            request.result = 'OK'
            job.state = SchedulerJob.STATE_CANCELED
            job.result = 'Job forcefully canceled by user while in cleanup'
            job.end_date = datetime.utcnow()
            self._session.commit()
            # remove job from resources manager
            self._resources_man.active_pop(job)
    # _cancel_active_job()

    def _cancel_job(self, request):
        """
        Cancel the job specified in the request. If the job is running, stop it
        first.

        Args:
            request (SchedulerRequest): request's model instance
        """
        job = self._session.query(SchedulerJob).filter(
            SchedulerJob.id == request.job_id).one_or_none()

        # target job does not exist: request fails. This is very unlikely to
        # occur as the job id is a FK constraint in the request table which
        # means requests with invalid job ids cannot be submitted in the first
        # place
        if job is None:
            request.state = SchedulerRequest.STATE_FAILED
            request.result = 'Specified job not found'
            self._session.commit()
            return

        if job.state in (SchedulerJob.STATE_RUNNING,
                         SchedulerJob.STATE_CLEANINGUP):
            self._cancel_active_job(request, job)

        # job already over: mark request as invalid
        elif job.state in (SchedulerJob.STATE_FAILED,
                           SchedulerJob.STATE_COMPLETED,
                           SchedulerJob.STATE_CANCELED):
            request.state = SchedulerRequest.STATE_FAILED
            request.result = 'Cannot cancel job because it already ended'
            self._session.commit()

        # job is still waiting for execution: just update entry in database
        elif job.state == SchedulerJob.STATE_WAITING:
            request.state = SchedulerRequest.STATE_COMPLETED
            request.result = 'OK'
            job.state = SchedulerJob.STATE_CANCELED
            job.result = 'Job canceled by user while waiting for execution'
            self._session.commit()
            # remove job from resources manager
            self._resources_man.wait_pop(job)

        # job in unknown state: don't know what to do
        else:
            request.state = SchedulerRequest.STATE_FAILED
            request.result = 'Job is in an unknown state'
            self._logger.error('Missing state branch in cancel_job')
            self._session.commit()

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
            if job.resources.get(res_mode, []):
                return True

        return False
    # _has_resources()

    def _signal_handler(self, *_args, **_kwargs):
        """
        Receives a stop signal (SIGTERM, SIGINT) and set the appropriate flag
        to let the looper knows it has to die.
        """
        self._logger.info('Signal caught: waiting for scheduler to exit...')
        self._should_run = False
    # _signal_handler()

    def _submit_job(self, request):
        """
        Process a request and register a new job for execution

        Args:
            request (SchedulerRequest): request's model instance
        """
        # get the appropriate machine parser based on specified job type
        try:
            parser = self._machines[request.job_type].parse
        except KeyError:
            request.state = SchedulerRequest.STATE_FAILED
            request.result = "Invalid job type '{}'".format(request.job_type)
            self._session.commit()
            return
        # should never happen
        except AttributeError:
            request.state = SchedulerRequest.STATE_FAILED
            request.result = (
                'Internal error, parser not found for the job type')
            self._session.commit()
            return

        state_machine = self._machines[request.job_type]

        # recover complete parameters
        # A complete parmfile is checked by the state machine parser
        # before a job is created. so errors can be caught at an earlier stage
        token = 'job_requests:{}:vars'.format(request.id)
        extra_vars = None
        try:
            extra_vars = MEDIATOR.get(token)
        except ValueError as exc:
            self._logger.warning(
                'Wrong value in mediator: key %s, exception %s',
                token, str(exc))

        try:
            complete_parameters = state_machine.recombine(
                request.parameters, extra_vars)
        except Exception as exc:
            request.state = SchedulerRequest.STATE_FAILED
            request.result = (
                'Failed to apply parmfile variables: {}'.format(str(exc)))
            self._session.commit()
            return

        # call the parser to define:
        # 1- resources to be used by this state machine
        # 2- job description
        try:
            parsed_content = parser(complete_parameters)
            resources = parsed_content['resources']
            # validate against schema
            validate(resources, resources_manager.RESOURCES_SCHEMA)
            description = parsed_content['description']
        # whatever error happened we don't want the scheduler to stop so we
        # catch all exceptions and mark the request as failed
        except Exception as exc:  # pylint: disable=broad-except
            request.state = SchedulerRequest.STATE_FAILED
            request.result = (
                'Parsing of parameters failed with: {}'.format(str(exc)))
            self._session.commit()
            return
        if not description:
            description = 'No description'

        if not self._resources_man.validate_resources(resources):
            request.state = SchedulerRequest.STATE_FAILED
            request.result = (
                'Invalid resources. A resource appears twice.')
            self._session.commit()
            return

        # as of today only systems are allocated as resources, if that
        # changes in future the resources list should contain the db
        # objects themselves instead of strings
        for resource in resources['exclusive']:
            # validate that requester can perform updates on the systems
            try:
                system_obj = System.query.filter_by(name=resource).one()
                self._perman.can(
                    'UPDATE', request.requester_rel, system_obj, 'system')
            except Exception as exc:
                request.state = SchedulerRequest.STATE_FAILED
                request.result = (
                    'Permission validation for resource {} failed: {}'
                    .format(resource, str(exc)))
                self._session.commit()
                return
            # state must allow actions too
            if system_obj.state != 'AVAILABLE':
                request.state = SchedulerRequest.STATE_FAILED
                request.result = (
                    'System {} must be switched to a valid state before '
                    'actions can be performed (current state: {})'.format(
                        system_obj.name, system_obj.state))
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

        if new_job.start_date and new_job.timeout == 0:
            request.state = SchedulerRequest.STATE_FAILED
            request.result = (
                'Job with a start date must have a timeout defined.')
            self._session.commit()
            return

        if not self._resources_man.can_enqueue(new_job):
            request.state = SchedulerRequest.STATE_FAILED
            request.result = (
                'Job would conflict with another scheduled job.')
            self._session.commit()
            return

        # save to job table
        self._session.add(new_job)

        # flush so that the job id becomes available
        self._session.flush()

        # update request in table with success
        request.job_id = new_job.id
        request.state = SchedulerRequest.STATE_COMPLETED
        request.result = 'OK'

        self._session.commit()

        # enqueue job

        self._resources_man.enqueue(
            self._refresh_and_expunge(new_job))

    # _submit_job()

    def _init_manager(self):
        """
        Reflect current database state and populate the manager accordingly
        """
        self._resources_man.reset()

        # get the list of jobs still waiting for execution
        waiting_jobs = SchedulerJob.query.filter(
            SchedulerJob.state == SchedulerJob.STATE_WAITING
        ).order_by(
            SchedulerJob.submit_date.asc()
        ).all()

        for job in waiting_jobs:
            if not self._has_resources(job):
                self._logger.warning(
                    'Job %s has no resources associated', job.id)
                continue

            self._resources_man.enqueue(
                self._refresh_and_expunge(job))

        # get the list of active jobs
        active_jobs = SchedulerJob.query.filter(
            SchedulerJob.state.in_(
                [SchedulerJob.STATE_CLEANINGUP, SchedulerJob.STATE_RUNNING])
        ).all()

        for job in active_jobs:
            # validate pid to determine if job is still executing (in a reboot
            # scenario all processes died)
            # job has ended: post process job to update its state
            if self._validate_pid(job) == spawner.PROCESS_DEAD:
                self._post_process_job(job)
                continue

            if self._has_resources(job):
                self._resources_man.set_active(
                    self._refresh_and_expunge(job))

    # _init_manager()

    def _finish_jobs(self):
        """
        Update state of active jobs that have finished
        """
        # get the list of active jobs
        active_jobs = SchedulerJob.query.filter(
            SchedulerJob.state.in_(
                [SchedulerJob.STATE_CLEANINGUP, SchedulerJob.STATE_RUNNING])
        ).all()

        for job in active_jobs:
            # validate pid to determine if job is still executing
            # job still running: nothing to do
            if self._validate_pid(job) != spawner.PROCESS_DEAD:
                continue

            # job has ended: post process job to update its state
            self._post_process_job(job)
            # remove job from queue
            if self._has_resources(job):
                self._resources_man.active_pop(job)

    # _finish_jobs()

    def _post_process_job(self, job):
        """
        Update job state according to the result of its process

        Args:
            job (SchedulerJob): job's model instance
        """
        job_dir = '{}/{}'.format(self._jobs_dir, job.id)
        results_file_name = '{}/.{}'.format(job_dir, job.id)

        try:
            with open(results_file_name, 'r') as results_file:
                results_lines = results_file.readlines()

            results = iter(results_lines)

            ret_code = int(next(results).strip())

            cleanup_code = None

            if len(results_lines) > 2:
                cleanup_code = int(next(results).strip())

            end_date = datetime.strptime(next(results).strip(),
                                         wrapper.DATE_FORMAT)
        except Exception as exc:
            self._logger.warning(
                'Reading of result file for job %s: %s failed',
                job.id, str(exc))
            job.state = SchedulerJob.STATE_FAILED
            job.result = 'Job ended in unknown state'
            job.end_date = datetime.utcnow()
            self._session.commit()
            return

        # success return code: mark job as finished successfully
        if ret_code == wrapper.RESULT_SUCCESS:
            job.state = SchedulerJob.STATE_COMPLETED
            result = 'Job finished successfully.'
        elif ret_code in (wrapper.RESULT_CANCELED, wrapper.RESULT_TIMEOUT):
            job.state = SchedulerJob.STATE_CANCELED

            if ret_code == wrapper.RESULT_CANCELED:
                result = 'Job canceled.'
            else:
                assert ret_code == wrapper.RESULT_TIMEOUT
                result = 'Job timed out.'

            if cleanup_code is None:
                # Job was already cleaning up before being interrupted.
                result += " Normal cleanup was interrupted."
            elif cleanup_code == wrapper.RESULT_TIMEOUT:
                result += " Cleanup timed out."
            elif cleanup_code == wrapper.RESULT_EXCEPTION:
                result += " Cleanup failed abnormally."
            elif cleanup_code == wrapper.RESULT_SUCCESS:
                result += " Cleanup completed."
            else:
                result += " Cleanup ended with error exit code."
        elif ret_code == wrapper.RESULT_EXCEPTION:
            job.state = SchedulerJob.STATE_FAILED
            result = 'Job failed abnormally.'
        else:
            job.state = SchedulerJob.STATE_FAILED
            result = 'Job ended with error exit code'

        job.result = result
        job.end_date = end_date
        self._session.commit()
    # _post_process_job()

    def _start_jobs(self):
        """
        Process waiting jobs and try to start them
        """
        self._logger.info('Trying to start waiting jobs')

        # get the list of jobs still waiting for execution
        pending_jobs = SchedulerJob.query.filter(
            SchedulerJob.state == SchedulerJob.STATE_WAITING
        ).all()

        for job in pending_jobs:
            if not self._resources_man.can_start(job):
                continue

            self._logger.info('Starting job %s', job.id)

            # recover complete parmfile
            request = SchedulerRequest.query.filter(
                SchedulerRequest.job_id == job.id
            ).first()
            token = 'job_requests:{}:vars'.format(request.id)
            extra_vars = None
            try:
                extra_vars = MEDIATOR.get(token)
            except ValueError as exc:
                self._logger.warning(
                    'Unexpected value in mediator: key %s, exception %s',
                    token, str(exc))

            try:
                complete_parameters = self._machines[job.job_type].recombine(
                    job.parameters, extra_vars)
            except Exception as exc:
                job.state = SchedulerJob.STATE_FAILED
                job.result = (
                    'Failed to apply parmfile variables: {}'.format(str(exc)))
                current_date = datetime.utcnow()
                job.start_date = current_date
                job.end_date = current_date
                self._session.commit()
                # remove from queue since it won't be scheduled anymore
                self._resources_man.wait_pop(job)
                continue

            # start job's state machine
            job_dir = '{}/{}'.format(self._jobs_dir, job.id)
            try:
                process_pid = self._spawner.spawn(
                    job_args={
                        'job_dir': job_dir,
                        'job_type': job.job_type,
                        'job_parameters': complete_parameters,
                        'timeout': job.timeout
                    }
                )

            except spawner.SpawnerError as exc:
                self._logger.warning(
                    'Failed to start job %s: %s', job.id, str(exc))
                job.state = SchedulerJob.STATE_FAILED
                job.result = 'Job failed to start'
                current_date = datetime.utcnow()
                job.start_date = current_date
                job.end_date = current_date
                self._session.commit()
                # remove from queue since it won't be scheduled anymore
                self._resources_man.wait_pop(job)
                continue

            # update job in database to reflect new state
            job.pid = process_pid
            job.state = SchedulerJob.STATE_RUNNING
            job.result = 'Job is running'
            job.start_date = datetime.utcnow()
            self._session.commit()

            self._refresh_and_expunge(job)
            self._resources_man.wait_pop(job)
            self._resources_man.set_active(job)

    # _start_jobs()

    def _validate_pid(self, job):
        """
        Verify the state of the job's process (whether it still belongs to a
        tessia job or died).

        Args:
            job (SchedulerJob): job instance

        Returns:
            int: one of the PROCESS_* constants
        """
        self._logger.debug('Checking pid %s of job %s', job.pid, job.id)

        return self._spawner.validate(job)

    # _validate_pid()

    def _process_pending_requests(self):
        """
        Collect the pending requests from the table and process them.
        """
        pending_requests = (
            SchedulerRequest.query.filter(
                SchedulerRequest.state == SchedulerRequest.STATE_PENDING)
            .order_by(
                SchedulerRequest.submit_date.asc()
            )).all()

        for request in pending_requests:
            try:
                method = self._request_methods[request.action_type]
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
    # _process_pending_requests()

    def initialize(self):
        """
        Delayed initialization for internal structures
        """
        try:
            self._jobs_dir = CONF.get_config().get('scheduler')['jobs_dir']
        except (TypeError, KeyError):
            raise RuntimeError('No scheduler job directory configured')

        self._logger = logging.getLogger(__name__)
        # manager to validate user permissions on resources allocated to jobs
        self._perman = PermManager()
        # resources manager keeps track of resource allocation to determine
        # which job can execute next
        self._resources_man = resources_manager.ResourcesManager()
        # dict with state machine parsers keyed by name
        self._machines = MACHINES.classes
        # db session
        self._session = MANAGER.session
        # spawn strategy
        self._spawner = spawner.ContainerSpawner()
        # mapping of allowed request actions and their methods
        self._request_methods = {
            SchedulerRequest.ACTION_CANCEL: self._cancel_job,
            SchedulerRequest.ACTION_SUBMIT: self._submit_job,
        }

        # handle the signals for graceful termination
        signal.signal(signal.SIGHUP, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        # signal handler will set flag to False to make looper gracefully stop
        self._should_run = True

        # init resources manager with information from jobs
        self._init_manager()
    # initialize()

    def loop(self, sleep_time=0.5):
        """
        Starts the main scheduling loop.

        Args:
            sleep_time (int): interval to wait between each loop
        """
        try:
            while self._should_run:
                # finish any active jobs
                self._finish_jobs()

                self._process_pending_requests()

                # try to schedule jobs in pending state
                self._start_jobs()

                self._logger.debug(self._resources_man)
                # TODO: scheduler is running too fast
                time.sleep(sleep_time)

        except:
            self._session.rollback()
            self._logger.error(
                "Caught exception in scheduler, exiting...", exc_info=True)
            raise

    # loop()
# Looper
