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
from tessia_cli.types import LIBVIRT_XML
from tessia_cli.types import QETH_GROUP
from tessia_cli.utils import fetch_and_delete

import click

#
# CONSTANTS AND DEFINITIONS
#
IFACE_FIELDS = (
    'name', 'osname', 'system', 'type', 'ip_address', 'mac_address',
    'attributes', 'profiles', 'desc'
)
IFACE_TYPE_FIELDS = (
    'name', 'desc'
)
ATTR_BY_TYPE = {
    'ccwgroup': 'OSA',
    'layer2': 'OSA',
    'portname': 'OSA',
    'portno': 'OSA',
    'hostiface': 'MACVTAP',
    'libvirt': 'MACVTAP',
}

#
# CODE
#

@click.command(name='iface-add')
@click.option('--system', required=True, help="target system")
@click.option('--name', required=True, help="interface name")
@click.option('--type', required=True,
              help="interface type (see iface-types)")
@click.option('--osname', help="interface name in operating system (i.e. en0)")
@click.option('mac_address', '--mac', required=True, help="mac address")
@click.option('--subnet', help="subnet of ip address to be assigned")
@click.option('--ip', help="ip address to be assigned to interface")
@click.option('--layer2', type=click.BOOL,
              help="enable layer2 mode (OSA only)")
@click.option('--ccwgroup', help="device channels (OSA only)")
@click.option('--portno', help="port number (OSA only)")
@click.option('--portname', help="port name (OSA only)")
@click.option('--hostiface', help="host iface to bind (KVM only)")
@click.option('--libvirt', type=LIBVIRT_XML,
              help="libvirt definition file (KVM only)")
@click.option('--desc', help="free form field describing interface")
def iface_add(**kwargs):
    """
    create a new network interface
    """
    ip_addr = kwargs.pop('ip')
    subnet = kwargs.pop('subnet')
    # one of mandatory parameters not specified: report error
    if (subnet is not None and ip_addr is None or
            subnet is None and ip_addr is not None):
        raise click.ClickException(
            '--subnet and --ip must be specified together')
    # both parameters specified: set value for item creation
    elif subnet is not None and ip_addr is not None:
        kwargs['ip_address'] = '{}/{}'.format(subnet, ip_addr)

    client = Client()

    item = client.SystemIfaces()
    item.attributes = {}
    for key, value in kwargs.items():
        # option was not specified: skip it
        if value is None:
            continue

        # process attribute arg
        if key in ATTR_BY_TYPE:
            if ATTR_BY_TYPE[key] != kwargs['type']:
                raise click.ClickException(
                    'invalid attribute for this iface type')

            item.attributes[key] = value

        # normal arg: just add to the dict
        else:
            setattr(item, key, value)

    # sanity checks
    if kwargs['type'] == 'OSA':
        try:
            item.attributes['ccwgroup']
        except KeyError:
            raise click.ClickException('--ccwgroup must be specified')
    elif kwargs['type'] == 'MACVTAP':
        try:
            item.attributes['hostiface']
        except KeyError:
            try:
                item.attributes['libvirt']
            except KeyError:
                raise click.ClickException(
                    'at least one of --hostiface or --libvirt must be '
                    'specified')

    item.save()
    click.echo('Item added successfully.')
# iface_add()

@click.command(
    name='iface-attach',
    short_help='attach a network interface to a system activation profile')
@click.option('--system', required=True, help='target system')
@click.option('--profile', required=True, help='target activation profile')
@click.option('--iface', required=True, help='interface name')
def iface_attach(system, profile, iface):
    """
    attach a network interface to a system activation profile
    """
    # fetch data from server
    client = Client()

    prof_obj = fetch_item(
        client.SystemProfiles,
        {'system': system, 'name': profile},
        'no profile found.'
    )
    iface_obj = fetch_item(
        client.SystemIfaces,
        {'system': system, 'name': iface},
        'no network interface found.'
    )

    # perform operation
    prof_obj.iface_attach({'id': iface_obj.id})
    click.echo('Network interface attached successfully.')
# iface_attach()

@click.command(name='iface-del')
@click.option('--system', required=True, help="system name")
@click.option('--name', required=True, help="interface name")
def iface_del(**kwargs):
    """
    remove an existing network interface
    """
    client = Client()

    fetch_and_delete(
        client.SystemIfaces,
        kwargs,
        'network interface not found.'
    )
    click.echo('Item successfully deleted.')
# iface_del()

@click.command(
    name='iface-detach',
    short_help='detach a network interface from a system activation profile')
