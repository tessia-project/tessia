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
from tessia.cli.client import Client
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import PrintMode
from tessia.cli.types import LOGIN
from tessia.cli.types import NAME
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update

import click

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'login', 'name', 'title', 'restricted', 'admin'
)

FIELDS_TABLE = (
    'login', 'name', 'admin', 'restricted', 'title'
)

FIELDS_ROLE = (
    'user', 'project', 'role')

#
# CODE
#

@click.command(name='user-add')
@click.option('--login', required=True, type=LOGIN, help="user's login")
@click.option('--name', required=True, type=NAME, help="user's fullname")
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
@click.option('--login', required=True, type=LOGIN,
              help="login of user to delete")
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
@click.option('--login', required=True, type=LOGIN,
              help="login of target user")
@click.option('--name', type=NAME, help="user's fullname")
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
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--login', type=LOGIN, help="filter by user's login")
@click.option('--restricted', type=click.BOOL, help="list restricted users")
@click.option('--admin', type=click.BOOL, help="list admin users")
def user_list(**kwargs):
    """
    list registered users
    """
    # fetch data from server
    client = Client()

    long_info = kwargs.pop('long_info')
    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'login': False}
    entries = client.Users.instances(**parsed_filter)

    # present results
    if long_info:
        print_items(FIELDS, client.Users, None, entries, PrintMode.LONG)
    else:
        print_items(FIELDS_TABLE, client.Users, None, entries, PrintMode.TABLE)

# user_list()

@click.command(name='user-roles')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('user', '--login', type=LOGIN, help="filter by user login")
@click.option('project', '--project', type=NAME, help="filter by project")
@click.option('role', '--role', type=NAME, help="filter by role name")
def user_roles(**kwargs):
    """
    list the roles associated to users
    """
    # fetch data from server
    client = Client()

    long_info = kwargs.pop('long_info')
    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'user': False}
    entries = client.UserRoles.instances(**parsed_filter)

    # present results
    if long_info:
        print_items(FIELDS_ROLE, client.UserRoles, None, entries,
                    PrintMode.LONG)
    else:
        print_items(FIELDS_ROLE, client.UserRoles, None, entries,
                    PrintMode.TABLE)
# user_roles()

CMDS = [user_add, user_del, user_edit, user_list, user_roles]
