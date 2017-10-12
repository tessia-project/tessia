# Copyright 2017 IBM Corp.
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
Module for the project subcommands
"""

#
# IMPORTS
#
from tessia_cli.client import Client
from tessia_cli.filters import dict_to_filter
from tessia_cli.output import print_items
from tessia_cli.types import NAME
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

@click.command(name='project-add')
@click.option('--name', required=True, type=NAME, help="project's name")
@click.option('--desc', required=True,
              help="free form field describing project")
def project_add(**kwargs):
    """
    create a new project
    """
    client = Client()

    item = client.Projects()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()

    click.echo('Item added successfully.')
# project_add()

@click.command(name='project-del')
@click.option('--name', required=True, type=NAME,
              help="name of project to delete")
def project_del(name):
    """
    remove an existing project
    """
    client = Client()

    fetch_and_delete(
        client.Projects, {'name': name}, 'project not found.')
    click.echo('Item successfully deleted.')
# project_del()

@click.command(name='project-edit')
@click.option('cur_name', '--name', required=True,
              help="name of project to edit")
@click.option('name', '--newname', type=NAME,
              help="new name of project")
@click.option('--desc', required=True,
              help="free form field describing project")
def project_edit(cur_name, **kwargs):
    """
    change properties of an project
    """
    client = Client()
    fetch_and_update(
        client.Projects,
        {'name': cur_name},
        'project not found.',
        kwargs)
    click.echo('Item successfully updated.')
# project_edit()

@click.command(name='project-list')
@click.option('--name', type=NAME, help="list specified project only")
def project_list(**kwargs):
    """
    list registered projects
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.Projects.instances(**parsed_filter)

    # present results
    print_items(
        FIELDS, client.Projects, None, entries)

# project_list()

CMDS = [project_add, project_del, project_edit, project_list]
