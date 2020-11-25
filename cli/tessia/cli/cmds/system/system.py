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
from tessia.cli.config import CONF
from tessia.cli.cmds.job.job import cancel as job_cancel
from tessia.cli.cmds.job.job import output as job_output
from tessia.cli.cmds.storage.vol import vol_list
from tessia.cli.cmds.system.iface import iface_list
from tessia.cli.cmds.system.prof import prof_edit, prof_list
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import PrintMode
from tessia.cli.types import CONSTANT, CustomIntRange, HOSTNAME, \
    MIB_SIZE, NAME, NAME_URL, TEXT, VERBOSITY_LEVEL
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update
from tessia.cli.utils import fetch_item
from tessia.cli.utils import submit_csv_job
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

SYSTEM_FIELDS_TABLE = (
    'name', 'hostname', 'type', 'model', 'state', 'owner', 'project'
)

CURRENT_PASSWD_PROMPT = "Current z/VM password"
NEW_PASSWD_PROMPT = "New z/VM password"

#
# CODE
#

@click.command()
@click.option('--name', '--system', required=True, type=NAME, help="system name")
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
@click.option('--name', '--system', required=True, type=NAME, help='system to delete')
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
@click.option('--bg', is_flag=True,
              help="do not wait for output after submitting")
def autoinstall(ctx, **kwargs):
    """
    install a system using an autofile template
    """
    bg_flag = kwargs.pop('bg')
    request = {'action_type': 'SUBMIT', 'job_type': 'autoinstall'}
    for key in ('profile', 'template', 'verbosity'):
        if kwargs[key] is None:
            kwargs.pop(key)
    if not kwargs['repos']:
        kwargs.pop('repos')
    request['parameters'] = json.dumps(kwargs)
    client = Client()
    job_id = wait_scheduler(client, request)
    # bg flag: do not wait for output, just return to prompt
    if bg_flag:
        return
    try:
        wait_job_exec(client, job_id)
        ctx.invoke(job_output, job_id=job_id)
    except KeyboardInterrupt:
        cancel_job = click.confirm('\nDo you want to cancel the job?')
        if not cancel_job:
            click.echo('warning: job is still running, remember to cancel it '
                       'if you want to submit a new action for this system')
            raise
        ctx.invoke(job_cancel, job_id=job_id)
# autoinstall()

