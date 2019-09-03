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
Module for package repositories commands
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
from tessia.cli.types import URL
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update

import click

#
# CONSTANTS AND DEFINITIONS
#
MODEL_FIELDS = (
    'name', 'operating_system', 'url', 'kernel', 'initrd', 'owner',
    'project', 'modified', 'modifier', 'desc'
)

MODEL_FIELDS_TABLE = (
    'name', 'operating_system', 'url', 'kernel', 'initrd', 'owner',
    'project'
)

#
# CODE
#

@click.group()
def repo():
    """manage package repositories"""
    pass
# repo()

@repo.command('add')
@click.option('--name', required=True, type=NAME, help="repository name")
@click.option('--url', required=True, type=URL, help="network url")
@click.option('operating_system', '--os', help="installable operating system")
@click.option('--kernel', help="kernel path (when --os is specified)")
@click.option('--initrd', help="initrd path (when --os is specified)")
@click.option('--owner', help="owner of repository")
@click.option('--project', help="project owning repository")
@click.option('--desc', help="free form field describing repository")
def add(**kwargs):
    """
    add a new package repository
    """
    if kwargs['operating_system'] is not None:
        if kwargs['kernel'] is None:
            raise click.ClickException(
                '--kernel is required when --os was specified')
        elif kwargs['initrd'] is None:
            raise click.ClickException(
                '--initrd is required when --os was specified')

    client = Client()

    item = client.Repositories()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()

    click.echo('Item added successfully.')
# add()

@repo.command(name='del')
@click.option('--name', required=True, type=NAME, help="repository to delete")
def del_(name):
    """
    remove an existing repository
    """
    client = Client()

    fetch_and_delete(
        client.Repositories, {'name': name}, 'repository not found.')
    click.echo('Item successfully deleted.')
# del_()

@repo.command('edit', help='change properties of a repository')
@click.option('cur_name', '--name', required=True, type=NAME,
              help="repository name")
@click.option('name', '--newname', type=NAME, help="new repository name")
@click.option('--url', type=URL, help="network url")
@click.option('operating_system', '--os', help="installable operating system")
@click.option('--kernel', help="kernel path (when --os is specified)")
@click.option('--initrd', help="initrd path (when --os is specified)")
@click.option('--owner', help="owner of repository")
@click.option('--project', help="project owning repository")
@click.option('--desc', help="free form field describing repository")
def edit(cur_name, **kwargs):
    """
    change properties of an existing repository
    """
    client = Client()
    fetch_and_update(
        client.Repositories,
        {'name': cur_name},
        'repository not found.',
        kwargs)
    click.echo('Item successfully updated.')
# edit()

@repo.command(name='list')
@click.option('--initrd', help="filter by initrd path")
@click.option('--kernel', help="filter by kernel path")
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--my', help="show only my own repos", is_flag=True,
              default=False)
@click.option('--name', type=NAME, help="filter by repository name")
@click.option('operating_system', '--os', help="filter by operating system")
@click.option('--owner', help="filter by owner")
@click.option('--project', help="filter by project")
@click.option('--url', type=URL, help="filter by network url")
def list_(**kwargs):
    """
    list the available repositories
    """
    client = Client()

    long_info = kwargs.pop('long_info')
    only_mine = kwargs.pop('my')
    if only_mine:
        kwargs.update({'owner': CONF.get_login()})
    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'name': False}
    # fetch data from server
    entries = client.Repositories.instances(**parsed_filter)
    # present results
    if long_info:
        print_items(MODEL_FIELDS, client.Repositories, None, entries,
                    PrintMode.LONG)
    else:
        print_items(MODEL_FIELDS_TABLE, client.Repositories, None, entries,
                    PrintMode.TABLE)
# list_()
