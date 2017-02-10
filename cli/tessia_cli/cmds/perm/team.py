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
Module for the users command
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
    'name', 'desc'
)

#
# CODE
#

@click.command(name='team-add')
@click.option('--name', required=True, help="team's name")
@click.option('--desc', help="free form field describing team")
def team_add(**kwargs):
    """
    create a new team
    """
    client = Client()

    item = client.Projects()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()

    click.echo('Item added successfully.')
# team_add()

@click.command(name='team-del')
@click.option('--name', required=True, help="name of team to delete")
def team_del(name):
    """
    remove an existing team
    """
    client = Client()

    fetch_and_delete(
        client.Projects, {'name': name}, 'team not found.')
    click.echo('Item successfully deleted.')
# team_del()

@click.command(name='team-edit')
@click.option('cur_name', '--name', required=True,
              help="name of team to delete")
@click.option('name', '--newname', help="new name of team")
@click.option('--desc', help="free form field describing team")
def team_edit(cur_name, **kwargs):
    """
    change properties of an team
    """
    client = Client()
    fetch_and_update(
        client.Projects,
        {'name': cur_name},
        'team not found.',
        kwargs)
    click.echo('Item successfully updated.')
# team_edit()

@click.command(name='team-list')
@click.option('--name', help="list specified team only")
def team_list(**kwargs):
    """
    list registered teams
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.Projects.instances(**parsed_filter)

    # present results
    print_items(
        FIELDS, client.Projects, None, entries)

# team_list()

CMDS = [team_add, team_del, team_edit, team_list]
