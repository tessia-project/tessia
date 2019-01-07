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
Module for the ip (ip addresses) command
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.filters import dict_to_filter
from tessia.cli.types import IPADDRESS
from tessia.cli.types import SUBNET
from tessia.cli.output import print_items
from tessia.cli.output import PrintMode
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update

import click

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'address', 'subnet', 'owner', 'project', 'modified', 'modifier', 'desc',
    'system'
)

FIELDS_TABLE = (
    'address', 'subnet', 'system', 'owner', 'project', 'desc'
)

#
# CODE

@click.command(name='ip-add')
@click.option('--subnet', required=True, type=SUBNET, help='target subnet')
@click.option('address', '--ip', required=True, type=IPADDRESS,
              help="ip address to create (i.e. 192.168.0.50)")
@click.option('--owner', help="owner login")
@click.option('--project', help="project owning ip address")
@click.option('--desc', help="free form field describing address")
def ip_add(**kwargs):
    """
    create a new ip address
    """
    client = Client()

    item = client.IpAddresses()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# ip_add()

@click.command(name='ip-del')
@click.option('--subnet', required=True, type=SUBNET,
              help='subnet containing ip')
@click.option('address', '--ip', required=True, type=IPADDRESS,
              help="ip address to delete")
def ip_del(**kwargs):
    """
    remove an existing ip address
    """
    client = Client()

    fetch_and_delete(
        client.IpAddresses,
        kwargs,
        'ip address not found.'
    )
    click.echo('Item successfully deleted.')
# ip_del()

@click.command(name='ip-edit')
@click.option('--subnet', required=True, type=SUBNET,
              help='subnet containing ip')
@click.option('cur_address', '--ip', required=True, type=IPADDRESS,
              help="ip address to edit")
@click.option('address', '--newip', type=IPADDRESS, help="new ip-addr")
@click.option('--owner', help="owner login")
@click.option('--project', help="project owning ip address")
@click.option('--desc', help="free form field describing address")
def ip_edit(subnet, cur_address, **kwargs):
    """
    change properties of an existing ip address
    """
    client = Client()
    fetch_and_update(
        client.IpAddresses,
        {'address': cur_address, 'subnet': subnet},
        'ip address not found.',
        kwargs)
    click.echo('Item successfully updated.')
# ip_edit()

@click.command(name='ip-list')
@click.option('address', '--ip', type=IPADDRESS,
              help='filter by ip address')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
@click.option('--subnet', type=SUBNET, help='the subnet to list')
def ip_list(**kwargs):
    """
    list the registered ip addresses
    """
    # at least one qualifier must be specified so that we don't have to
    # retrieve the full list
    if kwargs['subnet'] is None and kwargs['address'] is None:
        raise click.ClickException(
            'at least one of --subnet or --ip must be specified')

    # fetch data from server
    client = Client()

    long_info = kwargs.pop('long_info')
    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'address': False}
    entries = client.IpAddresses.instances(**parsed_filter)

    # present results
    if long_info:
        print_items(FIELDS, client.IpAddresses, None, entries, PrintMode.LONG)
    else:
        print_items(FIELDS_TABLE, client.IpAddresses, None, entries,
                    PrintMode.TABLE)
# ip_list()

CMDS = [ip_add, ip_del, ip_edit, ip_list]
