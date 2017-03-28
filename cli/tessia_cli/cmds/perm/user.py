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
    'login', 'name', 'title', 'restricted', 'admin')

FIELDS_ROLE = (
    'project', 'role')

#
# CODE
#

@click.command(name='user-add')
@click.option('--login', required=True, help="user's login")
@click.option('--name', required=True, help="user's fullname")
@click.option('--title', help="user's job title")
@click.option('--restricted', is_flag=True,
              help="make user restricted (see docs for details)")
@click.option('--admin', is_flag=True, help="grant admin privilege")
def user_add(**kwargs):
    """
    create a new user
    """
    client = Client()

    item = client.Users()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()

    click.echo('User added successfully.')
# user_add()

@click.command(name='user-del')
@click.option('--login', required=True, help="login of user to delete")
def user_del(login):
    """
    remove an existing user
    """
    client = Client()

    fetch_and_delete(
        client.Users, {'login': login}, 'user not found.')
    click.echo('User successfully deleted.')
# user_del()

@click.command(name='user-edit')
@click.option('--login', required=True, help="login of target user")
@click.option('--name', help="user's fullname")
@click.option('--title', help="user's job title")
@click.option('--restricted', type=click.BOOL, help="switch restricted flag")
@click.option('--admin', type=click.BOOL, help="switch admin flag")
def user_edit(login, **kwargs):
    """
    change properties of a user
    """
    client = Client()
    fetch_and_update(
        client.Users,
        {'login': login},
        'user not found.',
        kwargs)
    click.echo('User successfully updated.')
# user_edit()

@click.command(name='user-list')
@click.option('--login', help="filter by user's login")
@click.option('--restricted', help="list restricted users")
@click.option('--admin', help="list admin users")
def user_list(**kwargs):
    """
    list registered users
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.Users.instances(**parsed_filter)

    # present results
    print_items(
        FIELDS, client.Users, None, entries)

# user_list()

@click.command(name='user-roles')
@click.option('user', '--login', required=True, help="user's login to list")
def user_roles(**kwargs):
    """
    list the roles associated to a user
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.UserRoles.instances(**parsed_filter)

    # present results
    print_items(
        FIELDS_ROLE, client.UserRoles, None, entries)

# user_roles()

CMDS = [user_add, user_del, user_edit, user_list, user_roles]
