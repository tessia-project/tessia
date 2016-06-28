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
from tessia_cli.client import Client
from tessia_cli.filters import dict_to_filter
from tessia_cli.output import print_items
from tessia_cli.utils import fetch_and_delete
from tessia_cli.utils import fetch_and_update
from tessia_cli.utils import str_to_size
from tessia_cli.utils import size_to_str

import click

#
# CONSTANTS AND DEFINITIONS
#
PROFILE_FIELDS = (
    'name', 'system', 'hypervisor_profile', 'operating_system', 'default',
    'cpu', 'memory', 'parameters', 'credentials', 'storage_volumes',
    'system_ifaces'
)

#
# CODE
#

@click.command(name='prof-add')
@click.option('--name', required=True,
              help="profile name in form system-name/profile-name")
@click.option('--cpu', default=1, type=click.IntRange(min=1),
              help="number of cpus")
@click.option('--memory', default='1gb', help="memory size (i.e. 1gb)")
@click.option('--default', is_flag=True, help="make it the default profile")
@click.option('hypervisor_profile', '--require',
              help="hypervisor profile required for activation")
@click.option('parameters', '--params',
              help="activation parameters (future use)")
@click.option('--login',
              help="user:passwd for admin access to operating system")
def prof_add(**kwargs):
    """
    create a new system activation profile
    """
    client = Client()

    try:
        kwargs['system'], kwargs['name'] = kwargs['name'].split('/', 1)
    except:
        raise click.ClickException('invalid format for name')
    # convert a human size to integer
    try:
        kwargs['memory'] = str_to_size(kwargs['memory'])
    except ValueError:
        raise click.ClickException('invalid memory size specified.')

    # login provided: parse it to json format expected by API
    if kwargs['login'] is not None:
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
@click.option('--name', required=True,
              help="system-name/profile-name to delete")
def prof_del(name):
    """
    remove an existing system activation profile
    """
    try:
        system_name, prof_name = name.split('/', 1)
    except:
        raise click.ClickException('invalid format for name')

    client = Client()

    fetch_and_delete(
        client.SystemProfiles,
        {'system': system_name, 'name': prof_name},
        'system profile not found.'
    )
    click.echo('Item successfully deleted.')
# prof_del()

@click.command(name='prof-edit')
@click.option('cur_name', '--name', required=True,
              help="profile name in the form system-name/profile-name")
@click.option('name', '--newname', help="new name (i.e. new-profile-name)")
@click.option('--cpu', type=click.IntRange(min=1), help="number of cpus")
@click.option('--memory', help="memory size (i.e. 1gb)")
@click.option('--default', is_flag=True, help="make it the default profile")
@click.option('hypervisor_profile', '--require',
              help="hypervisor profile required for activation")
@click.option('parameters', '--params',
              help="activation parameters (future use)")
@click.option('--login',
              help="user:passwd for admin access to operating system")
def prof_edit(cur_name, **kwargs):
    """
    change properties of an existing system activation profile
    """
    try:
        system_name, cur_name = cur_name.split('/', 1)
    except:
        raise click.ClickException('invalid format for name')
    # convert a human size to integer
    try:
        kwargs['memory'] = str_to_size(kwargs['memory'])
    except ValueError:
        raise click.ClickException('invalid memory size specified.')

    # login provided: parse it to json format expected by API
    if kwargs['login'] is not None:
        login = kwargs.pop('login')
        try:
            user, passwd = login.split(':', 1)
        except (AttributeError, ValueError):
            raise click.ClickException('invalid format specified for login')
        kwargs['credentials'] = {'user': user, 'passwd': passwd}

    client = Client()
    fetch_and_update(
        client.SystemProfiles,
        {'system': system_name, 'name': cur_name},
        'system profile not found.',
        kwargs)
    click.echo('Item successfully updated.')
# prof_edit()

@click.command(name='prof-show')
@click.option(
    '--name',
    help="show specific system-name/profile-name or filter by profile-name")
@click.option('--system',
              help="filter by specified system")
@click.option('--cpu', help="filter by specified number of cpus")
@click.option('--memory', help="filter by specified memory size (i.e. 1gb)")
@click.option('--default', type=click.BOOL, help="show default profiles")
@click.option('hypervisor_profile', '--require',
              help="filter by required hypervisor profile")
def prof_show(**kwargs):
    """
    show existing system activation profiles
    """
    # system-name/profile-name format specified: split it
    if kwargs['name'] is not None and kwargs['name'].find('/') > -1:
        # system dedicated parameter also specified: report conflict
        if kwargs['system'] is not None:
            raise click.ClickException(
                'system specified twice (--name and --system)')
        try:
            kwargs['system'], kwargs['name'] = kwargs['name'].split('/', 1)
        except:
            raise click.ClickException('invalid format for profile name')

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

# prof_show()

CMDS = [prof_add, prof_del, prof_edit, prof_show]
