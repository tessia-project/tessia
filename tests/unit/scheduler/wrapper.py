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

from tessia.server.scheduler import wrapper
from tessia.server.state_machines import base
from unittest import TestCase
from unittest import mock
from unittest.mock import patch

import unittest


#
# CONSTANTS AND DEFINITIONS
#

RUN_DIR = "/some/fake/dir"
MACHINE_NAME = "test-machine"

#
# CODE
#
class TestWrapper(TestCase):
    """
    Unit test for the machine wrapper module
    """

    def setUp(self):
        """
        Prepare the necessary patches at the beginning of each testcase
        """

        # logging module
        patcher = patch.object(wrapper, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)
        mock_logging.getLogger.return_value = mock.Mock(
            spec=['warning', 'error', 'debug', 'info'])

        # signal module
        patcher = patch.object(wrapper, 'signal', autospect=True)
        self._mock_signal = patcher.start()
        self.addCleanup(patcher.stop)

        # os module
        patcher = patch.object(wrapper, 'os', autospect=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        # open built-in function
        patcher = patch.object(wrapper, 'open', autospect=True)
        self._mock_open = patcher.start()
        self.addCleanup(patcher.stop)

        # pickle module
        patcher = patch.object(wrapper, 'pickle', autospect=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        # sys module
        patcher = patch.object(wrapper, 'sys', autospect=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        # patch machines dict to return a fake test machine
        machine_class = mock.MagicMock()

        # Mock the state machine registry so the wrapper will find
        # the mocked state machine class.
        dict_patcher = patch.dict(
            wrapper.MACHINES.classes,
            {MACHINE_NAME: machine_class})
        dict_patcher.start()
        self.addCleanup(dict_patcher.stop)

        machine_class.return_value = mock.MagicMock(spec=base.BaseMachine)

        self._mock_machine = machine_class.return_value

        self._wrapper = wrapper.MachineWrapper(RUN_DIR, MACHINE_NAME, '', 0)

    def _check_written_rc(self, ret, cleanup_ret=None):
        # check if the result was corretly written to the results file
        mock_write = self._mock_open.return_value.__enter__.return_value.write

        # Result will be something like
        # <rc>\n<cleanup_rc>\n<end_date>\n

        written_lines = mock_write.call_args[0][0].split('\n')

        # A trailing newline causes an empty line to appear at the end
        # of the split array.
        if not written_lines[-1]:
            written_lines = written_lines[:-1]

        written_ret = int(written_lines[0])

        self.assertEqual(ret, written_ret)

        if cleanup_ret is not None:
            self.assertEqual(len(written_lines), 3)
            written_cleanup_ret = int(written_lines[1])
            self.assertEqual(cleanup_ret, int(written_cleanup_ret))
        else:
            self.assertEqual(len(written_lines), 2)

    def _run_normal_start(self, ret=None):
        """
        Run start on a machine wrapper with no interruptions. Check if the
        results are properly written.
        """

        assert ret is not None
        self._mock_machine.start.return_value = ret
        expected_rc = ret

        self._wrapper.start()

        self._check_written_rc(expected_rc)

    def _run_interrupted_start(self, timeout=False, exception=None,
                               cleanup_ret=None, cleanup_exception=None,
                               cleanup_timeout=False):
        # either an exception occurs during machine start/run or
        # a signal triggers either a WrapperTimeout or WrapperCanceled
        # Exception
        if timeout:
            self._wrapper.timeout = 5

            def start_side_effect():
                """
                Simulate a machine start method that receives
                an alarm by directly calling the signal handler.
                """
                # Call the timeout handler twice to excercise
                # all paths. The exception from the first call will
                # still be raised after the finally block exits.
                try:
                    self._wrapper._handle_timeout()
                finally:
                    self._wrapper._handle_timeout()

            self._mock_machine.start.side_effect = start_side_effect
            expected_ret = wrapper.RESULT_TIMEOUT
        elif exception:
            self._mock_machine.start.side_effect = exception
            expected_ret = wrapper.RESULT_EXCEPTION
        else:
            def start_side_effect():
                """
                Simulate a machine start method that receives
                a cancel signal by directly calling the signal handler.
                """
                self._wrapper._handle_cancel()

            self._mock_machine.start.side_effect = start_side_effect
            expected_ret = wrapper.RESULT_CANCELED

        if self._mock_machine.cleaning_up:
            # machine was set to be cleaning up during interruption,
            # we don't expect a cleanup return code
            expected_cleanup_ret = None
        else:
            # machine was set to not be cleaning up during interruption,
            # we expect it to run the cleanup

            pickled_params_ref = {}

            def pickle_dump_side_effect(obj, dump_file):
                """
                Mock for pickle dump wich sets the value in a dictionary
                that will be retrieved by the pickle load mock.
                """
                # pylint: disable=unused-argument
                pickled_params_ref['params'] = obj

            wrapper.pickle.dump.side_effect = pickle_dump_side_effect

            def pickle_load_side_effect(dump_file):
                """
                Mock for pickle load which gets the value set by
                the mocked pickle dump.
                """
                # pylint: disable=unused-argument
                return pickled_params_ref['params']

            wrapper.pickle.load.side_effect = pickle_load_side_effect

            def execv_side_effect(*args, **kwargs):
                """
                Mock for os.execv that directly calls the function that
                the wrappr module calls when executed.
                """
                wrapper.do_interruption_cleanup()

            wrapper.os.execv.side_effect = execv_side_effect

            if cleanup_timeout:

                def cleanup_side_effect():
                    """
                    Mock the machine cleanup routine called during
                    the interruption routine so that it "times out".
                    """
                    # Cheating here, but I can't obtain a reference
                    # to the wrapper that is created during the interrupt
                    # routine at this point, so the signal handler from
                    # the original wrapper will be called.
                    self._wrapper._mask_timeouts = False

                    # Exercise all handler paths by calling it twice.
                    try:
                        self._wrapper._handle_cleanup_timeout()
                    finally:
                        self._wrapper._handle_cleanup_timeout()

                self._mock_machine.cleanup.side_effect = cleanup_side_effect
                expected_cleanup_ret = wrapper.RESULT_TIMEOUT
            elif cleanup_exception is not None:
                self._mock_machine.cleanup.side_effect = cleanup_exception
                expected_cleanup_ret = wrapper.RESULT_EXCEPTION
            else:
                assert cleanup_ret is not None
                self._mock_machine.cleanup.return_value = cleanup_ret
                expected_cleanup_ret = cleanup_ret

        self._wrapper.start()

        if timeout:
            self._mock_signal.alarm.assert_has_calls(
                [mock.call(self._wrapper._timeout)])

        self._check_written_rc(expected_ret,
                               expected_cleanup_ret)

    def test_start(self):
        """
        Test normal executions of the start method.
        """

        # test without a timeout
        self._mock_machine.cleaning_up = True
        self._run_normal_start(ret=wrapper.RESULT_SUCCESS)

        # no timeout and no interruption cleanup
        # means alarm should not have been called except for resetting
        alarm_args = self._mock_signal.alarm.call_args_lists

        for call in alarm_args:
            self.assertEqual(call, (0,))

    def test_machine_start_exception(self):
        """
        Test a wrapper that has machine starting with an exception but
        performs a successful cleanup
        """
        self._mock_machine.cleaning_up = False
        self._run_interrupted_start(exception=RuntimeError('test'),
                                    cleanup_ret=wrapper.RESULT_SUCCESS)

    def test_machine_start_exception_cleanup_exception(self):
        """
        Test a wrapper that has machine starting with an exception and also
        fails during cleanup.
        """
        self._mock_machine.cleaning_up = False
        self._run_interrupted_start(exception=RuntimeError('test'),
                                    cleanup_exception=RuntimeError("test"))

    def test_canceled_start_no_cleanup(self):
        """
        Test a wrapper that starts and gets interrupted by a cancel
        signal during normal cleanup.
        """

        self._mock_machine.cleaning_up = True
        self._run_interrupted_start(cleanup_ret=wrapper.RESULT_SUCCESS)

    def test_timed_out_start_with_cleanup_failing(self):
        """
        Test a wrapper that starts and gets interrupted by an alarm
        and the cleanup routine fails with an exception.
        """
        self._mock_machine.cleaning_up = False
        self._run_interrupted_start(timeout=True,
                                    cleanup_exception=RuntimeError('test'))

    def test_timed_out_start_with_timed_out_cleanup(self):
        """
        Test a wrapper that starts and gets interrupted by an alarm
        and the cleanup routine itself also times out.
        """
        self._mock_machine.cleaning_up = False
        self._run_interrupted_start(timeout=True,
                                    cleanup_timeout=True)

if __name__ == '__main__':
    unittest.main()
