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
Module for the prof (system activation profiles) commands
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.types import CustomIntRange
from tessia.cli.types import LOGIN
from tessia.cli.types import NAME
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update
from tessia.cli.utils import str_to_size
from tessia.cli.utils import size_to_str

import click

#
# CONSTANTS AND DEFINITIONS
#
PROFILE_FIELDS = (
    'name', 'system', 'hypervisor_profile', 'operating_system', 'default',
    'cpu', 'memory', 'parameters', 'credentials', 'storage_volumes',
    'system_ifaces', 'gateway'
)

#
# CODE
#

@click.command(name='prof-add')
@click.option('--system', required=True, type=NAME, help='target system')
@click.option('--name', required=True, type=NAME, help="profile name")
@click.option('--cpu', default=1, type=CustomIntRange(min=1),
              help="number of cpus")
@click.option('--memory', default='1gb', help="memory size (i.e. 1gb)")
@click.option('--default', is_flag=True, help="set as default for system")
@click.option('hypervisor_profile', '--hyp', type=NAME,
              help="hypervisor profile required for activation")
@click.option('--login', required=True, type=LOGIN,
              help="user:passwd for admin access to operating system")
def prof_add(**kwargs):
    """
    create a new system activation profile
    """
    client = Client()

    # convert a human size to integer
    try:
        kwargs['memory'] = str_to_size(kwargs['memory'])
    except ValueError:
        raise click.ClickException('invalid memory size specified.')
    # avoid user confusion
    if (kwargs['hypervisor_profile'] is not None and
            kwargs['hypervisor_profile'].find('/') > -1):
        raise click.ClickException(
            'invalid format for hypervisor profile, specify profile name only')

    # login provided: parse it to json format expected by API
    login = kwargs.pop('login')
    try:
        user, passwd = login.split(':', 1)
    except (AttributeError, ValueError):
        raise click.ClickException('invalid format specified for login')
    kwargs['credentials'] = {'user': user, 'passwd': passwd}

    item = client.SystemProfiles()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# prof_add()

@click.command(name='prof-del')
@click.option('--system', required=True, type=NAME, help='system name')
@click.option('--name', required=True, type=NAME,
              help="profile name to delete")
def prof_del(**kwargs):
    """
    remove an existing system activation profile
    """
    client = Client()

    fetch_and_delete(
        client.SystemProfiles,
        kwargs,
        'system profile not found.'
    )
    click.echo('Item successfully deleted.')
# prof_del()

@click.command(name='prof-edit')
@click.option('--system', required=True, type=NAME, help='system name')
@click.option('cur_name', '--name', required=True, type=NAME,
              help="profile name")
@click.option('name', '--newname', type=NAME,
              help="new name (i.e. new-profile-name)")
@click.option('--cpu', type=CustomIntRange(min=1), help="number of cpus")
@click.option('--memory', help="memory size (i.e. 1gb)")
@click.option('--default', is_flag=True, help="set as default for system")
@click.option('--gateway', help='name of interface to use as gateway')
@click.option('hypervisor_profile', '--hyp', type=NAME,
              help="hypervisor profile required for activation")
@click.option('--login', type=LOGIN,
              help="user:passwd for admin access to operating system")
def prof_edit(system, cur_name, **kwargs):
    """
    change properties of an existing system activation profile
    """
    # convert a human size to integer
    try:
        kwargs['memory'] = str_to_size(kwargs['memory'])
    except ValueError:
        raise click.ClickException('invalid memory size specified.')
    # avoid user confusion
    if (kwargs['hypervisor_profile'] is not None and
            kwargs['hypervisor_profile'].find('/') > -1):
        raise click.ClickException(
            'invalid format for hypervisor profile, specify profile name only')

    # login provided: parse it to json format expected by API
    login = kwargs.pop('login')
    if login is not None:
        try:
            user, passwd = login.split(':', 1)
        except (AttributeError, ValueError):
            raise click.ClickException('invalid format specified for login')
        kwargs['credentials'] = {'user': user, 'passwd': passwd}
    # default not provided: remove from dict otherwise it will force setting to
    # false
    if kwargs['default'] is False:
        kwargs.pop('default')

    client = Client()
    fetch_and_update(
        client.SystemProfiles,
        {'system': system, 'name': cur_name},
        'system profile not found.',
        kwargs)
    click.echo('Item successfully updated.')
# prof_edit()

@click.command(name='prof-list')
@click.option('--system', required=True, type=NAME, help="the system to list")
@click.option('--name', type=NAME, help="filter by profile-name")
@click.option('--cpu', type=CustomIntRange(min=1),
              help="filter by specified number of cpus")
@click.option('--memory', help="filter by specified memory size (i.e. 1gb)")
@click.option('--default', is_flag=True, help="list only default profiles")
@click.option('hypervisor_profile', '--hyp', type=NAME,
              help="filter by required hypervisor profile")
def prof_list(**kwargs):
    """
    list the activation profiles of a system
    """
    # convert a human size to integer
    try:
        kwargs['memory'] = str_to_size(kwargs['memory'])
    except ValueError:
        raise click.ClickException('invalid memory size specified.')

    # default not provided: remove from dict otherwise it will force listing
    # only non defaults
    if kwargs['default'] is False:
        kwargs.pop('default')

    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.SystemProfiles.instances(**parsed_filter)

    def parse_ifaces(ifaces):
        """Helper function to format output from ifaces list"""
        parsed_ifaces = []
        for iface in ifaces:
            if iface.ip_address is not None:
                ip_address = iface.ip_address.rsplit('/', 1)[-1]
                parsed_ifaces.append('[{}/{}]'.format(iface.name, ip_address))
            else:
                parsed_ifaces.append('[{}]'.format(iface.name))

        return ', '.join(parsed_ifaces)
    # parse_ifaces()

    parser_map = {
        'memory': size_to_str,
        'storage_volumes': lambda vols: ', '.join(
            ['[{}/{}]'.format(vol.server, vol.volume_id) for vol in vols]),
        'system_ifaces': parse_ifaces,
    }

    # present results
    print_items(
        PROFILE_FIELDS, client.SystemProfiles, parser_map, entries)

# prof_list()

CMDS = [prof_add, prof_del, prof_edit, prof_list]