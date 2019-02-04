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
from tessia.cli.config import CONF

import click
import json
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
    if not parsed_dict:
        raise click.ClickException('no update criteria provided.')

    item.update(**parsed_dict)
    return item
# fetch_and_update()

def log_exc_info(logger, msg, req_exc):
    """
    Log exception information of a failed request.

    Args:
        logger (Logger): logging object
        msg (str): initial message to be concatenated with the exception
                   information
        req_exc (requests.exceptions.RequestException): object
    """
    # exception caused by a failed http request: log its information
    if hasattr(req_exc, 'response') and req_exc.response is not None:
        msg = 'An error occurred during a request, debug info:\n'
        msg += 'URL: {}\n'.format(req_exc.request.url)
        msg += 'Status code: {} {}\n'.format(
            req_exc.response.status_code, req_exc.response.reason)
        msg += 'Response headers: {}\n'.format(req_exc.response.headers)
        msg += 'Response body: {}\n'.format(req_exc.response.text)
        msg += 'Request headers: {}\n'.format(
            req_exc.response.request.headers)
        msg += 'Request body: {}\n'.format(req_exc.response.request.body)

    logger.warning(msg, exc_info=req_exc)
# log_exc_info()

def parse_error_resp(response):
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
# parse_error_resp()

def size_to_str(size):
    """
    Take a size in mebibytes and return it in the biggest of the units MiB,
    GiB or TiB.

    Args:
        size (int): size to be formatted, in mebibytes

    Returns:
        str: formatted size with its unit
    """
    # user set a flag to keep memory configuration unchanged: no need to
    # compute size, just return
    if size == 0:
        return '0'

    units = ['MiB', 'GiB', 'TiB']
    max_units = len(units) - 1

    size = float(size)

    old = size

    i = 0
    while True:
        old = size
        size /= 1024
        if size >= 1 and i < max_units:
            i += 1
        else:
            break
    old = round(old, 2)

    return '{} {}'.format(old, units[i])
# size_to_str()

def str_to_size(size_str):
    """
    Receives a human size (i.e. 10GB) and converts to an integer size in
    mebibytes.

    Args:
        size_str (str): human size to be converted to integer

    Returns:
        int: formatted size in mebibytes

    Raises:
        ValueError: in case size provided in invalid
    """
    if size_str is None:
        return None

    # no unit: assume mebibytes as default and convert directly
    if size_str.isnumeric():
        return int(size_str)

    size_str = size_str.upper()

    # check if size is non-negative number
    if size_str.startswith('-'):
        raise ValueError(
            'Invalid size format: {}'.format(size_str)) from None

    # decimal units are converted to bytes and then to mebibytes
    dec_units = ('KB', 'MB', 'GB', 'TB')
    for index, unit in enumerate(dec_units):
        # unit used is different: try next
        if not size_str.endswith(unit):
            continue
        try:
            size_int = int(size_str[:-2]) * pow(1000, index+1)
        except ValueError:
            raise ValueError(
                'Invalid size format: {}'.format(size_str)) from None
        # result is returned in mebibytes
        return int(size_int / pow(1024, 2))

    # binary units are just divided/multipled by powers of 2
    bin_units = ('KIB', 'MIB', 'GIB', 'TIB')
    for index, unit in enumerate(bin_units):
        # unit used is different: try next
        if not size_str.endswith(unit):
            continue
        try:
            size_int = int(int(size_str[:-3]) * pow(1024, index-1))
        except ValueError:
            raise ValueError(
                'Invalid size format: {}'.format(size_str)) from None
        return size_int

    raise ValueError(
        'Invalid size format: {}'.format(size_str)) from None
# str_to_size()

def version_verify(logger, response):
    """
    Helper function, receives a response object and verify if any report or
    error must be generated regarding version compatibility.

    Args:
        logger (logging.Logger): logger instance
        response (requests.Response): response to be evaluated

    Raises:
        ClickException: in case validation fails
    """
    msg_invalid_resp = (
        "The defined server's address returned a malformed response, please "
        "verify if the address is correct before trying again.")

    # make sure the answer is valid and came from our server
    if response.status_code not in (200, 417):
        raise click.ClickException(msg_invalid_resp)
    try:
        server_version = int(response.headers['X-Tessia-Api-Version'])
    except (TypeError, KeyError, ValueError) as exc:
        logger.error(
            'Received invalid response from server:', exc_info=exc)
        raise click.ClickException(msg_invalid_resp)

    # response is from our server, now see possible scenarios regarding api
    # version state

    # server api version not supported by client
    if response.status_code == 417:
        raise click.ClickException(
            'The current server API version is not supported by this client. '
            'You need to update the client to a newer version to be able to '
            'use the service.')
    # server api supported but newer version is available: warn user
    elif CONF.get_api_version() < server_version:
        click.echo(
            'warning: a newer api version is available on the server, '
            'you might want to update this client to have access to the '
            'latest features.', err=True)

# version_verify()

def submit_csv_job(client, ctx, commit, file_content, verbosity, force,
                   resource_type):
    """
    submit a job for importing data in CSV format
    """
    params = {'resource_type': resource_type, 'content': file_content.read()}
    if commit:
        if not force:
            msg = ('warning: this operation affects multiple entries, are you '
                   'sure you want to proceed?')
            click.confirm(msg, abort=True, err=True)
        params['commit'] = commit
    if verbosity:
        params['verbosity'] = verbosity
    request = {'action_type': 'SUBMIT', 'job_type': 'bulkop',
               'parameters': json.dumps(params)}

    job_id = wait_scheduler(client, request)
    try:
        wait_job_exec(client, job_id)
        ctx.invoke(ctx.obj['OUTPUT'], job_id=job_id)
    except KeyboardInterrupt:
        cancel_job = click.confirm('\nDo you want to cancel the job?')
        if not cancel_job:
            click.echo('warning: job is still running, remember to cancel it '
                       'if you want to submit a new action for this system')
            raise
        ctx.invoke(ctx.obj['CANCEL'], job_id=job_id)
# submit_csv_job()

def wait_job_exec(client, job_id):
    """
    Wait until job starts to execute.

    Args:
        client (Client): Potion client to submit requests
        job_id (int): job id to wait for
    """
    click.echo('Waiting for job #{} to start...'.format(job_id))
    while True:
        item = fetch_item(
            client.Jobs,
            {'job_id': job_id},
            'job not found.')
        if item.state != 'WAITING':
            break
        time.sleep(0.5)
# wait_job_exec()

def wait_scheduler(client, arg_dict):
    """
    Helper function to submit a request and give user feedback while waiting
    for it to be processed by the scheduler.

    Args:
        client (Client): Potion client to submit requests
        arg_dict (dict): job request

    Returns:
        int: job id
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
            click.echo(
                'Request accepted; job #{} canceled.'.format(item.job_id))
    elif item.state == 'FAILED':
        raise click.ClickException('request failed, reason is: {}'.format(
            item.result))

    return item.job_id
# wait_scheduler()
