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
Module to handle state machine output, signals and result reports.
"""

#
# IMPORTS
#
from datetime import datetime
from tessia_engine import state_machines

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

# exit codes
RESULT_CANCELED = -1
RESULT_CANCELED_TIMEOUT = -2
RESULT_TIMEOUT = -3
RESULT_SUCCESS = 0

# string to be used in process comm to identify it as a tessia job in the list
# of processes
WORKER_COMM = 'tessia-job'

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
        # flag used to tell handler_cleanup_timeout whether the job failed
        # because of a timeout or because it was canceled
        self._timeout = False
    # __init__()

    def _handle_cancel(self, *args, **kwargs):
        """
        Action executed when a cancel signal (see CANCEL_SIGNALS) is received.
        Performs a cleanup, writes the result to the result file and exits.
        """
        try:
            signal.alarm(0)
            # replace the handler and give some time for the machine to finish
            signal.signal(signal.SIGALRM, self._handle_cleanup_timeout)
            signal.alarm(CLEANUP_TIME)

            # ask the machine to clean up
            self._machine.cleanup()
        except: # pylint: disable=bare-except
            # print the exception to stderr
            sys.excepthook(*sys.exc_info())
        finally:
            self._write_result(RESULT_CANCELED)
            os._exit(1) # pylint: disable=protected-access
    # _handle_cancel()

    def _handle_cleanup_timeout(self, *args, **kwargs):
        """
        Handles the signal which occurs when the cleanup routine in machine
        times out while executing
        """
        print('warning: clean up timed out and did not complete')
        if self._timeout:
            ret = RESULT_TIMEOUT
        else:
            ret = RESULT_CANCELED_TIMEOUT
        self._write_result(ret)
        os._exit(1) # pylint: disable=protected-access
    # _handle_cleanup_timeout()

    def _handle_timeout(self, *args, **kwargs):
        try:
            signal.alarm(0)
            # replace the handler and give some time for the machine to finish
            signal.signal(signal.SIGALRM, self._handle_cleanup_timeout)
            signal.alarm(CLEANUP_TIME)
            self._timeout = True

            # ask the machine to clean up
            self._machine.cleanup()

        except: # pylint: disable=bare-except
            # print the exception to stderr
            sys.excepthook(*sys.exc_info())
        finally:
            self._write_result(RESULT_TIMEOUT)
            os._exit(1) # pylint: disable=protected-access
    # _handle_timeout()

    def _write_result(self, ret_code):
        """
        Write the result file with exit code and end time

        Args:
            ret_code (int): the exit code to be written in result file
        """
        with open(self._result_file, 'w') as result_file:
            result_file.write('{}\n{}\n'.format(
                ret_code, datetime.utcnow().strftime(DATE_FORMAT)))

    # _write_result()

    def start(self):
        """
        Redirect the process outputs, setup signals and start the state
        machine
        """
        os.makedirs(self._run_dir, exist_ok=True)
        log_file = open('{}/output'.format(self._run_dir), 'wb')
        sys.stdout.flush()
        os.dup2(log_file.fileno(), sys.stdout.fileno())
        sys.stderr.flush()
        os.dup2(log_file.fileno(), sys.stderr.fileno())

        with open('/proc/self/comm', 'w') as comm_file:
            # comm file gets truncated to 15-bytes + null terminator
            comm_file.write(WORKER_COMM)

        os.chdir(self._run_dir)
        # here we are in the forked process and can start the machine
        self._machine = state_machines.MACHINES[self._job_type](
            self._job_params)

        # assure a graceful shutdown in case of interruption
        for signal_type in CANCEL_SIGNALS:
            signal.signal(signal_type, self._handle_cancel)

        # sigalarm occurs if test timeout was reached
        # TODO: enable timeout feature
        # signal.signal(signal.SIGALRM, self._handle_timeout)

        try:
            ret = self._machine.start()
        # we still need to write the results file before exiting therefore any
        # exception needs to be caught
        except: # pylint: disable=bare-except
            # print the exception to stderr
            sys.excepthook(*sys.exc_info())
            # set exit code to error
            ret = 1

        self._write_result(ret)
        sys.exit(ret)
    # start()

# MachineWrapper
