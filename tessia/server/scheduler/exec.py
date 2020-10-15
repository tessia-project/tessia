# Copyright 2020 IBM Corp.
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
Entrypoint for starting separate executors
"""

#
# IMPORTS
#
from jsonschema import validate
from tessia.server.lib.json_stream import JsonStream
from tessia.server.scheduler.spawner import SpawnerBase

import sys

#
# CONSTANTS AND DEFINITIONS
#
DESCRIPTION = """Tessia standalone job executor.

Provide the following job arguments on stdin as json-encoded object:
{
    job_dir (str): filesystem path to the directory used for the job
    job_type (str): the type of state machine to use
    job_parameters (str): parameters to pass to the state machine
    timeout (int): job timeout in seconds (0 to disable)
}
"""

# Schema to validate the job request
REQUEST_SCHEMA = {
    'type': 'object',
    'properties': {
        'job_dir': {
            'type': 'string'
        },
        'job_type': {
            'type': 'string',
        },
        'job_parameters': {
            'type': 'string'
        },
        'timeout': {
            'type': 'integer'
        },
    },
    'required': [
        'job_dir',
        'job_type',
        'job_parameters',
        'timeout'
    ],
    'additionalProperties': True
}


#
# CODE
#


def usage():
    """
    Print usage and exit
    """
    print("Usage: exec.py")
    print("")
    print(DESCRIPTION)
    sys.exit()

# usage()


def main():
    """
    Entry point to start the executor
    """
    # create the argument parser object and feed it with the possible options
    if len(sys.argv) > 1:
        usage()

    try:
        job_arguments = {}
        for value in JsonStream(sys.stdin):
            job_arguments = value
            break
    except Exception as exc:
        print("Failed to parse parameter object on stdin:", str(exc),
              file=sys.stderr)
        usage()

    # check that all required arguments are specified
    try:
        validate(job_arguments, REQUEST_SCHEMA)
    except Exception as exc:
        print("Parameter object does not match schema:", str(exc),
              file=sys.stderr)
        usage()

    # start the machine
    SpawnerBase.exec_machine(**job_arguments)

# main()


if __name__ == '__main__':
    main()
