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
Module for the ip (ip addresses) command
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.config import CONF
from tessia.cli.cmds.job.job import cancel as job_cancel
from tessia.cli.cmds.job.job import output as job_output
from tessia.cli.filters import dict_to_filter
from tessia.cli.types import IPADDRESS, NAME, SUBNET, VERBOSITY_LEVEL
from tessia.cli.output import print_items
from tessia.cli.output import PrintMode
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update
from tessia.cli.utils import submit_csv_job

import click

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'address', 'subnet', 'system', 'owner', 'project', 'modified',
    'modifier', 'desc',
)

FIELDS_TABLE = (
    'address', 'subnet', 'system', 'owner', 'project', 'desc'
)

#
# CODE

@click.command(name='ip-add')
@click.option('--subnet', required=True, type=SUBNET, help='target subnet')
@click.option('address', '--ip', required=True, type=IPADDRESS,
              help="ip address to create (i.e. 192.168.0.50)")
@click.option('--system', type=NAME, help="assign ip to this system")
@click.option('--owner', help="owner login")
@click.option('--project', help="project owning ip address")
@click.option('--desc', help="free form field describing address")
def ip_add(**kwargs):
    """
    create a new ip address
    """
    client = Client()

    item = client.IpAddresses()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# ip_add()

@click.command(name='ip-del')
@click.option('--subnet', required=True, type=SUBNET,
              help='subnet containing ip')
@click.option('address', '--ip', required=True, type=IPADDRESS,
              help="ip address to delete")
def ip_del(**kwargs):
    """
    remove an existing ip address
    """
    client = Client()

    fetch_and_delete(
        client.IpAddresses,
        kwargs,
        'ip address not found.'
    )
    click.echo('Item successfully deleted.')
# ip_del()

@click.command(name='ip-edit')
@click.option('--subnet', required=True, type=SUBNET,
              help='subnet containing ip')
@click.option('cur_address', '--ip', required=True, type=IPADDRESS,
              help="ip address to edit")
@click.option('address', '--newip', type=IPADDRESS, help="new ip-addr")
@click.option('--system', help="assign ip to this system")
@click.option('--owner', help="owner login")
@click.option('--project', help="project owning ip address")
@click.option('--desc', help="free form field describing address")
def ip_edit(subnet, cur_address, **kwargs):
    """
    change properties of an existing ip address
    """
    # system must be validated
    if kwargs['system']:
        kwargs['system'] = NAME.convert(kwargs['system'], None, None)

    client = Client()
    fetch_and_update(
        client.IpAddresses,
        {'address': cur_address, 'subnet': subnet},
        'ip address not found.',
        kwargs)
    click.echo('Item successfully updated.')
# ip_edit()

@click.command(name='ip-export')
@click.option('address', '--ip', type=IPADDRESS,
              help='filter by ip address')
@click.option('--system', type=NAME,
              help="filter by ips assigned to this system")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
@click.option('--subnet', type=SUBNET, help='filter by subnet')
def ip_export(**kwargs):
    """
    export data in CSV format
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'address': False}

    click.echo('preparing data, this might take some time ... (specially if '
               'no filters were specified)', err=True)
    result = client.IpAddresses.bulk(**parsed_filter)
    click.echo(result, nl=False)
# ip_export()

@click.command(name='ip-import')
@click.pass_context
@click.option('--commit', is_flag=True, default=False,
              help='commit changes to database (USE WITH CARE)')
@click.option('file_content', '--file', type=click.File('r'), required=True,
              help="csv file")
@click.option('--verbosity', type=VERBOSITY_LEVEL,
              help='output verbosity level')
@click.option('force', '--yes', is_flag=True, default=False,
              help='answer yes to confirmation question')
def ip_import(ctx, **kwargs):
    """
    submit a job for importing data in CSV format
    """
    # pass down the job commands used
    ctx.obj = {'CANCEL': job_cancel, 'OUTPUT': job_output}
    kwargs['resource_type'] = 'ip'
    submit_csv_job(Client(), ctx, **kwargs)
# ip_import()

@click.command(name='ip-list')
@click.option('address', '--ip', type=IPADDRESS,
              help='filter by ip address')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--my', help="show only my own ips", is_flag=True,
              default=False)
@click.option('--system', type=NAME, help="list ips assigned to this system")
@click.option('--owner', help="filter by specified owner login")
@click.option('--project', help="filter by specified project")
@click.option('--subnet', type=SUBNET, help='the subnet to list')
def ip_list(**kwargs):
    """
    list the registered ip addresses
    """
    # fetch data from server
    client = Client()

    long_info = kwargs.pop('long_info')
    only_mine = kwargs.pop('my')
    if only_mine:
        kwargs.update({'owner': CONF.get_login()})

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'address': False}
    entries = client.IpAddresses.instances(**parsed_filter)

    # present results
    if long_info:
        print_items(FIELDS, client.IpAddresses, None, entries, PrintMode.LONG)
    else:
        print_items(FIELDS_TABLE, client.IpAddresses, None, entries,
                    PrintMode.TABLE)
# ip_list()

CMDS = [ip_add, ip_del, ip_edit, ip_export, ip_import, ip_list]
