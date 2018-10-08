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
from tessia.cli.client import Client
from tessia.cli.cmds.job.job import cancel, output
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.types import CONSTANT, CustomIntRange, HOSTNAME, \
    VERBOSITY_LEVEL, NAME, NAME_URL
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update
from tessia.cli.utils import fetch_item
from tessia.cli.utils import str_to_size
from tessia.cli.utils import wait_scheduler, wait_job_exec

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
@click.option('--name', required=True, type=NAME, help="system name")
@click.option('--hostname', required=True, type=HOSTNAME,
              help="resolvable hostname or ip address")
@click.option('hypervisor', '--hyp', type=NAME, help="system's hypervisor")
@click.option('--type', required=True, type=CONSTANT,
              help="system type (see types)")
@click.option('--model', type=CONSTANT, help="system model (see model-list)")
@click.option('--state', type=CONSTANT, help="system state (see states)")
@click.option('--owner', help="owner login")
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
@click.option('--name', required=True, type=NAME, help='system to delete')
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
@click.option('--os', required=True, help='operating system to install')
@click.option('--template', help='custom autotemplate')
@click.option('--system', required=True, type=NAME,
              help='system to be installed')
@click.option('--profile', type=NAME,
              help='activation profile; if not specified default is used')
@click.option('repos', '--repo', multiple=True, type=NAME_URL,
              help='package repository to configure in installed system '
                   'or install repository to use for installation')
@click.option('--verbosity', type=VERBOSITY_LEVEL,
              help='output verbosity level')
def autoinstall(ctx, **kwargs):
    """
    install a system using an autofile template
    """
    request = {'action_type': 'SUBMIT', 'job_type': 'autoinstall'}
    for key in ('profile', 'template', 'verbosity'):
        if kwargs[key] is None:
            kwargs.pop(key)
    if not kwargs['repos']:
        kwargs.pop('repos')
    request['parameters'] = json.dumps(kwargs)
    client = Client()
    job_id = wait_scheduler(client, request)
    try:
        wait_job_exec(client, job_id)
        ctx.invoke(output, job_id=job_id)
    except KeyboardInterrupt:
        cancel_job = click.confirm('\nDo you want to cancel the job?')
        if not cancel_job:
            click.echo('warning: job is still running, remember to cancel it '
                       'if you want to submit a new action for this system')
            raise
        ctx.invoke(cancel, job_id=job_id)
# autoinstall()

@click.command(name='edit')
@click.option('cur_name', '--name', required=True, type=NAME,
              help='system to edit')
@click.option('name', '--newname', type=NAME, help="new system name")
@click.option('hypervisor', '--hyp', type=NAME, help="hypervisor's name")
@click.option('--hostname', type=HOSTNAME,
              help="resolvable hostname or ip address")
@click.option('--model', type=CONSTANT, help="system model (see model-list)")
@click.option('--type', type=CONSTANT, help="system type (see types)")
@click.option('--state', type=CONSTANT, help="system state (see states)")
@click.option('--owner', help="owner login")
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

@click.command(name='list')
@click.option('--name', type=NAME, help="filter by system name")
@click.option('hypervisor', '--hyp', type=NAME,
              help="filter by specified hypervisor")
