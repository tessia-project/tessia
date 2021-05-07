# Copyright 2021 IBM Corp.
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
Module for the HMC monitoring commands
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import PrintMode
from tessia.cli.types import HOSTNAME

import click

#
# CONSTANTS AND DEFINITIONS
#
TYPE_FIELDS_HMC = ('name', 'status', 'cpc_status', 'last_update')
TYPE_FIELDS_CPC = ('cpc_status', 'name', 'last_update')


#
# CODE
#


@click.command(name='status')
@click.option('--name', '--hmc', type=HOSTNAME,
              help="filter by HMC host name")
@click.option('--cpc', type=HOSTNAME,
              help="filter by CPC host name")
def status(**kwargs):
    """
    List hmc status.
    """
    # fetch data from server
    client = Client()

    check_cpc = kwargs.pop('cpc')

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'name': False}
    entries = client.HmcCanary.instances(**parsed_filter)

    # find CPC by name, if specified
    entries_by_cpc = []
    is_found = False
    if check_cpc is not None:
        for hmc_entry in entries:
            fields = [field for field in getattr(hmc_entry, 'cpc_status')
                      if field['name'] == check_cpc]
            if fields:
                is_found = True
                entries_by_cpc.append(hmc_entry)
            setattr(hmc_entry, 'cpc_status', fields)

    if is_found is False and check_cpc is not None:
        click.echo("No results were found.")
        return

    def parse_cpc(cpcs):
        """Helper function to format output."""
        parsed_cpcs = []
        for cpc in cpcs:
            parsed_cpcs.append('[{}: {}]'.format(cpc['name'], cpc['status']))
        return ", ".join(parsed_cpcs)
    # parse_cpc()

    parser_map = {
        'cpc_status': parse_cpc,
    }

    if check_cpc is None:
        print_items(TYPE_FIELDS_HMC, client.HmcCanary, parser_map, entries,
                    PrintMode.LONG)
    else:
        print_items(TYPE_FIELDS_CPC, client.HmcCanary, parser_map,
                    entries_by_cpc, PrintMode.LONG)
# status()

CMDS = [status]
