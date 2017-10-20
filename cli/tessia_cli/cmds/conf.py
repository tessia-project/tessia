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
from tessia_cli.session import SESSION
from tessia_cli.utils import build_expect_header
from tessia_cli.utils import fetch_item
from tessia_cli.utils import fetch_and_delete
from tessia_cli.utils import version_verify

import click
import logging
import os
import requests

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'user', 'key_id', 'created', 'last_used', 'desc'
)

NO_USER_MSG = (
    "current key is not registered, create a new one with 'tessia conf key-gen'"
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
        new_key = client.UserKeys()
        new_key.desc = desc
        key_id, key_secret = new_key.save()

    except requests.exceptions.HTTPError as exc:
        # not an authentication problem: let the exception go up and be
        # handled by the upper layer
        if exc.response.status_code != 401:
            raise
        raise click.ClickException(
            'authentication failed. Make sure your login and password '
            'are correct.')

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
        fetch_and_delete(
            client.UserKeys,
            {'key_id': key},
            'key id not found.'
        )

    except requests.exceptions.HTTPError as exc:
        # not an authentication problem: let the exception go up and be
        # handled by the upper layer
        if exc.response.status_code != 401:
            raise
        raise click.ClickException(
            'authentication failed. Make sure your login and password '
            'are correct.')
    click.echo('Item successfully deleted.')
# key_del()

@conf.command(name='key-list')
def key_list(**kwargs):
    """
    list the access keys associated with the user
    """
    client = Client()
    current_key = fetch_item(
        client.UserKeys,
        {'key_id': CONF.get_key()[0]},
        NO_USER_MSG,
    )
    entries = client.UserKeys.instances(where={'user': current_key.user})

    # present results
    print_items(
        FIELDS, client.UserKeys, None, entries)

# key_list()

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
        NO_USER_MSG,
    )

    conf_dict = CONF.get_config()
    resp = SESSION.head('{}/schema'.format(conf_dict['server_url']))
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
        resp = SESSION.head(
            schema_url,
            headers={'Expect': build_expect_header()}
        )
        # 417 is handled by version_verify below
        if resp.status_code not in (200, 417):
            resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        logger.debug(
            'Failed to connect to %s', schema_url, exc_info=exc)
        raise click.ClickException(
            'the address provided returned an invalid response.'
        ) from None
    except requests.exceptions.SSLError as exc:
        logger.debug(
            'Failed to connect to %s', schema_url, exc_info=exc)
        ssl_error = str(exc)
        if '[SSL: CERTIFICATE_VERIFY_FAILED]' not in ssl_error:
            msg = (
                "SSL connection to the server failed, verify if the trusted "
                "certificate file is valid and the server address is correct. "
                "You can also see the logs for details.")
            raise click.ClickException(msg) from None
        raise click.ClickException(
            "The validation of the server's SSL certificate failed. "
            "In order to assure the connection is safe, place a copy of the "
            "trusted CA's certificate file in {}/ca.crt and try again.".format(
                os.path.dirname(CONF.USER_CONF_PATH))
        ) from None
    except requests.exceptions.RequestException as exc:
        logger.debug(
            'Failed to connect to %s', schema_url, exc_info=exc)
        raise click.ClickException(
            'operation failed. The address provided did not respond.'
        ) from None

    # verify api version compatibility, may raise exception
    version_verify(logger, resp)

    conf_dict = CONF.get_config()
    conf_dict['server_url'] = url
    CONF.update_config(conf_dict)

    click.echo('Server successfully configured.')
# set_server()