@click.option('--model', type=CONSTANT, help="filter by specified model")
@click.option('--type', type=CONSTANT, help="filter by specified type")
@click.option('--state', type=CONSTANT, help="filter by specified state")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
def list_(**kwargs):
    """
    list registered systems
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.Systems.instances(**parsed_filter)

    # present results
    print_items(
        SYSTEM_FIELDS, client.Systems, None, entries)
# list_()

@click.command(name='poweroff')
@click.pass_context
@click.option('--name', required=True, type=NAME, help="system name")
@click.option('--verbosity', type=VERBOSITY_LEVEL,
              help='output verbosity level')
def poweroff(ctx, name, verbosity):
    """
    poweroff (deactivate) a system
    """
    client = Client()
    # make sure that system exists, it's faster than submitting a job request
    # and waiting for it to fail
    fetch_item(client.Systems, {'name': name},
               'system {} not found.'.format(name))

    # system exists, therefore we can submit our job request
    req_params = {'systems': [{'action': 'poweroff', 'name': name}]}
    if verbosity:
        req_params['verbosity'] = verbosity
    request = {
        'action_type': 'SUBMIT',
        'job_type': 'powerman',
        'parameters': json.dumps(req_params)
    }

    job_id = wait_scheduler(client, request)
    try:
        wait_job_exec(client, job_id)
        ctx.invoke(output, job_id=job_id)
    except KeyboardInterrupt:
        cancel_job = click.confirm('\nDo you want to cancel the job?')
        if not cancel_job:
            click.echo('warning: job is still running, remember to cancel it '
                       'if you want to submit a new action for this system')
            raise
        ctx.invoke(cancel, job_id=job_id)
# poweroff()

@click.command(name='poweron')
@click.pass_context
@click.option('--name', required=True, type=NAME, help="system name")
@click.option('--profile', type=NAME,
              help="activation profile to use, if not specified uses default")
@click.option('--cpu', type=CustomIntRange(min=1),
              help="override profile with custom cpu quantity")
@click.option('--memory',
              help="override profile with custom memory size (i.e. 1gib)")
@click.option('--force', is_flag=True,
              help="force a poweron even if system is already up")
@click.option('--noverify', is_flag=True,
              help="do not any perform system state verification")
@click.option(
    '--exclusive', is_flag=True,
    help="stop ALL other systems under same hypervisor, USE WITH CARE!")
@click.option('--verbosity', type=VERBOSITY_LEVEL,
              help='output verbosity level')
def poweron(ctx, name, **kwargs):
    """
    poweron (activate) a system
    """
    # convert a human size to integer
    try:
        kwargs['memory'] = str_to_size(kwargs['memory'])
    except ValueError:
        raise click.ClickException('invalid memory size specified.')

    client = Client()
    # make sure that system exists, it's faster than submitting a job request
    # and waiting for it to fail
    fetch_item(client.Systems, {'name': name},
               'system {} not found.'.format(name))

    req_params = {'systems': [
        {'action': 'poweron', 'name': name, 'profile_override': {}}
    ]}
    # profile specified: like system, make sure it exists first
    if kwargs['profile']:
        fetch_item(
            client.SystemProfiles, {'system': name, 'name': kwargs['profile']},
            'profile {} not found.'.format(kwargs['profile']))
        # add profile name to request
        req_params['systems'][0]['profile'] = kwargs['profile']

    if kwargs['noverify']:
        req_params['verify'] = False
    if kwargs['exclusive']:
        req_params['systems'][0]['action'] = 'poweron-exclusive'
    if kwargs['force']:
        req_params['systems'][0]['force'] = True
    if kwargs['cpu']:
        req_params['systems'][0]['profile_override']['cpu'] = kwargs['cpu']
    if kwargs['memory']:
        req_params['systems'][0]['profile_override']['memory'] = (
            kwargs['memory'])
    if kwargs['verbosity']:
        req_params['verbosity'] = kwargs['verbosity']

    # system exists, we can submit our job request
    request = {
        'action_type': 'SUBMIT',
        'job_type': 'powerman',
        'parameters': json.dumps(req_params)
    }
    job_id = wait_scheduler(client, request)
    try:
        wait_job_exec(client, job_id)
        ctx.invoke(output, job_id=job_id)
    except KeyboardInterrupt:
        cancel_job = click.confirm('\nDo you want to cancel the job?')
        if not cancel_job:
            click.echo('warning: job is still running, remember to cancel it '
                       'if you want to submit a new action for this system')
            raise
        ctx.invoke(cancel, job_id=job_id)
# poweron()

@click.command(name='types')
def types():
    """
    list the supported system types
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
    list the supported system states
    """
    # fetch data from server
    client = Client()

    entries = client.SystemStates.instances()

    # present results
    print_items(
        STATE_FIELDS, client.SystemStates, None, entries)
# states()

CMDS = [add, del_, edit, autoinstall, list_, poweroff, poweron, types, states]
