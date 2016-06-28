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
Module for the subnet command
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
    'name', 'zone', 'address', 'gateway', 'dns_1', 'dns_2', 'vlan',
    'owner', 'project', 'modified', 'modifier', 'desc'
)

#
# CODE

@click.command('subnet-add')
# set the parameter name after the model's attribute name to save on typing
@click.option(
    '--name', required=True,
    help="netzone-name/subnet-name to create (i.e. zone-foo/subnet-bar)")
@click.option('--address', required=True,
              help="subnet address (i.e. 192.168.0.0/24)")
@click.option('gateway', '--gw', help="gateway address (i.e. 192.168.0.1)")
@click.option('dns_1', '--dns1', help="primary dns address (i.e. 192.168.0.5)")
@click.option('dns_2', '--dns2',
              help="secondary dns address (i.e. 192.168.0.6)")
@click.option('--vlan', help="vlan identifier")
@click.option('--project', help="project owning subnet")
@click.option('--desc', help="free form field describing subnet")
def subnet_add(**kwargs):
    """
    create a new subnet
    """
    try:
        kwargs['zone'], kwargs['name'] = kwargs['name'].rsplit('/', 1)
    except:
        raise click.ClickException('invalid format for name')
    client = Client()

    item = client.Subnets()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# subnet_add()

@click.command(name='subnet-del')
@click.option(
    '--name', required=True,
    help="netzone-name/subnet-name to delete (i.e. zone-foo/subnet-bar)")
def subnet_del(name):
    """
    remove an existing subnet
    """
    try:
        zone, name = name.rsplit('/', 1)
    except:
        raise click.ClickException('invalid format for name')
    client = Client()

    fetch_and_delete(
        client.Subnets, {'zone': zone, 'name': name}, 'subnet not found.')
    click.echo('Item successfully deleted.')
# subnet_del()

@click.command(name='subnet-edit')
@click.option(
    'cur_name', '--name', required=True,
    help="netzone-name/subnet-name to edit (i.e. zone-foo/subnet-bar)")
@click.option('name', '--newname', help="new subnet name")
@click.option('--address', help="subnet address (i.e. 192.168.0.0/24)")
@click.option('gateway', '--gw', help="gateway address (i.e. 192.168.0.1)")
@click.option('dns_1', '--dns1', help="primary dns address (i.e. 192.168.0.5)")
@click.option('dns_2', '--dns2',
              help="secondary dns address (i.e. 192.168.0.6)")
@click.option('--vlan', help="vlan identifier")
@click.option('--project', help="project owning subnet")
@click.option('--desc', help="free form field describing subnet")
def subnet_edit(cur_name, **kwargs):
    """
    change properties of an existing subnet
    """
    try:
        zone, name = cur_name.rsplit('/', 1)
    except:
        raise click.ClickException('invalid format for name')

    client = Client()
    fetch_and_update(
        client.Subnets,
        {'zone': zone, 'name': name},
        'subnet not found.',
        kwargs)
    click.echo('Item successfully updated.')
# subnet_edit()

@click.command(name='subnet-show')
@click.option(
    '--name',
    help="show specified zone-name/subnet-name or filter by subnet-name")
@click.option('zone', '--zone',
              help="filter by specified network zone")
@click.option('--address', help="filter by specified address")
@click.option('--vlan', help="filter by specified vlan")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
def subnet_show(**kwargs):
    """
    show registered subnets
    """
    # zone/subnet format specified: split it
    if kwargs['name'] is not None and kwargs['name'].find('/') > -1:
        # zone dedicated parameter also specified: report conflict
        if kwargs['zone'] is not None:
            raise click.ClickException(
                'zone specified twice (--name and --zone)')
        try:
            kwargs['zone'], kwargs['name'] = \
                kwargs['name'].split('/', 1)
        except:
            raise click.ClickException('invalid format for name')

    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.Subnets.instances(**parsed_filter)

    # present results
    print_items(
        FIELDS, client.Subnets, None, entries)
# subnet_show()

CMDS = [subnet_add, subnet_del, subnet_edit, subnet_show]
