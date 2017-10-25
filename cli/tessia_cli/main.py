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
Module containing entry point for client execution
"""

#
# IMPORTS
#
from tessia_cli.config import CONF
from tessia_cli.cmds import root
from tessia_cli.utils import log_exc_info

import click
import json
import logging
import os
import requests
import sys

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
def _parse_resp_error(response):
    """
    Parse the content of the error response for more friendly messages
    """
    raw_answer = response.text.strip()
    try:
        answer = json.loads(raw_answer)
    # not a json content: just return the raw content
    except Exception:
        # empty body: as a last resource, return the status code and
        # description
        if not raw_answer:
            raw_answer = '{} {}'.format(response.status_code, response.reason)
        return raw_answer

    msg = ''
    try:
        parsed_errors = []
        for error in answer['errors']:
            path = ''.join(error['path'])
            validation_of = list(error['validationOf'].keys())[0]
            validation_value = error['validationOf'][validation_of]
            friendly_error = "{} must be {}={}".format(
                path, validation_of, validation_value)
            parsed_errors.append(friendly_error)
        msg = ', '.join(parsed_errors)
    except Exception:
        # error messages other than 400 bad request have a different format
        try:
            msg = answer['message']
        # not a json content: just return the raw content
        except KeyError:
            msg = answer

    return msg
# _parse_resp_error()

def main(*args, **kwargs):
    """
    Entry point for client execution
    """
    try:
        CONF.log_config()
    # IOError = config file is not readable or writable
    # RuntimeError = log configuration is corrupted
    # it is still possible that the logging library raises exceptions - in that
    # case we let the traceback show up to give information on what needs to be
    # fixed.
    except (IOError, RuntimeError) as exc:
        click.echo('Error: {}'.format(str(exc)), err=True)
        sys.exit(1)

    logger = logging.getLogger(__name__)
    try:
        root()
    except requests.exceptions.HTTPError as exc:
        log_exc_info(logger, 'An error occurred during a request', exc)

        if exc.response.status_code == 400:
            msg = _parse_resp_error(exc.response)
            click.echo(
                'The server did not accept our request. '
                'The response is: {}'.format(msg), err=True)
        elif exc.response.status_code == 401:
            click.echo(
                "Error: authentication failed. You might need to create a new "
                "authentication token with 'tess conf key-gen'.",
                err=True
            )
        elif exc.response.status_code == 403:
            msg = _parse_resp_error(exc.response)
            click.echo(
                "Error: permission denied. Server answered: {}".format(msg),
                err=True
            )
        elif exc.response.status_code > 403 and exc.response.status_code < 500:
            msg = _parse_resp_error(exc.response)
            click.echo(
                "Error: request failed. Server answered: {}".format(msg),
                err=True
            )
        elif exc.response.status_code == 500:
            click.echo(
                "Error: the server failed to answer our request. "
                "See the logs for details.",
                err=True
            )
        else:
            click.echo(
                'Error: the server did not understand our request. '
                'The error is: {}'.format(str(exc)), err=True)
        sys.exit(1)
    except requests.exceptions.SSLError as exc:
        log_exc_info(logger, 'SSL connection failed', exc)
        ssl_error = str(exc)
        if '[SSL: CERTIFICATE_VERIFY_FAILED]' not in ssl_error:
            click.echo('Error: {}'.format(ssl_error), err=True)
            click.echo('See the logs for details.', err=True)
            sys.exit(1)
        click.echo(
            "The validation of the server's SSL certificate from '{}' failed. "
            "In order to assure the connection is safe, place a copy of the "
            "trusted CA's certificate file in {}/ca.crt".format(
                exc.request.url, os.path.dirname(CONF.USER_CONF_PATH)),
            err=True
        )
        sys.exit(1)

    except requests.exceptions.RequestException as exc:
        log_exc_info(logger, 'Server connection failed', exc)
        click.echo(
            "Error: connection to server '{}' failed, see the logs for "
            "details.".format(exc.request.url), err=True)
        sys.exit(1)
    except Exception as exc:
        log_exc_info(
            logger, 'The client encountered an unexpected problem', exc)
        click.echo(
            'The client encountered an unexpected problem, '
            'the error is: {}'.format(str(exc)), err=True)
        sys.exit(1)
# main()
