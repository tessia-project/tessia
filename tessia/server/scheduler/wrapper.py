# Copyright 2017 IBM Corp.
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
from tessia.server.state_machines import MACHINES
from tessia.server.scheduler import exceptions

import builtins
import logging
import os
import pickle
import signal
import sys

#
# CONSTANTS AND DEFINITIONS
#

# How much time to wait for machine to cleanup after a signal was received
CLEANUP_TIME = 60

# Cancel signals we can handle
CANCEL_SIGNALS = (
    signal.SIGTERM,
    signal.SIGHUP,
    signal.SIGINT
)

# Format used to save the end date as string
DATE_FORMAT = '%Y-%m-%d %H:%M:%S:%f'

# Status codes that will be parsed by the looper
RESULT_CANCELED = -1
RESULT_TIMEOUT = -2
RESULT_EXCEPTION = -3
RESULT_SUCCESS = 0

# String to be used in process comm to identify it as a tessia job in the list
# of processes
WORKER_COMM = 'tessia-job'

# Name for the file that will hold picked parameters when execv-ing
# in interrupted workers
WRAPPER_PARAMETERS_FILE = 'wrapper_init_parameters'

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

    def __init__(self, run_dir, job_type, job_params, timeout):
        """
        Constructor, only initializes internal variables
        """
        self._logger = logging.getLogger(__name__)
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

        self._timeout = timeout

        self._mask_timeouts = False

    # __init__()

    def _pickle_cleanup_parameters(self, ret_code):
        """
        Write the parameters needed to build a new MachineWrapper to
        run the cleanup routine.

        Args:
            ret_code (int): status of the state machine start method
        Returns:
        Raises:
        """

        # The file will be written in the current working directory of the job.
        with open(WRAPPER_PARAMETERS_FILE, 'wb') as params_file:
            pickle.dump(
                (ret_code, self._run_dir, self._job_type,
                 self._job_params, self._timeout),
                params_file)
    # _pickle_cleanup_parameters()

    def _supress_signals(self):
        """
        Set any cancel signals do be ignored, cancel any outstanding alarms,
        and mask any pending alarms that could already have been triggered.

        Masking alarms is necessary since python only calls a signal handling
        function at an unspecified time after the signal was happened.
        This means that the alarm handling function could be called even after
        the alarm was reset with alarm(0).

        Args:
        Returns:
        Raises:
        """
        MachineWrapper.set_cancel_signal_handler(signal.SIG_IGN)
        self._mask_timeouts = True
        signal.alarm(0)

    def _handle_cancel(self, *args, **kwargs):
        """
        Handle a cancel signal.

        Args:
        Returns:
        Raises:
            WrapperCanceled
        """

        self._logger.error('Caught cancel signal, cleaning up and aborting...')
        # Don't let cancel signals arrive after this one is handled.
        self._supress_signals()

        raise exceptions.WrapperCanceled
    # _handle_cancel()

    def _handle_timeout(self, *args, **kwargs):
        """
        Handle a regular timeout when the state machine is executing.

        Args:
        Returns:
        Raises:
            WrapperTimeout, when not supressed
        """
        self._logger.error(
            'Caught timeout signal, cleaning up and aborting...')
        if self._mask_timeouts:
            # Ignore delayed alarms.
            return

        # Don't let cancel signals arrive after this one is handled.
        self._supress_signals()

        raise exceptions.WrapperTimeout
    # _handle_timeout()

    def _handle_cleanup_timeout(self, *args, **kwargs):
        """
        Handle a timeout when the state machine is cleaning up after a timeout
        or cancel signal.

        Args:
        Returns:
        Raises:
            WrapperTimeout, when not supressed
        """
        self._logger.error('Caught timeout signal while cleaning up')
        if self._mask_timeouts:
            return

        # Cancel signals are already ignored at the start of the cleanup,
        # no point in doing it again here, we just need to supress the alarm.
        self._mask_timeouts = True
        signal.alarm(0)

        raise exceptions.WrapperTimeout
    # _handle_cleanup_timeout()

    def _write_result(self, ret_code, cleanup_code=None):
        """
        Write the result file with exit code, cleanup code and end time,
        one in each of three lines.

        Args:
            ret_code (int): status code for the start method of the machine
            cleanup_code (int): status code for the cleanup method

        Returns:
        Raises:
        """
        status = [str(ret_code)]

        if cleanup_code is not None:
            status.append(str(cleanup_code))

        status.append(datetime.utcnow().strftime(DATE_FORMAT))

        with open(self._result_file, 'w') as result_file:
            result_file.write('{}\n'.format('\n'.join(status)))

    # _write_result()

    @classmethod
    def set_cancel_signal_handler(cls, handler):
        """
        Set the handler function for all cancellation signals.

        Args:
            handler (function): signal handler, like for signal.signal

        Returns:
        Raises
        """
        for signal_type in CANCEL_SIGNALS:
            signal.signal(signal_type, handler)

    @classmethod
    def write_comm(cls):
        """
        Change the process comm so that the scheduler can identify it.

        This is a class method so that it can be called early on by
        a new interpreter when handling timeout/cancel signals.

        Args:
        Returns:
        Raises:
        """
        with open('/proc/self/comm', 'w') as comm_file:
            # comm file gets truncated to 15-bytes + null terminator
            comm_file.write(WORKER_COMM)
    # write_comm

    def start(self):
        """
        Redirect the process outputs, setup signals and
        start the state machine.

        Args:
        Returns:
        Raises:
        """
        os.makedirs(self._run_dir, exist_ok=True)
        log_file = open('{}/output'.format(self._run_dir), 'wb')
        sys.stdout.flush()
        os.dup2(log_file.fileno(), sys.stdout.fileno())
        sys.stderr.flush()
        os.dup2(log_file.fileno(), sys.stderr.fileno())

        # replace the original print by one that always performs flush
        # so that output goes directly to the file
        orig_print = builtins.print
        def new_print(*args, **kwargs):
            """Print function with auto-flush"""
            if 'flush' in kwargs:
                kwargs.pop('flush')
            orig_print(*args, **kwargs, flush=True)
        builtins.print = new_print

        MachineWrapper.write_comm()

        os.chdir(self._run_dir)

        self._machine = MACHINES.classes[self._job_type](
            self._job_params)

        timed_out = False

        try:
            # This outer try block is to catch the timeout/cancel
            # exceptions.
            try:
                # This inner try block is to ensure the timeout/cancel
                # signals are supressed i nthe finally block.

                MachineWrapper.set_cancel_signal_handler(self._handle_cancel)

                if self._timeout > 0:
                    # Timeout was provided: set the alarm.
                    self._mask_timeouts = False
                    signal.signal(signal.SIGALRM, self._handle_timeout)
                    signal.alarm(self._timeout)

                try:
                    ret_code = self._machine.start()
                except Exception:
                    sys.excepthook(*sys.exc_info())
                    ret_code = RESULT_EXCEPTION

            finally:
                self._supress_signals()

            # At this point start and cleanup finished, the signals are
            # are supressed and we can safely write the exit codes and
            # finish.
            self._write_result(ret_code)
            return

        except exceptions.WrapperCanceled:
            pass
        except exceptions.WrapperTimeout:
            timed_out = True

        # At this point either there was a timeout or a cancel signal.

        if timed_out:
            ret_code = RESULT_TIMEOUT
        else:
            ret_code = RESULT_CANCELED

        if self._machine.cleaning_up:
            # The state machine was in the process of cleaning up,
            # don't do it again.
            self._write_result(ret_code)
            return

        # The state machine was not yet cleaning up, do it in
        # a new interpreter since the timeout/cancel exceptions
        # could have left everything in an undefined state.
        self._exec_for_cleanup(ret_code)
    # start()

    def _exec_for_cleanup(self, ret_code):
        """
        Substitute the current process by a new interpreter
        that will call the machine's cleanup routine.

        Args:
            ret_code (int): status code for the executed start method

        Returns:
        Raises:
        """
        self._pickle_cleanup_parameters(ret_code)
        python_location = os.readlink('/proc/self/exe')
        os.execv(python_location,
                 ['python', '-m', __name__])
    # _exec_for_cleanup

    def interruption_cleanup(self, ret_code):
        """
        Run the cleanup routine for the state machine. Should be called
        in a new interpreter after the original machine was preempted by
        a timeout or cancel signal.

        Report the status of the original state machine and the cleanup phase
        in a file.

        Args:
            ret_code (int): the status of the state machine that was executing
                            before the cleanup
        Returns:
        Raises:
        """
        machine = MACHINES.classes[self._job_type](
            self._job_params)

        try:
            try:
                self._mask_timeouts = False
                signal.signal(signal.SIGALRM, self._handle_cleanup_timeout)
                signal.alarm(CLEANUP_TIME)

                try:
                    cleanup_code = machine.cleanup()
                except Exception:
                    sys.excepthook(*sys.exc_info())
                    cleanup_code = RESULT_EXCEPTION
            finally:
                self._mask_timeouts = True
                signal.alarm(0)

        except exceptions.WrapperTimeout:
            cleanup_code = RESULT_TIMEOUT

        self._write_result(ret_code, cleanup_code)

# MachineWrapper

def do_interruption_cleanup():
    """
    Read pre-pickled parameters for a machine wrapper and run the cleanup
    for this machine. To be called after executing a new python interpreter
    when handling cancel/timeout signals.
    """
    # Ignore signals since we are already cleaning up.
    MachineWrapper.set_cancel_signal_handler(signal.SIG_IGN)
    MachineWrapper.write_comm()

    # We should be in the job working directory, where the previous interpreter
    # in this process wrote the pickled parameters we need.
    with open(WRAPPER_PARAMETERS_FILE, 'rb') as params_file:
        params = pickle.load(params_file)

    try:
        # Status of the state machine before we switched interpreters.
        ret_code = params[0]

        wrapper_params = params[1:]
        wrapper = MachineWrapper(*wrapper_params)
        wrapper.interruption_cleanup(ret_code)
    finally:
        os.remove(WRAPPER_PARAMETERS_FILE)

if __name__ == '__main__':
    # This module is called as the main module when executing a fresh
    # python interpreter when handling timeout/cancel signals.
    do_interruption_cleanup()
