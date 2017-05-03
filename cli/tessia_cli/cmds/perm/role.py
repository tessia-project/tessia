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
Module for the role subcommands
"""

#
# IMPORTS
#
from tessia_cli.client import Client
from tessia_cli.filters import dict_to_filter
from tessia_cli.output import print_items
from tessia_cli.utils import fetch_and_delete

import click

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'name', 'desc', 'actions')

#
# CODE
#

@click.command(name='role-deny')
@click.option('role', '--name', required=True,
              help="role name to be removed")
@click.option('user', '--login', required=True, help="user's login")
@click.option('--project', required=True, help="target project")
def role_deny(**kwargs):
    """
    remove a role of a user from a project
    """
    client = Client()

    fetch_and_delete(
        client.UserRoles, kwargs, 'user role not found.')
    click.echo('User role removed sucessfully.')
# role_deny()

@click.command(name='role-grant')
@click.option('role', '--name', required=True,
              help="role name to grant access")
@click.option('user', '--login', required=True, help="user's login")
@click.option('--project', required=True, help="target project")
def role_grant(**kwargs):
    """
    grant a role to a user on a project
    """
    client = Client()

    item = client.UserRoles()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()

    click.echo('User role added successfully.')
# role_grant()

@click.command(name='role-list')
@click.option('--name', help="filter by role name")
def role_list(**kwargs):
    """
    list the available roles
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.Roles.instances(**parsed_filter)

    # pre-process the list of actions before printing it
    pretty_entries = []
    class Entry(object):
        """Helper class to allow setting attributes"""
        def __init__(self, name, desc, actions):
            self.name = name
            self.desc = desc
            self.actions = actions
        # __init__()
    # Entry
    # create 'fake' objects to represent each role entry
    for entry in entries:
        pretty_actions = []
        for action_entry in entry['actions']:
            pretty_actions.append('{action}-{resource}'.format(**action_entry))

        pretty_entries.append(Entry(
            entry.name, entry.desc, ', '.join(pretty_actions)))

    # present results
    print_items(
        FIELDS, client.Roles, None, pretty_entries)
# role_list()

CMDS = [role_deny, role_grant, role_list]
