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
Job root group to which all commands are attached
"""

#
# IMPORTS
#
from tessia.cli.cmds.job.job import CMDS as job_cmds

import click

#
# CONSTANTS AND DEFINITIONS
#
CMDS = job_cmds

#
# CODE
#
@click.group()
def job():
    """
    commands related to scheduler jobs
    """
    pass
# job()

# add all the subcommands
for cmd in CMDS:
    job.add_command(cmd)
