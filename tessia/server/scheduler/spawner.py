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
from tessia.server.config import CONF
from tessia.server.scheduler import wrapper

import docker
import json
import logging
import multiprocessing
import os
import signal
import uuid

#
# CONSTANTS AND DEFINITIONS
#
PROCESS_RUNNING = 0
PROCESS_DEAD = 1
PROCESS_UNKNOWN = 2

CONTAINER_NAME_FILE = '.spawn_container_name'

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

    @staticmethod
    def exec_machine(job_dir, job_type, job_parameters, timeout):
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
    # exec_machine()

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
                target=ForkSpawner.exec_machine,
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


class ContainerSpawner(SpawnerBase):
    """
    Starts an executor by spawning a new container
    """

    def __init__(self):
        """
        Constructor, creates logger instance and initialize connection
        to docker daemon.
        """
        super().__init__()

        # docker client
        self._client = docker.from_env()

        # get executor image name
        self._image_name = os.getenv('TESSIA_EXECUTOR_IMAGE')
        if not self._image_name:
            raise RuntimeError('Executor image not defined in environment '
                               'variable TESSIA_EXECUTOR_IMAGE')
        self._compose_name = os.getenv('TESSIA_COMPOSE_NAME')
        if not self._image_name:
            raise RuntimeError('Compose name not defined in environment '
                               'variable TESSIA_COMPOSE_NAME')
        self._container_prefix = 'tessia_job_executor'

        self._jobs_dir = CONF.get_config().get('scheduler')['jobs_dir']

        #
    # __init__()

    def spawn(self, job_args, environment=None):
        """
        Starts a job executing container in a specified environment

        Args:
            job_args (dict): job arguments
            environment (dict): environment setting

        job_args should contain the following fields:
            job_dir (str): filesystem path to the directory used for the job
            job_type (str): the type of state machine to use
            job_parameters (str): parameters to pass to the state machine
            timeout (int): job timeout in seconds

        Returns:
            int: pid of the process (0 for container implementation)

        Raises:
            SpawnerError: when process spawn failed
        """
        # generate unique container name
        job_id_str = job_args['job_dir'].rsplit('/', 1)[-1]
        container_name = '{}_{}_{}'.format(
            self._container_prefix, job_id_str,
            str(uuid.uuid4()).replace('-', '')[:8])

        # Write container name to a file in job directory.
        # Normally job directory is created by MachineWrapper,
        # but we should get ahead of it and store container name there
        try:
            os.makedirs(job_args['job_dir'], exist_ok=True)
        except Exception as exc:
            raise SpawnerError(
                "Cannot create job directory {}".format(
                    job_args['job_dir'])) from exc

        container_tag_path = os.path.join(
            job_args['job_dir'], CONTAINER_NAME_FILE)
        try:
            with open(container_tag_path, 'w') as container_name_file:
                container_name_file.write(container_name)
        except Exception as exc:
            raise SpawnerError(
                "Cannot write container tag to {}".format(
                    job_args['job_dir'])) from exc

        # start the new container
        self._logger.debug('starting job container %s', container_name)
        try:
            # Right now the spawned container is a copy of tessia server
            # with all mounts and permissions. It is necessary to keep
            # configuration and database connectivity for state machines
            # to work.
            # TODO: create containers with least access possible,
            # which means rewriting state machines to run without
            # database and config
            container_obj = self._client.containers.run(
                image=self._image_name, name=container_name,
                detach=True,             # immediately return Container object
                remove=True,             # Removes container when finished
                stdin_open=True, tty=False,
                entrypoint=['/usr/bin/python3', '-m',
                            'tessia.server.scheduler.exec'],
                network_mode="container:{}_server_1".format(
                    self._compose_name),
                ports={},
                volumes_from=["{}_server_1".format(self._compose_name)],
            )
        # also catches docker.errors.ImageNotFound (inherits from api error)
        except docker.errors.APIError as exc:
            self._logger.warning('Container start failed: %s', str(exc))
            raise SpawnerError('Failed to start a containerized job') from exc

        self._logger.debug('job container status is <%s>',
                           container_obj.status)

        try:
            # pass job arguments as a json-encoded object to stdin
            self._logger.debug('sending job arguments to %s', container_name)
            with self._client.api.attach_socket(
                    container_obj.id,
                    params={'stdin': 1, 'stream': 1}) as stdin_socket:
                # to make things more weird, socket is a SocketIO socket,
                # and we access the lower level socket through a private
                # member.
                # A newline character is an equally disturbing phenomenon
                # that seems to help with line buffering somewhere along
                # the way to receiving stdin
                stdin_socket._sock.send(json.dumps(
                    job_args).encode('utf-8') + b'\n')
                stdin_socket.close()

        except docker.errors.APIError as exc:
            raise SpawnerError('Failed to pass job arguments') from exc

        self._logger.debug('started job container %s', container_name)

        # containers are not pid based, so we can return zero as pid
        return 0
    # spawn()

    def terminate(self, job, force=False):
        """
        Terminate a running job.

        Args:
            job (SchedulerJob): job instance
            force (bool): use force
        """
        job_dir = '{}/{}'.format(self._jobs_dir, job.id)
        try:
            # read container name from tag file in job directory
            with open(os.path.join(job_dir, CONTAINER_NAME_FILE)) as tag_file:
                container_name = tag_file.readline()
        except Exception as exc:
            # file is not accessible for any reason - nothing to do here
            self._logger.debug(
                'could not get container name for job id %d: %s',
                job.id, str(exc))
            return

        try:
            # obtain a handle to the container
            container_obj = self._client.containers.get(container_name)
        except docker.errors.NotFound as exc:
            self._logger.debug('could not find container %s for job id %d: %s',
                               container_name, job.id, str(exc))
            return
        except docker.errors.APIError as exc:
            self._logger.debug('docker API not available: %s', str(exc))
            return

        try:
            # stop/kill the container
            if not force:
                container_obj.stop()
            else:
                container_obj.kill()
        except docker.errors.APIError as exc:
            self._logger.debug('counld not stop container %s: %s',
                               container_name, str(exc))
            return
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
        job_dir = '{}/{}'.format(self._jobs_dir, job.id)
        try:
            # read container name from tag file in job directory
            with open(os.path.join(job_dir, CONTAINER_NAME_FILE)) as tag_file:
                container_name = tag_file.readline()
        except Exception:
            # file is not accessible for any reason - nothing to do here
            if job.pid == 0:
                # containerized job, no container tag - something has gone
                # completely wrong
                self._logger.debug('job %d has no container tag', job.id)
                return PROCESS_DEAD

            # there is a valid PID, meaning it is not a containerized job
            # and should be checked by a different spawner
            self._logger.debug('job %d has no container tag and valid PID',
                               job.id)
            forker = ForkSpawner()
            return forker.validate(job)

        try:
            # obtain a handle to the container
            container_obj = self._client.containers.get(container_name)
        except docker.errors.NotFound:
            self._logger.debug('container %s not found for job %d',
                               container_name, job.id)
            return PROCESS_DEAD
        except docker.errors.APIError:
            # assume API errors are temporary
            self._logger.debug(
                'API failure while searching container %s for job %d',
                container_name, job.id)
            return PROCESS_UNKNOWN
        except Exception:
            self._logger.debug(
                'Unhandled exception while searching container %s for job %d',
                container_name, job.id)
            return PROCESS_DEAD

        if container_obj.status in ('running', 'paused'):
            return PROCESS_RUNNING

        return PROCESS_DEAD
    # validate()

# ContainerSpawner
