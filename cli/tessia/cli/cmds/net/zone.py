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
Module for the zone (network zones) command
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.config import CONF
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import PrintMode
from tessia.cli.types import NAME
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update

import click

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'name', 'owner', 'project', 'modified', 'modifier', 'desc'
)

FIELDS_TABLE = (
    'name', 'owner', 'project', 'desc'
)

#
# CODE

@click.command(name='zone-add')
# set the parameter name after the model's attribute name to save on typing
@click.option('--name', '--zone', required=True, type=NAME,
              help="name of network zone")
@click.option('--owner', help="owner login")
@click.option('--project', help="project owning zone")
@click.option('--desc', help="free form field describing zone")
def zone_add(**kwargs):
    """
    create a new network zone
    """
    client = Client()

    item = client.NetZones()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# zone_add()

@click.command(name='zone-del')
@click.option('--name', '--zone', required=True, type=NAME,
              help="name of network zone")
def zone_del(name):
    """
    remove an existing network zone
    """
    client = Client()

    fetch_and_delete(
        client.NetZones, {'name': name}, 'network zone not found.')
    click.echo('Item successfully deleted.')
# del_net_zone()

# short help is needed to avoid truncation
@click.command(
    name='zone-edit',
    short_help="change properties of an existing network zone")
@click.option('cur_name', '--name', '--zone', required=True,
              help="name of network zone")
# set the parameter name after the model's attribute name to save on typing
@click.option('name', '--newname', type=NAME,
              help="new name of network zone")
@click.option('--owner', help="owner login")
@click.option('--project', help="project owning zone")
@click.option('--desc', help="free form field describing zone")
def zone_edit(cur_name, **kwargs):
    """
    change properties of an existing network zone
    """
    client = Client()
    fetch_and_update(
        client.NetZones,
        {'name': cur_name},
        'network zone not found.',
        kwargs)
    click.echo('Item successfully updated.')
# zone_edit()

@click.command(name='zone-list')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--my', help="show only my own zones", is_flag=True,
              default=False)
@click.option('--name', '--zone', type=NAME, help="filter by zone name")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
def zone_list(**kwargs):
    """
    list the registered network zones
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
    entries = client.NetZones.instances(**parsed_filter)

    # present results
    if long_info:
        print_items(FIELDS, client.NetZones, None, entries, PrintMode.LONG)
    else:
        print_items(FIELDS_TABLE, client.NetZones, None, entries, PrintMode.TABLE)
# zone_list()

CMDS = [zone_add, zone_del, zone_edit, zone_list]
