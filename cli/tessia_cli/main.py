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

import click
import json
import logging
import requests
import sys

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

def _log_exc_info(msg, exc):

    logger = logging.getLogger(__name__)
    # exception caused by a failed http request: log it's information

    if hasattr(exc, 'response') and exc.response is not None:
        msg += '\ndebug info:\n'
        msg = 'An error occurred during a request, debug info:\n'
        msg += 'Status code: {} {}\n'.format(
            exc.response.status_code, exc.response.reason)
        msg += 'Response headers: {}\n'.format(exc.response.headers)
        msg += 'Response body: {}\n'.format(exc.response.text)
        msg += 'Request headers: {}\n'.format(
            exc.response.request.headers)
        msg += 'Request body: {}\n'.format(exc.response.request.body)

    logger.error(msg, exc_info=exc)
# _log_response_info()

def _parse_resp_error(response):
    """
    Parse the content of the error response for more friendly messages
    """
    try:
        answer = json.loads(response.text.strip())
    # not a json content: just return the raw content
    except Exception:
        return answer

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

def main():
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

    try:
        root()
    except requests.exceptions.HTTPError as exc:
        _log_exc_info('An error occurred during a request', exc)

        if exc.response.status_code == 400:
            msg = _parse_resp_error(exc.response)
            click.echo(
                'The server did not accept our request. '
                'The response is: {}'.format(msg), err=True)
        elif exc.response.status_code == 401:
            click.echo(
                "Error: authentication failed. You might need to create a new "
                "authentication token with 'tessia conf key-gen'.",
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
    except requests.exceptions.RequestException as exc:
        _log_exc_info('Server connection failed', exc)
        click.echo(
            'Error: server connection failed, see the logs for details.',
            err=True)
        sys.exit(1)
    except Exception as exc:
        _log_exc_info('The client encountered an unexpected problem', exc)
        click.echo(
            'The client encountered an unexpected problem, '
            'the error is: {}'.format(str(exc)), err=True)
        sys.exit(1)
# main()
