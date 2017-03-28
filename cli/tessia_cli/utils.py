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
Miscellaneous utilities that can be consumed by different modules
"""

#
# IMPORTS
#
from potion_client.exceptions import ItemNotFound
from tessia_cli.config import CONF

import click
import time

#
# CONSTANTS AND DEFINITIONS
#
REQUEST_WAIT_TIMEOUT = 60
REQUEST_TIMEOUT_MSG = (
    "Warning: the scheduler did not process our request in a reasonable time. "
    "This might or might not indicate a problem, depending on the scheduler "
    "load. You can still follow the progress of the request with the "
    "'req-show' command."
)

#
# CODE
#
def build_expect_header():
    """
    Craft the Expect: header used to tell the server we need an answer that is
    backwards compatible with our supported api version
    """
    header = 'tessia-api-compat-version="{}"'.format(CONF.get_api_version())
    return header
# build_expect_header()

def fetch_item(resource, search_fields, error_msg):
    """
    Helper function to fetch a single item from server

    Args:
        resource (Client.Resource): rest resource model
        search_fields (dict): filters for search criteria
        error_msg (str): error message in case of error

    Returns:
        abc: metaclass representing the item fetched

    Raises:
        ClickException: in case request fails
    """
    try:
        item = resource.first(where=search_fields)
    except ItemNotFound:
        raise click.ClickException(error_msg)
    return item
# fetch_item()

def fetch_and_delete(resource, search_fields, error_msg):
    """
    Utility function to fetch an item from server and delete it

    Args:
        resource (Client.Resource): rest resource model
        search_fields (dict): filters for search criteria
        error_msg (str): error message in case of error

    Returns:
        None

    Raises:
        None
    """
    item = fetch_item(resource, search_fields, error_msg)
    item.destroy()
# fetch_and_delete()

def fetch_and_update(resource, search_fields, error_msg, update_dict):
    """
    Utility function to fetch an item from server and update it

    Args:
        resource (Client.Resource): rest resource model
        search_fields (dict): filters for search criteria
        error_msg (str): error message in case of error
        update_dict (dict): fields and values to update item

    Returns:
        abc: metaclass representing the item updated

    Raises:
        ClickException: in case update dict is empty
    """
    item = fetch_item(resource, search_fields, error_msg)
    parsed_dict = {}
    for key, value in update_dict.items():
        # allow unsetting parameter
        if value == '':
            parsed_dict[key] = None
        elif value is not None:
            parsed_dict[key] = value
        # value not being updated: remove from object to prevent being part of
        # request
        elif hasattr(item, key):
            del item[key]
    if len(parsed_dict) == 0:
        raise click.ClickException('no update criteria provided.')

    item.update(**parsed_dict)
    return item
# fetch_and_update()

def size_to_str(size):
    """
    Takes a size in mbytes and returns it in the biggest of the units MB,
    GB or TB.

    Args:
        size (int): size to be formatted, in mbytes

    Returns:
        str: formatted size with its unit

    Raises:
        None
    """
    units = ['MB', 'GB', 'TB']

    size = float(size)

    old = size

    i = 0
    while True:
        old = size
        size /= 1024
        if size >= 1 and i < len(units) - 1:
            i += 1
        else:
            break
    old = round(old, 2)

    return '{}{}'.format(old, units[i])
# size_to_str()

def str_to_size(size_str):
    """
    Receives a human size (i.e. 10GB) and converts to an integer size in
    megabytes.

    Args:
        size_str (str): human size to be converted to integer

    Returns:
        int: formatted size in mbytes

    Raises:
        ValueError: in case size provided in invalid
    """
    if size_str is None:
        return None

    units = {
        'KB': 1/1000,
        'MB': 1,
        'GB': 1000,
        'TB': 1000*1000,
    }
    size_str = size_str.upper()
    try:
        if len(size_str) < 3:
            size_int = int(size_str)
        else:
            size_int = int(size_str[:-2])
            size_int *= units[size_str[-2:]]
    except (KeyError, TypeError, ValueError):
        raise ValueError('Invalid size format')

    return round(size_int)
# str_to_size()

def version_verify(logger, response, silent=False):
    """
    Helper function, receives a response object and verify if any report or
    error must be generated regarding version compatibility.

    Args:
        logger (logging.Logger): logger instance
        response (requests.Response): response to be evaluated
        silent (bool): whether to print messages or just return

    Returns:
        bool: in silent mode, returns False if validation fails

    Raises:
        ClickException: when not in silent mode in case validation fails
    """
    if response.status_code == 417:
        if silent:
            return False

        raise click.ClickException(
            'The current server API version is not supported by this client. '
            'You need to update the client to a newer version to be able to '
            'use the service.')
    elif response.status_code == 200:
        try:
            server_version = int(response.headers['X-Tessia-Api-Version'])
        except (TypeError, KeyError, ValueError) as exc:
            logger.error(
                'Received invalid response from server:', exc_info=exc)

            if silent:
                return False
            raise click.ClickException(
                "The server's address returned a malformed response, please "
                "verify if the address configured is correct and the network "
                "is functional before trying again."
            )

        if CONF.get_api_version() < server_version:
            click.echo(
                'warning: a newer api version is available on the server, '
                'you might want to update this client to have access to the '
                'latest features.', err=True)

    return True
# version_verify()

def wait_scheduler(client, arg_dict):
    """
    Helper function to submit a request and give user feedback while waiting
    for it to be processed by the scheduler.
    """
    item = client.JobRequests()
    for key, value in arg_dict.items():
        setattr(item, key, value)
    req_id = item.save()
    click.echo('\nRequest #{} submitted, waiting for scheduler to process it '
               '(Ctrl+C to stop waiting) ...'.format(req_id))

    timeout = time.time() + REQUEST_WAIT_TIMEOUT
    had_timeout = False
    with click.progressbar(length=100, show_eta=False, empty_char=' ',
                           label='processing job') as widget_bar:
        cur_length = 0
        while True:
            time.sleep(2)
            item = fetch_item(
                client.JobRequests,
                {'request_id': req_id},
                'unexpected error, the request was not found.')
            if item.state == 'COMPLETED' or item.state == 'FAILED':
                widget_bar.update(100)
                break
            elif cur_length < 90:
                cur_length += 10
                widget_bar.update(10)
            elif time.time() >= timeout:
                had_timeout = True
                break

    if had_timeout:
        click.echo('\n' + REQUEST_TIMEOUT_MSG)
    elif item.state == 'COMPLETED':
        if arg_dict['action_type'] == 'SUBMIT':
            click.echo('Request accepted; job id is #{}'.format(item.job_id))
        else:
            click.echo('Request accepted; job canceled.')
    elif item.state == 'FAILED':
        raise click.ClickException('request failed, reason is: {}'.format(
            item.result))

    return item.job_id
# wait_scheduler()
