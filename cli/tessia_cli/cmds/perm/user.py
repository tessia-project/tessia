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

import click

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'login', 'name', 'title', 'restricted', 'admin')

#
# CODE
#

@click.command(name='user-show')
@click.option('--login', help="list specified user only")
@click.option('--restricted', help="list restricted users")
@click.option('--admin', help="list admin users")
def user_show(**kwargs):
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

# user_show()

CMDS = [user_show]
