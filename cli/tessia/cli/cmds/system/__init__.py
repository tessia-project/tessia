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
System root group to which all commands are attached
"""

#
# IMPORTS
#
from tessia.cli.cmds.system.iface import CMDS as iface_cmds
from tessia.cli.cmds.system.model import CMDS as model_cmds
from tessia.cli.cmds.system.prof import CMDS as prof_cmds
from tessia.cli.cmds.system.system import CMDS as system_cmds
from tessia.cli.cmds.system.vol import CMDS as vol_cmds
from tessia.cli.cmds.system.wizard import CMDS as wizard_cmds

import click

#
# CONSTANTS AND DEFINITIONS
#
CMDS = (iface_cmds + model_cmds + prof_cmds + system_cmds + vol_cmds +
        wizard_cmds)

#
# CODE
#
@click.group()
def system():
    """
    manage systems and related resources
    """
    pass
# root()

# add all the subcommands
for cmd in CMDS:
    system.add_command(cmd)
