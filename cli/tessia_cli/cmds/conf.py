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
Module for the conf command
"""

#
# IMPORTS
#
from tessia_cli.config import CONF
from tessia_cli.client import Client
from tessia_cli.output import print_items
from tessia_cli.output import print_hor_table
from tessia_cli.utils import build_expect_header
from tessia_cli.utils import fetch_item
from tessia_cli.utils import fetch_and_delete
from tessia_cli.utils import version_verify

import click
import logging
import requests

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'user', 'key_id', 'created', 'last_used', 'desc'
)

#
# CODE
#

@click.group()
def conf():
    """manage the client's configuration"""
    pass
# conf()

@conf.command(name='key-gen')
@click.option('--login', prompt=True)
@click.option('--password', prompt=True, hide_input=True)
@click.option('--desc', help='description for key usage')
def key_gen(login, password, desc):
    """
    create a new access key
    """
    try:
        client = Client(basic_auth=(login, password))
    except requests.exceptions.HTTPError as exc:
        # not an authentication problem: let the exception go up and be
        # handled by the upper layer
        if exc.response.status_code != 401:
            raise
        raise click.ClickException(
            'authentication failed. Make sure your login and password '
            'are correct.')

    new_key = client.UserKeys()
    new_key.desc = desc
    key_id, key_secret = new_key.save()

    CONF.update_key(key_id, key_secret)
    click.echo('Key successfully created and added to client configuration.')
# key_gen()

@conf.command(name='key-del')
@click.option('--key', required=True, help='key id')
@click.option('--login', prompt=True)
@click.option('--password', prompt=True, hide_input=True)
def key_del(key, login, password):
    """
    remove an access key from the user's key list
    """

    try:
        client = Client(basic_auth=(login, password))
    except requests.exceptions.HTTPError as exc:
        # not an authentication problem: let the exception go up and be
        # handled by the upper layer
        if exc.response.status_code != 401:
            raise
        raise click.ClickException(
            'authentication failed. Make sure your login and password '
            'are correct.')
    fetch_and_delete(
        client.UserKeys,
        {'key_id': key},
        'key id not found.'
    )
    click.echo('Item successfully deleted.')
# key_del()

@conf.command(name='key-show')
@click.option('--all', is_flag=True, help="show all users (admin only)")
def key_show(**kwargs):
    """
    show the access keys associated with the user
    """
    client = Client()
    # all parameter provided: list all keys
    if kwargs['all'] is True:
        entries = client.UserKeys.instances()
    else:
        current_key = fetch_item(
            client.UserKeys,
            {'key_id': CONF.get_key()[0]},
            'current key has no user associated.'
        )
        entries = client.UserKeys.instances(where={'user': current_key.user})

    # present results
    print_items(
        FIELDS, client.UserKeys, None, entries)

# key_show()

@conf.command()
def show():
    """
    show current client's configuration
    """
    logger = logging.getLogger(__name__)
    client = Client()
    current_key = fetch_item(
        client.UserKeys,
        {'key_id': CONF.get_key()[0]},
        'current key has no user associated.'
    )

    conf_dict = CONF.get_config()
    resp = requests.head('{}/schema'.format(conf_dict['server_url']))
    resp.raise_for_status()
    try:
        server_version = int(resp.headers['X-Tessia-Api-Version'])
    except (TypeError, KeyError, ValueError) as exc:
        logger.error(
            'Received invalid response from server:', exc_info=exc)
        raise click.ClickException(
            "The server's address returned a malformed response, please "
            "verify if the address configured is correct and the network "
            "is functional before trying again."
        )

    headers = [
        'Authentication key in use',
        'Key owner login',
        'Client API version',
        'Server address',
        'Server API version',
    ]
    rows = [
        [
            current_key.key_id,
            current_key.user,
            CONF.get_api_version(),
            conf_dict['server_url'],
            server_version,
        ]
    ]
    print_hor_table(headers, rows)
# show()

@conf.command(name='set-server')
@click.argument('url')
def set_server(url):
    """
    set the tessia server's URL
    """
    logger = logging.getLogger(__name__)

    schema_url = '{}/schema'.format(url)
    try:
        resp = requests.head(
            schema_url,
            headers={'Expect': build_expect_header()}
        )
    except requests.exceptions.RequestException as exc:
        logger.debug(
            'Failed to connect to %s', schema_url, exc_info=exc)
        raise click.ClickException(
            'operation failed. The address provided did not respond.')

    # verify api version compatibility
    if not version_verify(logger, resp, silent=True):
        raise click.ClickException(
            'operation failed. The address provided returned an invalid '
            'response.')

    conf_dict = CONF.get_config()
    conf_dict['server_url'] = url
    CONF.update_config(conf_dict)

    click.echo('Server successfully configured.')
# set_server()
