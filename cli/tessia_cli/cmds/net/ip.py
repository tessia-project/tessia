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
from tessia_cli.client import Client
from tessia_cli.filters import dict_to_filter
from tessia_cli.output import print_items
from tessia_cli.utils import fetch_and_delete
from tessia_cli.utils import fetch_and_update

import click

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'address', 'subnet', 'owner', 'project', 'modified', 'modifier', 'desc'
)

#
# CODE

@click.command(name='ip-add')
@click.option(
    '--address', required=True,
    help="subnet-name/ip-addr to create (i.e. subnet-foo/192.168.0.50)")
@click.option('--project', help="project owning ip address")
@click.option('--desc', help="free form field describing address")
def ip_add(address, **kwargs):
    """
    create a new ip address
    """
    try:
        kwargs['subnet'], kwargs['address'] = address.rsplit('/', 1)
    except:
        raise click.ClickException('invalid format for address')

    client = Client()

    item = client.IpAddresses()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# ip_add()

@click.command(name='ip-del')
@click.option(
    '--address', required=True,
    help="subnet-name/ip-addr to delete (i.e. foo/192.168.0.50)")
def ip_del(address):
    """
    remove an existing ip address
    """
    try:
        subnet, address = address.rsplit('/', 1)
    except:
        raise click.ClickException('invalid format for address')

    client = Client()

    fetch_and_delete(
        client.IpAddresses,
        {'address': address, 'subnet': subnet},
        'ip address not found.'
    )
    click.echo('Item successfully deleted.')
# ip_del()

@click.command(name='ip-edit')
@click.option(
    'cur_address', '--address', required=True,
    help="subnet-name/ip-addr to edit (i.e. foo/192.168.0.50)")
@click.option('address', '--newaddress', help="new ip-addr")
@click.option('--project', help="project owning ip address")
@click.option('--desc', help="free form field describing address")
def ip_edit(cur_address, **kwargs):
    """
    change properties of an existing ip address
    """
    try:
        subnet, address = cur_address.rsplit('/', 1)
    except:
        raise click.ClickException('invalid format for address')

    client = Client()
    fetch_and_update(
        client.IpAddresses,
        {'address': address, 'subnet': subnet},
        'ip address not found.',
        kwargs)
    click.echo('Item successfully updated.')
# ip_edit()

@click.command(name='ip-show')
@click.option('--address',
              help="show specific subnet-name/ip-addr or filter by ip-addr")
@click.option('--subnet', help="filter by specified subnet")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
def ip_show(**kwargs):
    """
    show registered ip addresses
    """
    # subnet/ip format specified: split it
    if kwargs['address'] is not None and kwargs['address'].find('/') > -1:
        # subnet dedicated parameter also specified: report conflict
        if kwargs['subnet'] is not None:
            raise click.ClickException(
                'subnet specified twice (--address and --subnet)')
        try:
            kwargs['subnet'], kwargs['address'] = \
                kwargs['address'].rsplit('/', 1)
        except:
            raise click.ClickException('invalid format for address')
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.IpAddresses.instances(**parsed_filter)

    # present results
    print_items(
        FIELDS, client.IpAddresses, None, entries)
# ip_show()

CMDS = [ip_add, ip_del, ip_edit, ip_show]