@click.command(name='edit')
@click.option('cur_name', '--name', '--system', required=True, type=NAME,
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

@click.command(name='export')
@click.option('--name', '--system', type=NAME, help="filter by system name")
@click.option('hypervisor', '--hyp', type=NAME,
              help="filter by specified hypervisor")
@click.option('--model', type=CONSTANT, help="filter by specified model")
@click.option('--type', type=CONSTANT, help="filter by specified type")
@click.option('--state', type=CONSTANT, help="filter by specified state")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
def export(**kwargs):
    """
    export data in CSV format
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'name': False}

    click.echo('preparing data, this might take some time ... (specially if '
               'no filters were specified)', err=True)
    result = client.Systems.bulk(**parsed_filter)
    click.echo(result, nl=False)
# export()

@click.command(name='import')
@click.pass_context
@click.option('--commit', is_flag=True, default=False,
              help='commit changes to database (USE WITH CARE)')
@click.option('file_content', '--file', type=click.File('r'), required=True,
              help="csv file")
@click.option('--verbosity', type=VERBOSITY_LEVEL,
              help='output verbosity level')
@click.option('force', '--yes', is_flag=True, default=False,
              help='answer yes to confirmation question')
def import_(ctx, **kwargs):
    """
    submit a job for importing data in CSV format
    """
    # pass down the job commands used
    ctx.obj = {'CANCEL': job_cancel, 'OUTPUT': job_output}
    kwargs['resource_type'] = 'system'
    submit_csv_job(Client(), ctx, **kwargs)
# _import_()

@click.command(name='info')
@click.option('--system', required=True, type=NAME,
              help='system of which more info should be shown')
@click.pass_context
def info(ctx, **kwargs):
    """
    show additional system info
    """
    # list info
    click.echo('System\n------', nl=False)
    ctx.invoke(list_, name=kwargs['system'], long_info=True)
    # storage info
    click.echo('\nStorage volumes\n---------------', nl=False)
    ctx.invoke(vol_list, system=kwargs['system'])
    # profiles info
    click.echo('\nProfiles\n--------', nl=False)
    ctx.invoke(prof_list, system=kwargs['system'])
    # iface info
    click.echo('\nNetwork interfaces\n------------------', nl=False)
    ctx.invoke(iface_list, system=kwargs['system'])
# info()

@click.command(name='list')
@click.option('--name', '--system', type=NAME, help="filter by system name")
@click.option('hypervisor', '--hyp', type=NAME,
              help="filter by specified hypervisor")
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--model', type=CONSTANT, help="filter by specified model")
@click.option('--my', help="show only my own systems", is_flag=True,
              default=False)
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

    long_info = kwargs.pop('long_info')
    only_mine = kwargs.pop('my')
    if only_mine:
        kwargs.update({'owner': CONF.get_login()})
    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'name': False}
    entries = client.Systems.instances(**parsed_filter)

    # present results
    if long_info:
        print_items(SYSTEM_FIELDS, client.Systems, None, entries,
                    PrintMode.LONG)
    else:
        print_items(SYSTEM_FIELDS_TABLE, client.Systems, None, entries,
                    PrintMode.TABLE)
# list_()

@click.command(name='poweroff')
@click.pass_context
@click.option('--name', '--system', required=True, type=NAME, help="system name")
@click.option('--verbosity', type=VERBOSITY_LEVEL,
              help='output verbosity level')
@click.option('bg_flag', '--bg', is_flag=True,
              help="do not wait for output after submitting")
def poweroff(ctx, name, verbosity, bg_flag):
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
    # bg flag: do not wait for output, just return to prompt
    if bg_flag:
        return
    try:
        wait_job_exec(client, job_id)
        ctx.invoke(job_output, job_id=job_id)
    except KeyboardInterrupt:
        cancel_job = click.confirm('\nDo you want to cancel the job?')
        if not cancel_job:
            click.echo('warning: job is still running, remember to cancel it '
                       'if you want to submit a new action for this system')
            raise
        ctx.invoke(job_cancel, job_id=job_id)
# poweroff()

@click.command(name='poweron')
@click.pass_context
@click.option('--name', '--system', required=True, type=NAME, help="system name")
@click.option('--profile', type=NAME,
              help="activation profile to use, if not specified uses default")
@click.option('--cpu', type=CustomIntRange(min=1),
              help="override profile with custom cpu quantity")
@click.option(
    '--memory', type=MIB_SIZE,
    help=("override profile with custom memory size (an integer followed by "
          "one of the units KB, MB, GB, TB, KiB, MiB, GiB, TiB"))
@click.option('--force', is_flag=True,
              help="force a poweron even if system is already up")
@click.option('--noverify', is_flag=True,
              help="do not perform any system state verification")
@click.option(
    '--exclusive', is_flag=True,
    help="stop ALL other systems under same hypervisor, USE WITH CARE!")
@click.option('--verbosity', type=VERBOSITY_LEVEL,
              help='output verbosity level')
@click.option('--bg', is_flag=True,
              help="do not wait for output after submitting")
def poweron(ctx, name, **kwargs):
    """
    poweron (activate) a system
    """
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
    # bg flag: do not wait for output, just return to prompt
    if kwargs['bg']:
        return
    try:
        wait_job_exec(client, job_id)
        ctx.invoke(job_output, job_id=job_id)
    except KeyboardInterrupt:
        cancel_job = click.confirm('\nDo you want to cancel the job?')
        if not cancel_job:
            click.echo('warning: job is still running, remember to cancel it '
                       'if you want to submit a new action for this system')
            raise
        ctx.invoke(job_cancel, job_id=job_id)
# poweron()

@click.command(name='types')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
def types(**kwargs):
    """
    list the supported system types
    """
    # fetch data from server
    client = Client()

    entries = client.SystemTypes.instances()

    # present results
    if kwargs.pop('long_info'):
        print_items(TYPE_FIELDS, client.SystemTypes, None, entries,
                    PrintMode.LONG)
    else:
        print_items(TYPE_FIELDS, client.SystemTypes, None, entries,
                    PrintMode.TABLE)
# types()

@click.command(name='states')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
def states(**kwargs):
    """
    list the supported system states
    """
    # fetch data from server
    client = Client()

    entries = client.SystemStates.instances()

    # present results
    if kwargs.pop('long_info'):
        print_items(STATE_FIELDS, client.SystemStates, None, entries,
                    PrintMode.LONG)
    else:
        print_items(STATE_FIELDS, client.SystemStates, None, entries,
                    PrintMode.TABLE)
# states()

@click.command(name='zvm-pass-update')
@click.pass_context
@click.option('--name', '--system', required=True, type=NAME,
              help='system name')
@click.option('--zvm-pass-current', type=TEXT,
              help="current password for access to z/VM guest")
@click.option('--zvm-pass-new', type=TEXT,
              help="new password for access to z/VM guest")
@click.option('--update_profiles', is_flag=True,
              help="update profiles with new password")
def zvm_pass_update(ctx, name, **kwargs):
    """
    update a z/VM password on VM
    """
    client = Client()
    # make sure that system exists, it's faster than submitting a job request
    # and waiting for it to fail
    system = fetch_item(client.Systems,
                        {'name': name},
                        'system {} not found.'.format(name))
    if system.type.lower() != 'zvm':
        raise click.ClickException(
            'the command applies to z/VM guest only')

    current_passwd = kwargs.pop('zvm_pass_current')
    if not current_passwd:
        current_passwd = click.prompt(
            CURRENT_PASSWD_PROMPT, hide_input=True, type=TEXT)

    new_passwd = kwargs.pop('zvm_pass_new')
    if not new_passwd:
        new_passwd = click.prompt(
            NEW_PASSWD_PROMPT, hide_input=True, confirmation_prompt=True, type=TEXT)

    # system exists, we can submit our job request
    req_params = {'systems': [{'name': name}]}
    req_params['current_passwd'] = current_passwd
    req_params['new_passwd'] = new_passwd

    request = {
        'action_type': 'SUBMIT',
        'job_type': 'zvm_passwd',
        'parameters': json.dumps(req_params)
    }
    job_id = wait_scheduler(client, request)

    def update_profile(new_passwd):
        """Helper function to update profiles with new z/VM password"""
        for prof in client.SystemProfiles.instances(where={'system': name}):
            ctx.invoke(
                prof_edit,
                system=name,
                cur_name=prof.name,
                zvm_pass=new_passwd)
    # update_profile()

    try:
        wait_job_exec(client, job_id)
        ctx.invoke(job_output, job_id=job_id)
        if kwargs.pop('update_profiles'):
                update_profile(new_passwd)

    except KeyboardInterrupt:
        cancel_job = click.confirm('\nDo you want to cancel the job?')
        if not cancel_job:
            click.echo('warning: job is still running, remember to cancel it '
                       'if you want to submit a new action for this system')
            raise
        ctx.invoke(job_cancel, job_id=job_id)
# zvm_pass_update()

CMDS = [add, autoinstall, del_, edit, export, import_, info, list_, poweroff,
        poweron, states, types, zvm_pass_update]