@click.option('--system', required=True, help='target system')
@click.option('--profile', required=True, help='target activation profile')
@click.option('--iface', required=True, help='interface name')
def iface_detach(system, profile, iface):
    """
    detach a network interface from a system activation profile
    """
    # fetch data from server
    client = Client()

    prof_obj = fetch_item(
        client.SystemProfiles,
        {'system': system, 'name': profile},
        'no profile found.'
    )
    iface_obj = fetch_item(
        client.SystemIfaces,
        {'system': system, 'name': iface},
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
@click.option('--system', required=True, help="system containing interface")
@click.option('cur_name', '--name', required=True, help="interface name")
@click.option('name', '--newname', help="new interface name")
@click.option('--type',
              help="interface type (see iface-types)")
@click.option('--osname', help="interface name in operating system (i.e. en0)")
@click.option('mac_address', '--mac', help="mac address")
@click.option('--subnet', help="subnet of ip address to be assigned")
@click.option('--ip', help="ip address to be assigned to interface")
@click.option('--layer2', type=click.BOOL,
              help="enable layer2 mode (OSA only)")
@click.option('--ccwgroup', type=QETH_GROUP,
              help="device channels (OSA only)")
@click.option('--portno', help="port number (OSA only)")
@click.option('--portname', help="port name (OSA only)")
@click.option('--hostiface', help="host iface to bind (KVM only)")
@click.option('--libvirt', type=LIBVIRT_XML,
              help="libvirt definition file (KVM only)")
@click.option('--desc', help="free form field describing interface")
def iface_edit(system, cur_name, **kwargs):
    """
    change properties of an existing network interface
    """
    client = Client()
    item = fetch_item(
        client.SystemIfaces,
        {'system': system, 'name': cur_name},
        'network interface not found.',
    )
    update_dict = {}
    if kwargs['type'] is None:
        iface_type = item.type
    else:
        iface_type = kwargs['type']

    ip_addr = kwargs.pop('ip')
    subnet = kwargs.pop('subnet')
    # one of mandatory parameters not specified: report error
    if (subnet is not None and ip_addr is None or
            subnet is None and ip_addr is not None):
        raise click.ClickException(
            '--subnet and --ip must be specified together')
    # both parameters specified: set value for update on item
    elif subnet is not None and ip_addr is not None:
        # both parameters are empty: unassign ip address
        if subnet == '' and ip_addr == '':
            update_dict['ip_address'] = None
        else:
            update_dict['ip_address'] = '{}/{}'.format(subnet, ip_addr)

    for key, value in kwargs.items():

        # option was not specified: skip it
        if value is None:
            continue

        # process attribute arg
        if key in ATTR_BY_TYPE:
            if ATTR_BY_TYPE[key] != iface_type:
                raise click.ClickException(
                    'invalid attribute for this iface type')

            update_dict.setdefault('attributes', item.attributes)

            # allow unsetting parameters
            if value == '' and key in update_dict['attributes']:
                update_dict['attributes'].pop(key)
            else:
                update_dict['attributes'][key] = value

        # normal arg: just add to the dict
        else:
            update_dict[key] = value

    if len(update_dict) == 0:
        raise click.ClickException('no update criteria provided.')

    # attributes changed: perform sanity checks
    if 'attributes' in update_dict:
        if iface_type == 'OSA':
            try:
                update_dict['attributes']['ccwgroup']
            except KeyError:
                raise click.ClickException('--ccwgroup must be present')
        elif iface_type == 'MACVTAP':
            try:
                update_dict['attributes']['hostiface']
            except KeyError:
                try:
                    update_dict['attributes']['libvirt']
                except KeyError:
                    raise click.ClickException(
                        'at least one of --hostiface or --libvirt must be '
                        'present')

    item.update(**update_dict)
    click.echo('Item successfully updated.')
# iface_edit()

@click.command(name='iface-list')
@click.option('--system', help='the system to list')
@click.option('--name', help="filter by interface name")
@click.option('--type',
              help="filter by specified interface type")
@click.option('--osname', help="filter by specified operating system name")
@click.option('mac_address', '--mac',
              help="filter by specified mac address")
@click.option('ip_address', '--ip',
              help="filter by specified ip address")
def iface_list(**kwargs):
    """
    list the network interfaces of a system
    """
    # at least one qualifier must be specified so that we don't have to
    # retrieve the full list
    if kwargs['system'] is None and kwargs['name'] is None:
        raise click.ClickException(
            'at least one of --system or --name must be specified')

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

# iface_list()

@click.command(name='iface-types')
def iface_types():
    """
    list the supported network interface types
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
    iface_add, iface_attach, iface_del, iface_edit, iface_detach, iface_list,
    iface_types
]
