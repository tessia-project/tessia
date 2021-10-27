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
Supervisord Tessia instance runner
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


class SupervisordInstance:
    """Tessia instance for supervisord"""

    def __init__(self, configuration) -> None:
        self._conf = configuration
    # __init__()

    def setup(self) -> None:
        """
        Create configuration files for components, check prerequisites etc.
        """
        raise NotImplementedError()
    # setup()

    def run(self) -> None:
        """
        Run the instance
        """
        raise NotImplementedError()
    # run()

    def stop(self) -> None:
        """
        Stop the instance
        """
        raise NotImplementedError()
    # stop()

    def cleanup(self) -> None:
        """
        Cleanup as much as possible
        """
        raise NotImplementedError()
    # cleanup()
# SupervisordInstance
