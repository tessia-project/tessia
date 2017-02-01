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
Module for the system commands
"""

#
# IMPORTS
#
from tessia_cli.client import Client
from tessia_cli.cmds.job.job import output
from tessia_cli.filters import dict_to_filter
from tessia_cli.output import print_items
from tessia_cli.utils import fetch_and_delete
from tessia_cli.utils import fetch_and_update
from tessia_cli.utils import wait_scheduler

import click
import json

#
# CONSTANTS AND DEFINITIONS
#
TYPE_FIELDS = (
    'name', 'arch', 'desc'
)
STATE_FIELDS = (
    'name', 'desc'
)
SYSTEM_FIELDS = (
    'name', 'hostname', 'hypervisor', 'type', 'model', 'state', 'owner',
    'project', 'modified', 'modifier', 'desc'
)

#
# CODE
#

@click.command()
@click.option('--name', required=True, help="system name")
@click.option(
    '--hostname', required=True, help="resolvable hostname or ip address")
@click.option('hypervisor', '--hyp', help="system's hypervisor")
@click.option('--type', required=True, help="system type (see types)")
@click.option('--model', help="system model (see model-show)")
@click.option('--state', help="system state (see states)")
@click.option('--project', help="project owning system")
@click.option('--desc', help="free form field describing system")
def add(**kwargs):
    """
    create a new system
    """
    client = Client()

    item = client.Systems()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# add()

@click.command(name='del')
@click.option('--name', required=True, help='system to delete')
def del_(name):
    """
    remove an existing system
    """
    client = Client()

    fetch_and_delete(
        client.Systems,
        {'name': name},
        'system not found.'
    )
    click.echo('Item successfully deleted.')
# del_()

@click.command(name='autoinstall')
@click.pass_context
@click.option('--template', required=True, help='autofile template')
@click.option('profile', '--system', required=True,
              help='system-name or system-name/profile-name')
def autoinstall(ctx=None, **kwargs):
    """
    install a system using an autofile template
    """
    request = {'action_type': 'SUBMIT', 'job_type': 'autoinstall'}
    request['parameters'] = json.dumps(kwargs)
    job_id = wait_scheduler(Client(), request)
    click.echo('Waiting for installation output (Ctrl+C to stop waiting)')
    ctx.invoke(output, job_id=job_id)
# install()

@click.command(name='edit')
@click.option('cur_name', '--name', required=True, help='system to edit')
@click.option('name', '--newname', help="new system name")
@click.option('hypervisor', '--hyp', help="hypervisor's name")
@click.option('--model', help="system model (see model-show)")
@click.option('--type', help="system type (see types)")
@click.option('--state', help="system state (see states)")
@click.option('--project', help="project owning system ")
@click.option('--desc', help="free form field describing system")
def edit(cur_name, **kwargs):
    """
    edit an existing system
    """
    client = Client()

    fetch_and_update(
        client.Systems,
        {'name': cur_name},
        'system not found.',
        kwargs)
    click.echo('Item successfully updated.')
# edit()

@click.command(name='show')
@click.option('--name', help="show specified system only")
@click.option('hypervisor', '--hyp', help="filter by specified hypervisor")
@click.option('--model', help="filter by specified model")
@click.option('--type', help="filter by specified type")
@click.option('--state', help="filter by specified state")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
def show(**kwargs):
    """
    show registered systems
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.Systems.instances(**parsed_filter)

    # present results
    print_items(
        SYSTEM_FIELDS, client.Systems, None, entries)
# show()

@click.command(name='types')
def types():
    """
    show the supported system types
    """
    # fetch data from server
    client = Client()

    entries = client.SystemTypes.instances()

    # present results
    print_items(
        TYPE_FIELDS, client.SystemTypes, None, entries)
# types()

@click.command(name='states')
def states():
    """
    show the supported system states
    """
    # fetch data from server
    client = Client()

    entries = client.SystemStates.instances()

    # present results
    print_items(
        STATE_FIELDS, client.SystemStates, None, entries)
# states()

CMDS = [add, del_, edit, autoinstall, show, types, states]
