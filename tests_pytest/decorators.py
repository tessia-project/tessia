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
Test helpers
"""

#
# IMPORTS
#
from functools import update_wrapper


#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#
def tracked(method):
    """
    Decorator for tracked method calls
    """
    class TrackedWrapper:
        """
        Wrapper class for a call
        """

        class TrackerData:
            """
            Recorded data
            """

            def __init__(self):
                self._calls = []

            def record(self, args):
                """
                Append record

                Args:
                    args (tuple): tuple with args, kwargs and result
                """
                self._calls.append(args)

            def set_result(self, result):
                """
                Set result of last call
                """
                self._calls[-1] = (*self._calls[-1][:-1], result)

        def __init__(self, target):
            update_wrapper(self, target)
            self._target = target
            self._current_instance = None

            # "trackers" is a mapping of (instance, method) to tracker data
            self._trackers = {}

        def __call__(self, *args, **kwargs):
            """
            Mark called

            Args:
                args: positional arguments to original call
                kwargs: named arguments to original call

            Returns:
                any: result of wrapped method
            """
            key = (self._current_instance, self._target)
            self._trackers[key].record((*args, kwargs, None))
            result = self._target(self._current_instance, *args, **kwargs)
            self._trackers[key].set_result(result)

            return result

        def __get__(self, instance, instance_type=None):
            """
            Set currently used object instance

            Instance is stored locally to ensure that next method access
            (whether call or tracker data) will use the specified instance
            """
            if instance is None:
                return self

            self._current_instance = instance
            if not self._trackers.get((instance, self._target), None):
                self._trackers[(instance, self._target)] = \
                    TrackedWrapper.TrackerData()

            return self

        @property
        def calls(self):
            """
            List of calls
            """
            key = (self._current_instance, self._target)
            if self._trackers.get(key, None):
                return self._trackers[key]._calls
            return []

        @property
        def called_once(self):
            """
            Was the method called only once
            """
            return len(self.calls) == 1

        @property
        def last_call(self):
            """
            Contents of last call

            Returns:
                tuple: positional args, kwargs dictionary, result
            """
            if self.calls:
                return self.calls[-1]
            return None

    return TrackedWrapper(method)
