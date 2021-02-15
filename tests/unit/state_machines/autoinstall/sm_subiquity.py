# Copyright 2021 IBM Corp.
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
Unit test for Subiquity-based state machine module.
"""

#
# IMPORTS
#
from tessia.server.state_machines.autoinstall.sm_subiquity import EventMarker
from tessia.server.state_machines.autoinstall.sm_subiquity import LogEvent
from tessia.server.state_machines.autoinstall.sm_subiquity import LogWatcher
from unittest import TestCase

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class TestLogEvent(TestCase):
    """
    LogEvent unit test
    """

    def test_from_binary_event(self):
        """
        Test binary (raw) event string
        """
        source = "binary:filename:size"

        event = LogEvent(source)

        self.assertEqual(str(event), "filename:size")

    def test_from_installer_event(self):
        """
        Test regular installer string
        """
        source = (r'{"name": "subiquity/Meta/status_GET", "description": '
                  r'"200 {\"state\": \"STARTING_UP\", \"confirming_tty\": '
                  r'\"\", \"error\": null, \"cloud_init_ok\"...", '
                  r'"event_type": "finish", "origin": "curtin", "timestamp": '
                  r'1613128538.2999392, "level": "INFO", "result": "SUCCESS"}')

        event = LogEvent(source)

        self.assertEqual(
            str(event),
            r'SUCCESS subiquity/Meta/status_GET : 200 {"state": "STARTING_UP",'
            r' "confirming_tty": "", "error": null, "cloud_init_ok"...')

    def test_from_watchdog_fail_event(self):
        """
        Test watchdog string
        """
        source = (r'{"name": "installer.log", "event_type": "log_dump", '
                  r'"origin": "watchdog", "timestamp": 1613128538.2999392, '
                  r'"level": "DEBUG", "result": "FAIL"}')

        event = LogEvent(source)

        self.assertEqual(
            str(event),
            r'File installer.log not present')

    def test_from_watchdog_success_event(self):
        """
        Test watchdog string
        """
        source = (r'{"name": "installer.log", "event_type": "log_dump", '
                  r'"origin": "watchdog", "timestamp": 1613128538.2999392, '
                  r'"level": "DEBUG", "result": "SUCCESS"}')

        event = LogEvent(source)

        self.assertEqual(
            str(event),
            r'File installer.log retrieved')

    def test_from_unparseable_event(self):
        """
        Test non-json string
        """
        source = (r'Exception: something is wrong')

        event = LogEvent(source)

        self.assertEqual(
            str(event),
            r'Undecodeable event: Exception: something is wrong')

# TestLogEvent


class TestLogWatcher(TestCase):
    """
    LogWatcher unit test
    """

    def setUp(self):
        """
        Setup objects for every test
        """
        # Default instance with a timeout at 10 ticks
        self._watcher = LogWatcher(10.)

    def test_installer_crash(self):
        """
        Test fail sequence
        """
        event = LogEvent(
            r'{"name": "subiquity/Error/1611592891.712457657.ui/add_info", '
            r'"description": "written to /var/crash/1611592891.712457657.ui.'
            r'crash", "event_type": "finish", "origin": "curtin", "timestamp":'
            r' 1611592897.6849818, "level": "DEBUG", "result": "SUCCESS"}')

        marker = self._watcher.process(event, 5.0)

        self.assertEqual(marker, EventMarker.FAIL)
        self.assertTrue(self._watcher.is_failure())
        self.assertFalse(self._watcher.is_success())

    def test_watchdog_event(self):
        """
        Test watchdog log message
        """
        event = LogEvent(
            r'{"name": "curtin-error-logs.tar", "event_type": "log_dump", '
            r'"origin": "watchdog", "timestamp": 1611592897.7736008, "level": '
            r'"DEBUG", "result": "FAIL"}')

        marker = self._watcher.process(event, 5.0)

        self.assertEqual(marker, EventMarker.NONE)
        self.assertFalse(self._watcher.is_failure())
        self.assertFalse(self._watcher.is_success())

    def test_success_ubuntu20(self):
        """
        Test successful sequence for Ubuntu 20
        """
        event = LogEvent(
            r'{"name": "subiquity/Reboot", "description": "completed", '
            r'"event_type": "finish", "origin": "curtin", "timestamp": '
            r'1613165112.2288225, "level": "INFO", "result": "SUCCESS"}')

        marker = self._watcher.process(event, 5.0)

        self.assertEqual(marker, EventMarker.SUCCESS)
        self.assertFalse(self._watcher.is_failure())
        self.assertTrue(self._watcher.is_success())

    def test_success_ubuntu21(self):
        """
        Test successful sequence for Ubuntu 21
        """
        event = LogEvent(
            r'{"name": "subiquity/Reboot/reboot", "description": "", '
            r'"event_type": "finish", "origin": "curtin", "timestamp": '
            r'1613128621.0414705, "level": "DEBUG", "result": "SUCCESS"}')

        marker = self._watcher.process(event, 5.0)

        self.assertEqual(marker, EventMarker.SUCCESS)
        self.assertFalse(self._watcher.is_failure())
        self.assertTrue(self._watcher.is_success())

    def test_stops(self):
        """
        Test watcher stops
        """
         # given time > time in setUp
        self.assertTrue(self._watcher.should_stop(150.0))

# TestLogWatcher
