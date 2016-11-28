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

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
def spawn(job_dir, job_type, job_parameters):
    """
    Creates the wrapped state machine instance and start it.

    Args:
        job_dir (str): filesystem path to the directory used for the job
        job_type (str): the type of state machine to use
        job_parameters (str): parameters to pass to the state machine
    """
    from tessia_engine.scheduler import wrapper

    wrapped_machine = wrapper.MachineWrapper(
        job_dir, job_type, job_parameters)
    wrapped_machine.start()
# spawn()
