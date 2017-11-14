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
Module for the vol (system volumes) command
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.types import NAME
from tessia.cli.types import VOLUME_ID
from tessia.cli.utils import fetch_item

import click

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

@click.command(
    name='vol-attach',
    short_help='attach a storage volume to a system activation profile')
@click.option('--system', required=True, help='target system')
@click.option('--profile', required=True, type=NAME,
              help='target activation profile')
@click.option('--server', required=True,
              help='storage server containing volume')
@click.option('--vol', required=True, type=VOLUME_ID, help='volume id')
def vol_attach(system, profile, server, vol):
    """
    attach a storage volume to a system activation profile
    """
    # fetch data from server
    client = Client()

    prof_obj = fetch_item(
        client.SystemProfiles,
        {'system': system, 'name': profile},
        'no profile found.'
    )
    vol_obj = fetch_item(
        client.StorageVolumes,
        {'server': server, 'volume_id': vol},
        'no storage volume found.'
    )

    # perform operation
    prof_obj.vol_attach({'unique_id': vol_obj.unique_id})
    click.echo('Volume attached successfully.')
# vol_attach()

@click.command(
    name='vol-detach',
    short_help='detach a storage volume from a system activation profile')
@click.option('--system', required=True, help='target system')
@click.option('--profile', required=True, type=NAME,
              help='target activation profile')
@click.option('--server', required=True,
              help='storage server containing volume')
@click.option('--vol', required=True, type=VOLUME_ID, help='volume id')
def vol_detach(system, profile, server, vol):
    """
    detach a storage volume from a system activation profile
    """
    # fetch data from server
    client = Client()

    prof_obj = fetch_item(
        client.SystemProfiles,
        {'system': system, 'name': profile},
        'no profile found.'
    )
    vol_obj = fetch_item(
        client.StorageVolumes,
        {'server': server, 'volume_id': vol},
        'no storage volume found.'
    )

    # since the lib does not support to pass the unique id on the url for a
    # instance we need to use the class method directly
    client.SystemProfiles.vol_detach(
        vol_unique_id=vol_obj.unique_id, id=prof_obj.id)
    click.echo('Volume detached successfully.')
# vol_detach()

CMDS = [vol_attach, vol_detach]
