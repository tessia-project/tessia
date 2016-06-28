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

#
# CONSTANTS AND DEFINITIONS
#

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
        if value is not None:
            parsed_dict[key] = value
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
    mbytes.

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
        'KB': 1/1024,
        'MB': 1,
        'GB': 1024,
        'TB': 1024*1024,
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
