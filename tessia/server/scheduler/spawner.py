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
Spawner used to start the workers (jobs' processes)
"""

#
# IMPORTS
#
from abc import abstractmethod
from tessia.server.scheduler import wrapper

import logging
import multiprocessing
import os
import signal

#
# CONSTANTS AND DEFINITIONS
#
PROCESS_RUNNING = 0
PROCESS_DEAD = 1
PROCESS_UNKNOWN = 2

#
# CODE
#


class SpawnerBase():
    """
    Class to encapsulate spawning strategies
    """

    def __init__(self):
        """
        Constructor, creates logger instance and initialize connection
        to docker daemon.
        """
        self._logger = logging.getLogger(__name__)
    # __init__()

    @abstractmethod
    def spawn(self, job_args, environment):
        """
        Spawn an executor instance

        Args:
            job_args (dict): job arguments
            environment (dict): environment setting
        """
        raise NotImplementedError
    # spawn()

    @abstractmethod
    def terminate(self, job, force):
        """
        Terminate a running job.

        Args:
            job (SchedulerJob): job instance
            force (bool): use force
        """
        raise NotImplementedError
    # terminate()

    @abstractmethod
    def validate(self, job):
        """
        Verify the state of the job's process (whether it still belongs to a
        tessia job or died).

        Args:
            job (SchedulerJob): job instance

        Returns:
            int: one of the PROCESS_* constants
        """
        raise NotImplementedError
    # validate()
# SpawnerBase

class SpawnerError(Exception):
    """
    Class incapsulating spawn error
    """
# SpawnerError

class ForkSpawner(SpawnerBase):
    """
    Starts an executor by forking a process
    """

    def __init__(self):
        """
        Constructor, creates logger instance and initialize connection
        to docker daemon.
        """
        super().__init__()

        # store our working directory to be used for validation of job's
        # processes
        self._cwd = os.getcwd()
    # __init__()

    @staticmethod
    def _spawn(job_dir, job_type, job_parameters, timeout):
        """
        Start a state machine in a MachineWrapper

        Args:
            job_dir (str): filesystem path to the directory used for the job
            job_type (str): the type of state machine to use
            job_parameters (str): parameters to pass to the state machine
            timeout (int): job timeout in seconds
        """
        wrapped_machine = wrapper.MachineWrapper(
            run_dir=job_dir, job_type=job_type, job_params=job_parameters,
            timeout=timeout
        )
        wrapped_machine.start()
    # _spawn()

    def spawn(self, job_args, environment=None):
        """
        Creates the wrapped state machine instance and starts it.

        Args:
            job_args (dict): job arguments
            environment (dict): environment setting

        job_args should contain the following fields:
            job_dir (str): filesystem path to the directory used for the job
            job_type (str): the type of state machine to use
            job_parameters (str): parameters to pass to the state machine
            timeout (int): job timeout in seconds

        Returns:
            int: pid of the process

        Raises:
            SpawnerError: when process spawn failed
        """

        try:
            process = multiprocessing.Process(
                target=ForkSpawner._spawn,
                kwargs=job_args)

            process.start()
        except multiprocessing.ProcessError as exc:
            raise SpawnerError from exc

        return process.pid
    # spawn()

    def terminate(self, job, force=False):
        """
        Terminate a running job.

        Args:
            job (SchedulerJob): job instance
            force (bool): use force
        """
        if not force:
            os.kill(job.pid, signal.SIGTERM)
        else:
            os.kill(job.pid, signal.SIGKILL)
    # terminate()

    def validate(self, job):
        """
        Verify the state of the job's process (whether it still belongs to a
        tessia job or died).

        Args:
            job (SchedulerJob): job instance

        Returns:
            int: one of the PROCESS_* constants
        """
        inexistent_pid_msg = 'Job {} has inexistent pid {}'.format(
            job.id, job.pid)
        no_permission_msg = 'Job {} has inaccessible pid {}'.format(
            job.id, job.pid)

        try:
            # the read comm will include a newline, so strip it
            with open('/proc/{}/comm'.format(job.pid), 'r') as comm_file:
                proc_comm = comm_file.read().strip()
        except FileNotFoundError:
            self._logger.debug(inexistent_pid_msg)
            return PROCESS_DEAD
        # permission error in case the pid is recycled and the file is created
        # with inaccessible permissions
        except PermissionError:
            self._logger.debug(no_permission_msg)
            return PROCESS_DEAD
        # in rare cases instead of "file not found" we may get a
        # "no such process" error
        except ProcessLookupError:
            self._logger.debug(inexistent_pid_msg)
            return PROCESS_DEAD

        self._logger.debug('Process comm is %s', proc_comm)
        comm_ok = bool(proc_comm == wrapper.WORKER_COMM)

        # verify through the current working directory if the process belongs
        # to the correct job
        proc_cwd_file = '/proc/{}/cwd'.format(job.pid)
        try:
            proc_cwd = os.readlink(proc_cwd_file)
        except FileNotFoundError:
            self._logger.debug(inexistent_pid_msg)
            return PROCESS_DEAD
        # permission error in case the pid is recycled and the file is created
        # with inaccessible permissions
        except PermissionError:
            self._logger.debug(no_permission_msg)
            return PROCESS_DEAD

        self._logger.debug('Process cwd is %s', proc_cwd)
        cwd_ok = bool(os.path.basename(proc_cwd) == str(job.id))

        # Process had time to change its comm and cwd, and they are
        # both correct: consider process as running
        if comm_ok and cwd_ok:
            self._logger.debug('Process is running with cwd and comm correct.')
            return PROCESS_RUNNING

        # At this point we don't know for sure if the process is correct, it
        # might not have had time to change its comm or cwd. However we know
        # that the starting cwd of the worker process is the same as the
        # looper's cwd so if the process' cwd is neither the final worker
        # process cwd nor looper's then it must be another process
        if not cwd_ok and proc_cwd != self._cwd:
            self._logger.warning(
                'Process did not start with looper cwd, assuming dead')
            return PROCESS_DEAD

        # for now assume the process is running and it will eventually either
        # die or change its cwd/comm
        self._logger.warning(
            'Process has not yet set comm and cwd: unknown state.')
        return PROCESS_UNKNOWN
    # validate()

# ForkSpawner
