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
Root group to which all commands are attached
"""

#
# IMPORTS
#
from tessia_cli.client import Client
from tessia_cli.cmds.conf import conf
from tessia_cli.cmds.conf import key_gen
from tessia_cli.cmds.system import system
from tessia_cli.cmds.perm import perm
from tessia_cli.config import CONF
from tessia_cli.cmds.net import net
from tessia_cli.cmds.storage import storage
from tessia_cli.utils import build_expect_header
from tessia_cli.utils import version_verify

import click
import logging
import requests
import sys

#
# CONSTANTS AND DEFINITIONS
#
CMDS = [
    conf,
    net,
    perm,
    storage,
    system,
]
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
MSG_NO_URL = (
    'There is no server address configured. Please enter the URL (i.e. '
    'https://domain.com:5000) where we can find the tessia server'
)
MSG_URL_CANNOT_CONNECT = (
    'Sorry, the address provided did not respond. Please try again or press '
    'Ctrl+C to cancel.'
)
MSG_URL_INVALID_ANSWER = (
    'Sorry, the address provided returned an invalid response. Please try '
    'again or press Ctrl+C to cancel.'
)
MSG_NO_KEY = (
    'There is no authentication key configured. Please enter your login and '
    'password so that the client can generate one for you.'
)

#
# CODE
#

def _config_server():
    """
    Auxiliary routine to request input from user and configure the server url.
    """
    logger = logging.getLogger(__name__)

    # show notification and prompt for input
    click.echo(MSG_NO_URL)
    while True:
        server_url = click.prompt("Server's address")
        schema_url = '{}/schema'.format(server_url)

        # try a connection to the provided address
        click.echo("Checking server's availability...")
        try:
            resp = requests.head(
                schema_url,
                headers={'Expect': build_expect_header()}
            )
        except requests.exceptions.RequestException as exc:
            logger.debug(
                'Failed to connect to %s', schema_url, exc_info=exc)
            click.echo(MSG_URL_CANNOT_CONNECT)
            continue

        # verify api version compatibility
        if not version_verify(logger, resp, silent=True):
            click.echo(MSG_URL_INVALID_ANSWER)
            continue

        # server is valid and input routine is finished
        break

    # save the url to config file
    conf_dict = CONF.get_config()
    conf_dict['server_url'] = server_url
    CONF.update_config(conf_dict)

    # verify api version compatibility, this time to report in case an update
    # is needed
    version_verify(logger, resp)

# _config_server()

@click.group(context_settings=CONTEXT_SETTINGS)
@click.pass_context
def root(ctx=None):
    """
    Tessia command line client
    """
    # command to set server url specified: don't do anything and let the
    # subcommand be called
    if (len(sys.argv) >= 3 and sys.argv[1].lower() == 'conf' and
            sys.argv[2].lower() == 'set-server'):
        return

    logger = logging.getLogger(__name__)

    server_url = CONF.get_config().get('server_url')

    # no server configured: enter routine to ask user for input
    if server_url is None:
        _config_server()
    # server found in configuration: verify api version compatibility
    else:
        server_url = '{}/schema'.format(server_url)
        resp = requests.head(
            server_url,
            headers={'Expect': build_expect_header()}
        )

        # response is not valid: report error (417 will be handled by
        # version_verify in sequence)
        if resp.status_code != 200 and resp.status_code != 417:
            resp.raise_for_status()

        # perform version verification routine, in case server api is not
        # compatible execution it will stop here
        version_verify(logger, resp)

    auth_key = CONF.get_key()
    # authorization key is missing: generate one
    if auth_key is None:
        click.echo(MSG_NO_KEY)
        login = click.prompt('Login')
        pwd = click.prompt('Password', hide_input=True)
        ctx.invoke(key_gen, login=login, password=pwd)
# root()

# add all the subcommands
for cmd in CMDS:
    root.add_command(cmd)
