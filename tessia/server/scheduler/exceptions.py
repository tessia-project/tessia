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
Module containing the exceptions used by the scheduler and wrapper modules.
"""

#
# IMPORTS
#

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class WrapperTimeout(BaseException):
    """
    Exception raised by the alarm signal handler in
    the wrapper.

    It inherits from BaseException so that it won't be caught
    by the state machines.
    """


class WrapperCanceled(BaseException):
    """
    Exception raised by the cancel signal handlers in
    the wrapper.

    It inherits from BaseException so that it won't be caught
    by the state machines.
    """
