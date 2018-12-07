# Copyright 2018 IBM Corp.
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
Module for operating system commands
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import PrintMode
from tessia.cli.types import CustomIntRange, NAME
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update

import click

#
# CONSTANTS AND DEFINITIONS
#
OS_TYPES = click.Choice(('cms', 'debian', 'redhat', 'suse'))

MODEL_FIELDS = (
    'name', 'type', 'major', 'minor', 'pretty_name', 'template'
)

MODEL_FIELDS_TABLE = (
    'name', 'type', 'pretty_name', 'template', 'major', 'minor'
)

VERSION_TYPE = CustomIntRange(min=0)

#
# CODE
#

@click.group(name='os')
def _os():
    """manage the supported operating systems"""
    pass
# _os()

@_os.command('add',
             short_help='add a supported operating system (admin only)')
@click.option('--name', required=True, type=NAME, help="OS identifier")
@click.option('--type', required=True, type=OS_TYPES, help="OS type")
@click.option('--major', required=True, type=VERSION_TYPE,
              help="major version number")
@click.option('--minor', required=True, type=VERSION_TYPE,
              help="minor version number")
@click.option('pretty_name', '--pname', required=True,
              help="OS pretty name (as in /etc/os-release)")
@click.option('--template', type=NAME, help="default install template")
def os_add(**kwargs):
    """
    add a supported operating system (admin only)
    """
    client = Client()

    item = client.OperatingSystems()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()

    click.echo('Item added successfully.')
# os_add()

@_os.command('del',
             short_help='remove a supported operating system (admin only)')
@click.option('--name', required=True, type=NAME, help="OS to delete")
def os_del(name):
    """
    remove a supported operating system (admin only)
    """
    client = Client()

    fetch_and_delete(
        client.OperatingSystems, {'name': name}, 'OS not found.')
    click.echo('Item successfully deleted.')
# os_del()

@_os.command(
    'edit',
    short_help='change properties of an operating system (admin only)')
@click.option('cur_name', '--name', required=True, type=NAME,
              help="OS identifier")
@click.option('name', '--newname', type=NAME, help="new OS name identifier")
@click.option('--type', type=OS_TYPES, help="OS type")
@click.option('--major', type=VERSION_TYPE, help="major version number")
@click.option('--minor', type=VERSION_TYPE, help="minor version number")
@click.option('pretty_name', '--pname',
              help="OS pretty name (as in /etc/os-release)")
@click.option('--template', type=NAME, help="default install template")
def os_edit(cur_name, **kwargs):
    """
    change properties of an operating system (admin only)
    """
    client = Client()
    fetch_and_update(
        client.OperatingSystems,
        {'name': cur_name},
        'OS not found.',
        kwargs)
    click.echo('Item successfully updated.')
# os_edit()

@_os.command('list')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--name', type=NAME, help="filter by OS identifier")
@click.option('--type', type=OS_TYPES, help="filter by OS type")
@click.option('--template', type=NAME, help="filter by default template")
def os_list(**kwargs):
    """
    list the supported operating systems
    """
    # fetch data from server
    client = Client()

    long_info = kwargs.pop('long_info')
    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.OperatingSystems.instances(**parsed_filter)

    # present results
    if long_info:
        print_items(MODEL_FIELDS, client.OperatingSystems, None, entries,
                    PrintMode.LONG)
    else:
        print_items(MODEL_FIELDS_TABLE, client.OperatingSystems, None, entries,
                    PrintMode.TABLE)
# os_list()
