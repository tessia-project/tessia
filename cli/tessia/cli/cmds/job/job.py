# Copyright 2017 IBM Corp.
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
Module for the job (scheduler jobs) command
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import print_ver_table
from tessia.cli.types import ACTION_TYPE
from tessia.cli.types import CONSTANT
from tessia.cli.types import JOB_TYPE
from tessia.cli.utils import fetch_item
from tessia.cli.utils import wait_scheduler
from time import sleep

import click

#
# CONSTANTS AND DEFINITIONS
#
REQUEST_FIELDS_GENERIC = (
    'request_id', 'action_type', 'job_type', 'submit_date', 'requester',
    'state',
)
REQUEST_FIELDS_DETAILED = (
    'request_id', 'action_type', 'job_type', 'submit_date', 'requester',
    'state', 'job_id', 'time_slot', 'timeout', 'priority', 'start_date',
    'result', 'parameters'
)
JOB_FIELDS_GENERIC = (
    'job_id', 'job_type', 'submit_date', 'start_date', 'end_date', 'requester',
    'state', 'description'
)
JOB_FIELDS_DETAILED = (
    'job_id', 'job_type', 'submit_date', 'start_date', 'end_date', 'requester',
    'state', 'description', 'resources', 'time_slot', 'timeout', 'result'
)

#
# CODE
#
@click.command(
    name='req-list',
    short_help='show the queue of requests or details of a request')
@click.option('request_id', '--id', type=int,
              help="filter by the specified request id")
@click.option('action_type', '--action', type=ACTION_TYPE,
              help='filter by action type')
@click.option('job_type', '--type', type=JOB_TYPE,
              help='filter by machine type')
@click.option('requester', '--owner', help='filter by owner login')
@click.option('--state', type=CONSTANT, help='filter by request state')
def req_list(request_id, **kwargs):
    """
    show the queue of requests or details of a request
    """
    client = Client()

    # id specified: print detailed information
    if request_id is not None:
        item = fetch_item(
            client.JobRequests,
            {'request_id': request_id},
            'request not found.')
        print_items(
            REQUEST_FIELDS_DETAILED, client.JobRequests, None, [item])
        return

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    # the result is paginated so we can iterate on it later
    entries = client.JobRequests.instances(**parsed_filter)

    print_ver_table(REQUEST_FIELDS_GENERIC, entries, REQUEST_FIELDS_GENERIC)

# req_list()

@click.command(short_help='send a request to the scheduler to cancel a job')
@click.option('job_id', '--id', type=int, required=True,
              help='job id to be canceled')
def cancel(**kwargs):
    """
    send a request to the scheduler to cancel a job
    """
    kwargs['action_type'] = 'CANCEL'

    wait_scheduler(Client(), kwargs)
# cancel()

@click.command(name='output')
@click.option('job_id', '--id', required=True, type=int, help="job id")
def output(job_id):
    """
    show the output of a job
    """
    client = Client()
    # retrieve the specified job from server
    item = fetch_item(
        client.Jobs,
        {'job_id': job_id},
        'job not found.')

    # retrieve the output from server in chunks of 100 lines so that we print
    # something to the user as soon as possible
    offset = 0
    qty = 100
    click.echo('Waiting for job output (Ctrl+C to stop waiting)')
    while True:
        output_buf = item.output({'offset': offset, 'qty': qty})
        # no output: set the line counter to 0
        if len(output_buf) == 0:
            buf_lines = 0
        # output available: print and increment the line counter and offset
        else:
            click.echo(output_buf, nl=False)
            buf_lines = len(output_buf.strip().split('\n'))
            # move the offset forward
            offset += buf_lines
        # got less lines than expected: possibly means the output ended, in
        # which case it only makes sense to continue if job is still active
        # so we check the job state
        if buf_lines < qty:
            item = fetch_item(
                client.Jobs,
                {'job_id': job_id},
                'job not found.')
            # job has finished: nothing more to do
            if item.state not in ('RUNNING', 'CLEANINGUP', 'WAITING'):
                return

            # job still active: sleep a bit and try to fetch more lines
            sleep(0.5)

# output()

@click.command(
    short_help='send a request to the scheduler to submit a new job')
@click.option('job_type', '--type', type=JOB_TYPE, required=True,
              help="type of execution machine to use")
@click.option('--parmfile', type=click.File('r'), required=True,
              help="parameter file for the execution machine")
@click.option('--timeout', type=int,
              help="period in seconds after job times out")
@click.option('--startdate', help="date when the job should be started")
@click.option('priority', '--prio', type=int, help="job priority")
def submit(job_type, parmfile, **kwargs):
    """
    send a request to the scheduler to submit a new job
    """
    request = {
        'action_type': 'SUBMIT',
        'job_type': job_type,
        'parameters': parmfile.read()
    }
    if kwargs['priority'] is not None:
        request['priority'] = kwargs['priority']
    if kwargs['timeout'] is not None:
        request['timeout'] = kwargs['timeout']
    if kwargs['startdate'] is not None:
        request['startdate'] = kwargs['startdate']

    wait_scheduler(Client(), request)
# submit()

@click.command(
    name='list',
    short_help='show the queue of jobs or details of a job')
@click.option('job_id', '--id', type=int, help="show details of a job id")
@click.option('--params', is_flag=True, help="show the job parameters")
@click.option('job_type', '--type', type=JOB_TYPE,
              help='filter by machine type')
@click.option('requester', '--owner', help='filter by owner login')
@click.option('--state', type=CONSTANT, help='filter by request state')
def list_(job_id, params, **kwargs):
    """
    show the queue of jobs or details of a job
    """
    if params is True and job_id is None:
        raise click.ClickException(
            'for --params a job id must be specified')

    client = Client()

    # id specified: print specific information
    if job_id is not None:
        item = fetch_item(
            client.Jobs,
            {'job_id': job_id},
            'job not found.')
        if params is True:
            click.echo(item.parameters)
        else:
            print_items(
                JOB_FIELDS_DETAILED, client.Jobs, None, [item])
        return

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    # the result is paginated so we can iterate on it later
    entries = client.Jobs.instances(**parsed_filter)

    print_ver_table(JOB_FIELDS_GENERIC, entries, JOB_FIELDS_GENERIC)
# list_()

CMDS = [cancel, list_, output, req_list, submit]
