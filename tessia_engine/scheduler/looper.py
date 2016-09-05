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
from tessia_engine.db.connection import SESSION
from tessia_engine.db.models import SchedulerRequest
from tessia_engine.db.models import SchedulerJob
from tessia_engine.scheduler.resources_manager import ResourcesManager
from tessia_engine.scheduler import wrapper
from tessia_engine import state_machines
from sqlalchemy.sql import func

import logging
import os
import signal

#
# CONSTANTS AND DEFINITIONS
#
# TODO: specific string for type of list element
# i.e. {'exclusive': ['system.guest01', 'volume.disk01'], 'shared':
# ['system.lpar01']}
RESOURCES_SCHEMA = {
    'type': 'object',
    'properties': {
        'exclusive': {'type': 'list'},
        'shared': {'type': 'list'},
    }
}

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
        try:
            self._jobs_dir = CONF.get_config()['scheduler']['jobs_dir']
        except KeyError:
            raise RuntimeError('No scheduler job directory configured')

        self._logger = logging.getLogger(__name__)
        # resources manager keeps track of resource allocation to determine
        # which job can execute next
        self._resources_man = ResourcesManager()
        # dict with state machine parsers keyed by name
        self._machines = state_machines.MACHINES
    # __init__()

    def _cancel_job(self, request):
        """
        Cancel the job specified in the request. If the job is running, stop it
        first.
        """
        job = SchedulerJob.query.filter(SchedulerJob.id==request.job_id)
        try:
            job = job[0]
        except IndexError:
            request.state = SchedulerRequest.STATE_FAILED
            request.result = 'Specified job not found'
            SESSION.commit()
            return

        # job is running: stop state machine first
        if job.state == SchedulerJob.STATE_RUNNING:
            ret = self._validate_pid(job)
            # pid ended or does not belong to this job: post process job and
            # mark request as failed since job already ended
            if ret != 'OK':
                self._post_process_job(job)
                request.state = SchedulerRequest.STATE_FAILED
                request.result = 'Job has ended while processing request'
                SESSION.commit()
                return

            # ask state machine process to die gracefully. Later we collect all
            # jobs in clean up state that pid has finished and mark them as
            # failed.
            os.kill(job.pid, signal.SIGTERM)
            request.state = SchedulerRequest.STATE_COMPLETED
            request.result = 'OK'
            job.state = SchedulerJob.STATE_CLEANINGUP
            job.result = 'Job canceled by user; cleaning up'
            SESSION.commit()

        # job already over: mark request as invalid
        elif job.state in (SchedulerJob.STATE_FAILED,
                           SchedulerJob.STATE_COMPLETED):
            request.state = SchedulerRequest.STATE_FAILED
            request.result = 'Cannot cancel job because it already ended'
            SESSION.commit()

        # job is in clean up phase: force kill it
        # we might consider in future to use a FORCECANCEL request type
        # to be more explicit
        elif job.state == SchedulerJob.STATE_CLEANINGUP:
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
            job.end_date = func.now()
            SESSION.commit()
            # remove job from resources manager
            self._resources_man.active_pop(job)

        # job is still waiting for execution: just update entry in database
        elif job.state == SchedulerJob.STATE_WAITING:
            request.state = SchedulerRequest.STATE_COMPLETED
            request.result = 'OK'
            job.state = SchedulerJob.STATE_CANCELED
            job.result = 'Job canceled by user while waiting for execution'
            SESSION.commit()
            # remove job from resources manager
            self._resources_man.wait_pop(job)

    # _cancel_job()

    def _submit_job(self, request):
        """
        Process a request and register a new job for execution
        """
        # get the appropriate machine parser based on specified job type
        try:
            parser = self._machines[request.job_type].parse
        except KeyError:
            request.status = 'FAILED'
            request.result = "Invalid job type '{}'".format(request.job_type)
            SESSION.commit()
            return
        # should never happen
        except AttributeError:
            request.status = 'FAILED'
            request.result = (
                'Internal error, parser not found for the job type')
            SESSION.commit()
            return

        # call the parser to define:
        # 1- resources to be used by this state machine
        # 2- job description
        try:
            parsed_content = parser(request.parameters)
            resources = parsed_content['resources']
            # validate against schema
            validate(resources, RESOURCES_SCHEMA)
            description = parsed_content['description']
        # whatever error happened we don't want the scheduler to stop so we
        # catch all exceptions and mark the request as failed
        # pylint: disable=broad-except
        except Exception as exc:
            request.status = 'FAILED'
            request.result = (
                'Parsing of parameters failed with: {}'.format(str(exc)))
            SESSION.commit()
            return

        # create job object
        new_job = SchedulerJob(
            id=request.job_id,
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
            result='Waiting for resources'
        )

        # enqueue job
        self._resources_man.enqueue(new_job)

        # save to job table
        SESSION.add(new_job)

        # update request in table with success
        request.job_id = new_job.id
        request.status = 'COMPLETE'
        request.result = 'OK'

        # new job and processed request are an atomic operation
        SESSION.commit()

    # _submit_job()

    def _init_manager(self):
        """
        Reflect current database state and populate the manager accordingly
        """
        self._resources_man.reset()

        # get the list of jobs still waiting for execution
        waiting_jobs = SchedulerJob.query.filter_by(
            SchedulerJob.state == SchedulerJob.STATE_WAITING
        ).order_by(
            SchedulerJob.submit_date.asc()
        ).all()

        for job in waiting_jobs:
            if job.resources is None:
                self._logger.warning(
                    'Job %s has no resources associated', job.id)
                continue

            self._resources_man.enqueue(job)

        # get the list of active jobs
        active_jobs = SchedulerJob.query.filter(
            SchedulerJob.state.in_(
                [SchedulerJob.STATE_CLEANINGUP, SchedulerJob.STATE_RUNNING])
        ).all()
        for job in active_jobs:
            if job.resources is None:
                self._logger.warning(
                    'Active Job %s has no resources associated', job.id)
                continue

            # validate pid to determine if job is still executing (in a reboot
            # scenario all processes died)
            ret = self._validate_pid(job)
            # job has ended: post process job to update its state
            if ret != 'OK':
                self._post_process_job(job)
                continue

            self._resources_man.enqueue(job)
    # _init_manager()

    def _finish_jobs(self):
        """
        Update state of all jobs finished
        """
        # get the list of active jobs
        active_jobs = SchedulerJob.query.filter(
            SchedulerJob.state.in_(
                [SchedulerJob.STATE_CLEANINGUP, SchedulerJob.STATE_RUNNING])
        ).all()
        for job in active_jobs:
            if job.resources is None:
                self._logger.warning(
                    'Active Job %s has no resources associated', job.id)
                continue

            # validate pid to determine if job is still executing
            ret = self._validate_pid(job)
            # job still running: nothing to do
            if ret == 'OK':
                continue

            # job has ended: post process job to update its state
            self._post_process_job(job)
            # remove job from queue
            self._resources_man.active_pop(job)

    # _finish_jobs()

    def _post_process_job(self, job):
        """
        Update job entry according to the result of its process
        """
        job_dir = '{}/{}'.format(self._jobs_dir, job.id)
        try:
            results = open('{}/.{}'.format(job_dir, job.id), 'r').readlines()
            ret_code = int(results[0].strip())
            end_date = datetime.strptime(results[1].strip(),
                                         wrapper.DATE_FORMAT)
        except Exception as exc:
            self._logger.warning('Reading of result file for job %s: %s',
                                 job.id, str(exc))
            job.state = SchedulerJob.STATE_FAILED
            job.result = 'Job ended in unknown state'
            job.end_date = func.now()
            SESSION.commit()
            return

        # 0 return code: mark job as finished successfully
        if ret_code == 0:
            job.state = SchedulerJob.STATE_COMPLETED
            job.result = 'Job finished successfully'
        # job timed out: mark as failed and report cause
        elif ret_code == -1:
            job.state = SchedulerJob.STATE_FAILED
            job.result = 'Job aborted due to timeout'
        # user requested job to stop: mark job as canceled
        elif job.state == SchedulerJob.STATE_CLEANINGUP:
            job.state = SchedulerJob.STATE_CANCELED
            job.result = 'Job was canceled by user'
        # job ended in error: mark as failed
        else:
            job.state = SchedulerJob.STATE_FAILED
            job.result = 'Job ended with error exit code'

        job.end_date = end_date
        SESSION.commit()
    # _post_process_job()

    def _start_jobs(self):
        """
        Loop on waiting jobs and try to start them
        """
        self._logger.info('Trying to start waiting jobs')

        # get the list of jobs still waiting for execution
        pending_jobs = SchedulerJob.query.filter_by(
            SchedulerJob.state == SchedulerJob.STATE_WAITING
        ).all()
        for job in pending_jobs:
            if not self._resources_man.can_start(job):
                continue

            self._logger.info('Starting job %s', job.id)

            # start job's state machine
            job_dir = '{}/{}'.format(self._jobs_dir, job.id)
            cur_time = datetime.now()
            try:
                wrapped_machine = wrapper.MachineWrapper(
                    job_dir, job.job_type, job.parameters)
                pid = wrapped_machine.start()
            except (IOError, PermissionError, OSError) as exc:
                self._logger.warning(
                    'Failed to start job %s: %s', job.id, str(exc))
                continue

            # update job in database to reflect new state
            job.pid = pid
            job.state = SchedulerJob.STATE_RUNNING
            job.result = 'Job is running'
            job.start_date = func.now()
            SESSION.commit()

    # _start_jobs()

    def _validate_pid(self, job):
        """
        Verify if the pid corresponds to a state machine process and return an
        error message if not.
        """
        # read the modified command line value from process
        try:
            proc_cmdline = open('/proc/{}/comm'.format(job.pid), 'r').read()
        except FileNotFoundError:
            self._logger.warning("Job '%s' has inexistent pid '%s'", job.id,
                                 job.pid)
            return 'Job has inexistent pid'

        # value do not match: process is something else
        if not proc_cmdline.startswith('tessia-'):
            self._logger.warning("Pid '%s' of job '%s' is not a state machine",
                                 job.pid, job.id)
            return "Job's pid is not a valid process"

        # verify through the current working directory if the process belongs
        # to the correct job
        proc_cwd_file = '/proc/{}/cwd'.format(job.pid)
        cwd_path = os.path.join(
            os.path.dirname(proc_cwd_file), os.readlink(proc_cwd_file))
        proc_job = os.path.basename(cwd_path)
        # process is a state machine but belongs to a different job: report
        # error
        if proc_job != str(job.pid):
            self._logger.warning("Pid '%s' of job '%s' has cwd of job '%s'",
                                 job.pid, job.id, proc_job)
            return "Job's pid points to a different job"

        return 'OK'
    # _validate_job()

    def start(self):
        """
        Starts the main scheduling loop.
        """
        # init resources manager with information from jobs
        self._init_manager()

        request_methods = {
            SchedulerRequest.ACTION_CANCEL: self._cancel_job,
            SchedulerRequest.ACTION_CREATE: self._submit_job,
        }
        while True:
            # process all pending requests
            pending_requests = SchedulerRequest.query.filter_by(
                SchedulerRequest.state == SchedulerRequest.STATE_PENDING
            ).order_by(
                SchedulerRequest.submit_date.asc()
            ).all()
            for request in pending_requests:
                try:
                    method = request_methods[request.action_type]
                # request is invalid: mark it as failed
                except KeyError:
                    self._logger.warning(
                        "Invalid operation '%s', ignoring", request.action_type)
                    request.state = SchedulerRequest.STATE_FAILED
                    request.result = 'Invalid operation specified'
                    SESSION.commit()
                # valid request: execute the specified action
                else:
                    method(request)

            # finish any active jobs
            self._finish_jobs()

            # try to schedule jobs in pending state
            self._start_jobs()
    # start()

# Looper
