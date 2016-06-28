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
    'name', 'hostname', 'model', 'type', 'fw_level', 'owner', 'project',
    'modified', 'modifier', 'desc'
)
TYPE_FIELDS = ('name', 'desc')

#
# CODE
#

@click.command(name='server-add')
@click.option('--name', required=True, help="server's name")
@click.option('--model', required=True,
              help="string describing server's model")
@click.option('--type', required=True, help="type of volume offered by server")
@click.option('--hostname', help="address where server is reachable")
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
@click.option('--name', required=True, help="server to delete")
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
@click.option('cur_name', '--name', required=True,
              help="name of server to be updated")
# set the parameter name after the model's attribute name to save on typing
@click.option('name', '--newname', help="new name of server")
@click.option('--desc', help="free form field describing server")
@click.option('fw_level', '--fwlevel', help="string describing firmware level")
@click.option('--hostname', help="address where server is reachable")
@click.option('--model', help="string describing server's model")
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

@click.command(name='server-show')
@click.option('--name', help="show specified server only")
@click.option('--model', help="filter by specified model")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
@click.option('--type', help="filter by specified volume type")
def server_show(**kwargs):
    """
    show registered storage servers
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.StorageServers.instances(**parsed_filter)

    # present results
    print_items(
        FIELDS, client.StorageServers, None, entries)

# server_show()

@click.command(name='server-types')
def server_types():
    """
    show the supported storage server types
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    entries = client.StorageServerTypes.instances()

    # present results
    print_items(
        TYPE_FIELDS, client.StorageServerTypes, None, entries)

# server_types()

CMDS = [server_add, server_del, server_edit, server_show, server_types]
