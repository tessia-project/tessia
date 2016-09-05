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


#
# IMPORTS
#
from datetime import datetime
from tessia_engine import state_machines
from tessia_engine.db.connection import SESSION

import os
import signal
import sys

#
# CONSTANTS AND DEFINITIONS
#

# how much time to wait for machine to cleanup after a signal was received
CLEANUP_TIME = 60

# which signals we are handling
CANCEL_SIGNALS = (
    signal.SIGTERM,
    signal.SIGHUP,
    signal.SIGINT
)

# format used to save the end date as string
DATE_FORMAT = '%Y-%m-%d %H:%M:%S:%f'

#
# CODE
#
class MachineWrapper(object):
    """
    This class' purpose is to create the appropriate environment for the state
    machine to run. That means:
    - handle signals to gracefully shutdown the machine
    - make sure the job finishes if timeout is reached
    - redirect streams to the correct output file defined by the scheduler
    - switch to the appropriate working directory so that the machine has a
      place to store its files if needed
    """

    def __init__(self, run_dir, job_type, job_params):
        """
        Constructor, only initializes internal variables
        """
        # instance of state machine
        self._machine = None
        # we switch to this directory after forking
        self._run_dir = run_dir
        # job type determines which state machine to use
        self._job_type = job_type
        # parameters to pass to the state machine
        self._job_params = job_params
        # path to results file where exit code and end date will be store on
        # test end
        self._result_file = '{}/.{}'.format(
            self._run_dir, os.path.basename(self._run_dir))
        # flag to tell the handler for cleanup timeout whether the job failed
        # because of a timeout or canceled
        self._timeout = False
    # __init__()

    def _fork(self):
        """
        Fork a separate process to run the state machine. A double fork is made
        to prevent the process from becoming a zombie (it would have to be
        waited by the parent process to avoid that) and from accidentally
        acquiring a controlling terminal.
        """
        # create the job's directory and log file before forking, otherwise
        # if it fails in the forked process we wouldn't know what happened
        # these can raise exceptions if permissions are not correct
        os.makedirs(self._run_dir, exist_ok=True)
        log_file = open('{}/output'.format(self._run_dir), 'wb')

        # use a pipe to allow the grandchild to inform scheduler of its pid
        pipe_read, pipe_write = os.pipe()
        pipe_read = os.fdopen(pipe_read, 'r')
        pipe_write = os.fdopen(pipe_write, 'w')
        pid = os.fork()

        # parent
        if pid != 0:
            log_file.close()
            pipe_write.close()
            os.waitpid(pid, 0)
            executor_pid = pipe_read.read()
            pipe_read.close()
            return executor_pid

        # child
        pipe_read.close()
        pid = os.fork()
        if pid != 0:
            log_file.close()
            # write the grandchild pid to the pipe to inform scheduler process
            pipe_write.write(str(pid))
            pipe_write.close()
            # kill the child process so that the grandchild gets re-parented
            # and thus do not become a zombie later
            os._exit(0)

        # grandchild - here we are in the state machine process

        # close fds we don't want to use
        pipe_write.close()
        sys.stdin.close()

        # redirect all its output to the appropriate log file
        sys.stdout.flush()
        os.dup2(log_file.fileno(), sys.stdout.fileno())
        sys.stderr.flush()
        os.dup2(log_file.fileno(), sys.stderr.fileno())

        # change command line so that our process can be spotted in the process
        # list
        with os.open('/proc/self/task/{}/comm'.format(pid), 'w') as comm_file:
            # comm file gets truncated to 15-bytes + null terminator
            comm_file.write('tessia-{}'.format(self._job_type))

        # change the current working directory of the process so that
        # it can then create any files there
        os.chdir(self._run_dir)

        return 0
    # _fork()

    def _handle_cancel(self, *args, **kwargs):
        # replace the handler and give some time for the machine to finish
        signal.signal(signal.SIGALRM, self._handle_cleanup_timeout)
        signal.alarm(CLEANUP_TIME)

        # ask the machine to clean up
        self._machine.cleanup()

        self._write_result(1)
        sys.exit(1)
    # _handle_cancel()

    def _handle_cleanup_timeout(self, *args, **kwargs):
        """
        Handles the signal which occurs when the cleanup routine in machine
        times out while executing
        """
        print('warning: clean up timed out and did not complete')
        if self._timeout:
            # -1 is interpreted by the scheduler as timed out
            ret = -1
        else:
            ret = 1
        self._write_result(ret)
        sys.exit(1)
    # _handle_cleanup_timeout()

    def _handle_timeout(self, *args, **kwargs):
        # replace the handler and give some time for the machine to finish
        signal.signal(signal.SIGALRM, self._handle_cleanup_timeout)
        signal.alarm(CLEANUP_TIME)
        self._timeout = True

        # ask the machine to clean up
        self._machine.cleanup()

        # -1 is interpreted by the scheduler as timed out
        self._write_result(-1)
        sys.exit(1)
    # _handle_timeout()

    def _write_result(self, ret_code):
        """
        Write the result file with exit code and end time
        """
        with open(self._result_file, 'w') as result_file:
            result_file.write('{}\n{}\n'.format(
                ret_code, datetime.utcnow().strftime(DATE_FORMAT)))

    # _write_result()

    def start(self):
        pid = self._fork()
        # return the pid to scheduler
        if pid != 0:
            return pid

        # here we are in the forked process and can start the machine
        self._machine = state_machines.MACHINES[self._job_type](
            self._job_params)

        # assure a graceful shutdown in case of interruption
        for signal_type in CANCEL_SIGNALS:
            signal.signal(signal_type, self._handle_cancel)

        # sigalarm occurs if test timeout was reached
        signal.signal(signal.SIGALRM, self._handle_timeout)

        try:
            ret = self._machine.start()
        # we still need to write the results file before exiting therefore any
        # exception needs to be caught
        # pylint: disable=bare-except
        except:
            # print the exception to stderr
            sys.excepthook(*sys.exc_info())
            # set exit code to error
            ret = 1

        self._write_result(ret)
        sys.exit(ret)
    # start()

# MachineWrapper
