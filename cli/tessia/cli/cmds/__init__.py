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
from pkg_resources import get_distribution
from tessia.cli.client import Client
from tessia.cli.cmds.autotemplate import autotemplate
from tessia.cli.cmds.conf import conf
from tessia.cli.cmds.conf import key_gen
from tessia.cli.cmds.job import job
from tessia.cli.cmds.system import system
from tessia.cli.cmds.perm import perm
from tessia.cli.cmds.net import net
from tessia.cli.cmds.repo import repo
from tessia.cli.cmds.storage import storage
from tessia.cli.config import CONF
from tessia.cli.session import SESSION
from tessia.cli.utils import build_expect_header, log_exc_info, version_verify

import click
import logging
import os
import requests
import sys

#
# CONSTANTS AND DEFINITIONS
#
CMDS = [
    autotemplate,
    conf,
    job,
    net,
    perm,
    repo,
    storage,
    system,
]
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
# messages constants
MSG_NO_KEY = (
    'There is no authentication key configured. Please enter your login and '
    'password so that the client can generate one for you.'
)
MSG_NO_SSL_CONN = (
    "SSL connection to the server failed, verify if the trusted certificate "
    "file is valid and the server address is correct. Press Ctrl+C to cancel "
    "or enter another URL."
)
MSG_NO_SSL_CERT = (
    "The validation of the server's SSL certificate failed. In order to "
    "assure the connection is safe, press Ctrl+C to cancel and place a copy "
    "of the trusted CA's certificate file in {}/ca.crt or enter another URL."
    .format(os.path.dirname(CONF.USER_CONF_PATH))
)
MSG_NO_URL = (
    'There is no server address configured. Please enter the URL (i.e. '
    'https://domain.com:5000) where we can find the tessia server'
)
MSG_SERVER_NOT_VALID = (
    'Enter the URL of a valid server or press Ctrl+C to cancel.'
)
MSG_URL_CANNOT_CONNECT = (
    'The address provided did not respond. Press Ctrl+C to cancel or enter '
    'another server URL.'
)
MSG_URL_INVALID_ANSWER = (
    'The address provided returned an invalid response. Enter the URL of a '
    'valid server or press Ctrl+C to cancel.'
)

PKG_DIST = get_distribution('tessia-cli')

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
            resp = SESSION.head(
                schema_url,
                headers={'Expect': build_expect_header()}
            )
            # 417 is handled by version_verify below
            if resp.status_code not in (200, 417):
                resp.raise_for_status()

        except requests.exceptions.HTTPError as exc:
            log_exc_info(logger, 'An error occurred during a request', exc)
            click.echo(MSG_URL_INVALID_ANSWER)
            continue

        except requests.exceptions.SSLError as exc:
            log_exc_info(logger, 'SSL connection failed', exc)
            # ssl cert not available for validation
            if '[SSL: CERTIFICATE_VERIFY_FAILED]' in str(exc):
                click.echo(MSG_NO_SSL_CERT)
            # general error
            else:
                click.echo(MSG_NO_SSL_CONN)
            continue

        except requests.exceptions.RequestException as exc:
            log_exc_info(logger, 'Server connection failed', exc)
            click.echo(MSG_URL_CANNOT_CONNECT)
            continue

        try:
            version_verify(logger, resp)
        except Exception as exc:
            click.echo(str(exc))
            click.echo(MSG_SERVER_NOT_VALID)
            continue

        # server is valid and input routine is finished
        break

    # save the url to config file
    conf_dict = CONF.get_config()
    conf_dict['server_url'] = server_url
    CONF.update_config(conf_dict)
# _config_server()

@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(
    prog_name='tessia command line client', version=PKG_DIST.version)
@click.pass_context
def root(ctx=None):
    """
    Tessia command line client
    """
    # certain commands should bypass server connection verification
    # any command with one argument will trigger help page
    if len(sys.argv) == 2:
        return
    # explicit call to help page
    elif len(sys.argv) > 2 and sys.argv[2].lower() in ('-h', '--help'):
        return
    # set-server should be reachable to establish server connectivity
    elif (len(sys.argv) > 2 and sys.argv[1].lower() == 'conf' and
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
        resp = SESSION.head(
            server_url,
            headers={'Expect': build_expect_header()}
        )

        # response is not valid: report error (417 will be handled by
        # version_verify in sequence)
        if resp.status_code != 200 and resp.status_code != 417:
            resp.raise_for_status()

        # perform version verification routine, in case server api is not
        # compatible execution will stop here
        version_verify(logger, resp)

    auth_key = CONF.get_key()
    # authorization key is missing and command is not to create one: force new
    # key generation
    if auth_key is None and not (
            len(sys.argv) >= 3 and sys.argv[1].lower() == 'conf' and
            sys.argv[2].lower() == 'key-gen'):

        click.echo(MSG_NO_KEY)
        login = click.prompt('Login')
        pwd = click.prompt('Password', hide_input=True)
        ctx.invoke(key_gen, login=login, password=pwd)
# root()

# add all the subcommands
for cmd in CMDS:
    root.add_command(cmd)
