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
Command line entry point for the canary daemon
"""

#
# IMPORTS
#
from tessia.server.config import CONF
from tessia.server.lib.canary.canary import Canary
import argparse

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


def main():
    """
    Entry point to start the canary daemon
    """
    # create the argument parser object and feed it with the possible options
    parser = argparse.ArgumentParser(
        description='HMC availability status checker'
    )
    parser.add_argument(
        '-d', '--debug', help='enable debug logging',
        required=False, action='store_true')

    # parser error can occur here to inform user of wrong options provided
    parsed_args = parser.parse_args()

    log_level = {True: 'DEBUG', False: None}[parsed_args.debug]
    CONF.log_config(log_level=log_level)

    daemon = Canary()
    daemon.loop()
# main()


if __name__ == '__main__':
    main()
