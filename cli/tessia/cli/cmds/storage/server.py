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
Module for the server (storage servers) command
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import PrintMode
from tessia.cli.types import CONSTANT
from tessia.cli.types import HOSTNAME
from tessia.cli.types import NAME
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update
import click

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'name', 'hostname', 'model', 'type', 'fw_level', 'owner', 'project',
    'modified', 'modifier', 'desc'
)

FIELDS_TABLE = (
    'name', 'hostname', 'model', 'type', 'fw_level', 'owner', 'project'
)

TYPE_FIELDS = ('name', 'desc')

#
# CODE
#

@click.command(name='server-add')
@click.option('--name', required=True, type=NAME, help="server's name")
@click.option('--model', required=True, type=CONSTANT,
              help="string describing server's model")
@click.option('--type', required=True, help="type of volume offered by server")
@click.option('--hostname', type=HOSTNAME,
              help="address where server is reachable")
@click.option('fw_level', '--fwlevel', help="string describing firmware level")
@click.option('--project', help="project owning server")
@click.option('--desc', help="free form field describing server")
def server_add(**kwargs):
    """
    add a new storage server entry
    """
    client = Client()

    item = client.StorageServers()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()

    click.echo('Item added successfully.')
# server_add()

@click.command(name='server-del')
@click.option('--name', required=True, type=NAME, help="server to delete")
def server_del(name):
    """
    remove an existing storage server
    """
    client = Client()

    fetch_and_delete(
        client.StorageServers, {'name': name}, 'server not found.')
    click.echo('Item successfully deleted.')
# server_del()

@click.command(
    name='server-edit',
    short_help='change properties of an existing storage server')
@click.option('cur_name', '--name', required=True, type=NAME,
              help="name of server to be updated")
# set the parameter name after the model's attribute name to save on typing
@click.option('name', '--newname', type=NAME, help="new name of server")
@click.option('--desc', help="free form field describing server")
@click.option('fw_level', '--fwlevel', help="string describing firmware level")
@click.option('--hostname', type=HOSTNAME,
              help="address where server is reachable")
@click.option('--model', type=CONSTANT,
              help="string describing server's model")
@click.option('--owner', help="server's owner login")
@click.option('--project', help="project owning server")
@click.option('--type', help="type of volume offered by server")
def server_edit(cur_name, **kwargs):
    """
    change properties of an existing storage server
    """
    client = Client()
    fetch_and_update(
        client.StorageServers,
        {'name': cur_name},
        'server not found.',
        kwargs)
    click.echo('Item successfully updated.')
# server_edit()

@click.command(name='server-list')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--model', type=CONSTANT, help="filter by specified model")
@click.option('--name', type=NAME, help="filter by specified name")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
@click.option('--type', help="filter by specified volume type")
def server_list(**kwargs):
    """
    list registered storage servers
    """
    # fetch data from server
    client = Client()

    long_info = kwargs.pop('long_info')
    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'name': False}
    entries = client.StorageServers.instances(**parsed_filter)

    # present results
    if long_info:
        print_items(FIELDS, client.StorageServers, None, entries,
                    PrintMode.LONG)
    else:
        print_items(FIELDS_TABLE, client.StorageServers, None, entries,
                    PrintMode.TABLE)
# server_list()

@click.command(name='server-types')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
def server_types(**kwargs):
    """
    list the supported storage server types
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    entries = client.StorageServerTypes.instances()

    # present results
    if kwargs.pop('long_info'):
        print_items(TYPE_FIELDS, client.StorageServerTypes, None, entries,
                    PrintMode.LONG)
    else:
        print_items(TYPE_FIELDS, client.StorageServerTypes, None, entries,
                    PrintMode.TABLE)
# server_types()

CMDS = [server_add, server_del, server_edit, server_list, server_types]
