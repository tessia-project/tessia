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
    'name', 'owner', 'project', 'modified', 'modifier', 'desc'
)

#
# CODE

@click.command(name='zone-add')
# set the parameter name after the model's attribute name to save on typing
@click.option('--name', required=True, help="name of network zone")
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
@click.option('--name', required=True, help="name of network zone")
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
@click.option('cur_name', '--name', required=True,
              help="name of network zone")
# set the parameter name after the model's attribute name to save on typing
@click.option('name', '--newname', help="new name of network zone")
@click.option('--owner', help="zone's owner login")
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

@click.command(name='zone-show')
@click.option('--name', help="show specified network zone only")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
def zone_show(**kwargs):
    """
    show registered network zones
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.NetZones.instances(**parsed_filter)

    # present results
    print_items(
        FIELDS, client.NetZones, None, entries)

# zone_show()

CMDS = [zone_add, zone_del, zone_edit, zone_show]
