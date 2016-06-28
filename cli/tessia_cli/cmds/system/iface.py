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
Module for the iface (network interfaces) commands
"""

#
# IMPORTS
#
from tessia_cli.client import Client
from tessia_cli.filters import dict_to_filter
from tessia_cli.utils import fetch_item
from tessia_cli.output import print_items
from tessia_cli.utils import fetch_and_delete
from tessia_cli.utils import fetch_and_update

import click

#
# CONSTANTS AND DEFINITIONS
#
IFACE_FIELDS = (
    'name', 'osname', 'system', 'type', 'ip_address', 'mac_address',
    'attributes', 'desc', 'profiles'
)
IFACE_TYPE_FIELDS = (
    'name', 'desc'
)

#
# CODE
#

@click.command(name='iface-add')
@click.option('--name', required=True,
              help="interface name in form system-name/iface-name")
@click.option('--type', required=True,
              help="interface type (see iface-types)")
@click.option('--osname', help="interface name in operating system (i.e. en0)")
@click.option('mac_address', '--mac',
              help="mac address, leave blank to auto generate")
@click.option('ip_address', '--ip',
              help="assign subnet-name/ip-addr to interface")
@click.option('--attributes', help="custom attributes (future use)")
@click.option('--desc', help="free form field describing interface")
def iface_add(**kwargs):
    """
    create a new network interface
    """
    try:
        kwargs['system'], kwargs['name'] = kwargs['name'].split('/', 1)
    except:
        raise click.ClickException('invalid format for name')

    client = Client()

    item = client.SystemIfaces()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# iface_add()

@click.command(
    name='iface-attach',
    short_help='attach a network interface to a system activation profile')
@click.option(
    'target', '--to', required=True,
    help="target profile system-name/profile-name")
@click.option('--iface', required=True, help='iface-name')
def iface_attach(target, iface):
    """
    attach a network interface to a system activation profile
    """
    try:
        system_name, profile_name = target.split('/', 1)
    except:
        raise click.ClickException('invalid format for profile')

    # fetch data from server
    client = Client()

    prof_obj = fetch_item(
        client.SystemProfiles,
        {'system': system_name, 'name': profile_name},
        'no profile found.'
    )
    iface_obj = fetch_item(
        client.SystemIfaces,
        {'system': system_name, 'name': iface},
        'no network interface found.'
    )

    # perform operation
    prof_obj.iface_attach({'id': iface_obj.id})
    click.echo('Network interface attached successfully.')
# iface_attach()

@click.command(name='iface-del')
@click.option('--name', required=True,
              help="interface name in form system-name/iface-name")
def iface_del(name):
    """
    remove an existing network interface
    """
    try:
        system_name, iface_name = name.split('/', 1)
    except:
        raise click.ClickException('invalid format for name')

    client = Client()

    fetch_and_delete(
        client.SystemIfaces,
        {'system': system_name, 'name': iface_name},
        'network interface not found.'
    )
    click.echo('Item successfully deleted.')
# iface_del()

@click.command(
    name='iface-detach',
    short_help='detach a network interface from a system activation profile')
@click.option(
    'profile', '--from', required=True,
    help="from profile system-name/profile-name")
@click.option('--iface', required=True, help='iface-name')
def iface_detach(profile, iface):
    """
    detach a network interface from a system activation profile
    """
    try:
        system_name, profile_name = profile.split('/', 1)
    except:
        raise click.ClickException('invalid format for profile')

    # fetch data from server
    client = Client()

    prof_obj = fetch_item(
        client.SystemProfiles,
        {'system': system_name, 'name': profile_name},
        'no profile found.'
    )
    iface_obj = fetch_item(
        client.SystemIfaces,
        {'system': system_name, 'name': iface},
        'no network interface found.'
    )

    # since the lib does not support to pass the unique id on the url for a
    # instance we need to use the class method directly
    client.SystemProfiles.iface_detach(
        iface_id=iface_obj.id, id=prof_obj.id)
    click.echo('Network interface detached successfully.')
# iface_detach()

@click.command(
    name='iface-edit',
    short_help='change properties of an existing network interface')
@click.option('cur_name', '--name', required=True,
              help="interface name in form system-name/iface-name")
@click.option('name', '--newname', help="new interface name iface-name")
@click.option('--type',
              help="interface type (see iface-types)")
@click.option('--osname', help="interface name in operating system (i.e. en0)")
@click.option('mac_address', '--mac',
              help="mac address, leave blank to auto generate")
@click.option('ip_address', '--ip',
              help="assign subnet-name/ip-addr to interface")
@click.option('--attributes', help="custom attributes (future use)")
@click.option('--desc', help="free form field describing interface")
def iface_edit(cur_name, **kwargs):
    """
    change properties of an existing network interface
    """
    try:
        system_name, cur_name = cur_name.split('/', 1)
    except:
        raise click.ClickException('invalid format for name')

    client = Client()
    fetch_and_update(
        client.SystemIfaces,
        {'system': system_name, 'name': cur_name},
        'network interface not found.',
        kwargs)
    click.echo('Item successfully updated.')
# iface_edit()

@click.command(name='iface-show')
@click.option(
    '--name',
    help="show specific system-name/iface-name or filter by iface-name")
@click.option('--system', help='filter by specified system')
@click.option('--type',
              help="filter by specified interface type")
@click.option('--osname', help="filter by specified operating system name")
@click.option('mac_address', '--mac',
              help="filter by specified mac address")
@click.option('ip_address', '--ip',
              help="filter by specified ip address")
def iface_show(**kwargs):
    """
    show existing system activation profiles
    """
    # system-name/iface-name format specified: split it
    if kwargs['name'] is not None and kwargs['name'].find('/') > -1:
        # system dedicated parameter also specified: report conflict
        if kwargs['system'] is not None:
            raise click.ClickException(
                'system specified twice (--name and --system)')
        try:
            kwargs['system'], kwargs['name'] = kwargs['name'].split('/', 1)
        except:
            raise click.ClickException('invalid format for interface name')

    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.SystemIfaces.instances(**parsed_filter)

    # present results
    print_items(
        IFACE_FIELDS,
        client.SystemIfaces,
        {'profiles': lambda prof_list: ', '.join(
            ['[{}]'.format(prof.name) for prof in prof_list])
        },
        entries)

# iface_show()

@click.command(name='iface-types')
def iface_types():
    """
    show the supported storage server types
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    entries = client.IfaceTypes.instances()

    # present results
    print_items(
        IFACE_TYPE_FIELDS, client.IfaceTypes, None, entries)
# iface_types()

CMDS = [
    iface_add, iface_attach, iface_del, iface_edit, iface_detach, iface_show,
    iface_types
]
