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
from tessia_cli.client import Client
from tessia_cli.utils import fetch_item

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
@click.option(
    'target', '--to', required=True,
    help="target profile system-name/profile-name")
@click.option(
    '--vol', required=True,
    help='storage-server/volume-id')
def vol_attach(target, vol):
    """
    attach a storage volume to a system activation profile
    """
    try:
        system_name, profile_name = target.split('/', 1)
    except:
        raise click.ClickException('invalid format for profile')
    try:
        server_name, vol_id = vol.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume')

    # fetch data from server
    client = Client()

    prof_obj = fetch_item(
        client.SystemProfiles,
        {'system': system_name, 'name': profile_name},
        'no profile found.'
    )
    vol_obj = fetch_item(
        client.StorageVolumes,
        {'server': server_name, 'volume_id': vol_id},
        'no storage volume found.'
    )

    # perform operation
    prof_obj.vol_attach({'unique_id': vol_obj.unique_id})
    click.echo('Volume attached successfully.')
# vol_attach()

@click.command(
    name='vol-detach',
    short_help='detach a storage volume from a system activation profile')
@click.option(
    'profile', '--from', required=True,
    help="from profile system-name/profile-name")
@click.option(
    '--vol', required=True,
    help='storage-server/volume-id')
def vol_detach(profile, vol):
    """
    detach a storage volume from a system activation profile
    """
    try:
        system_name, profile_name = profile.split('/', 1)
    except:
        raise click.ClickException('invalid format for profile')
    try:
        server_name, vol_id = vol.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume')

    # fetch data from server
    client = Client()

    prof_obj = fetch_item(
        client.SystemProfiles,
        {'system': system_name, 'name': profile_name},
        'no profile found.'
    )
    vol_obj = fetch_item(
        client.StorageVolumes,
        {'server': server_name, 'volume_id': vol_id},
        'no storage volume found.'
    )

    # since the lib does not support to pass the unique id on the url for a
    # instance we need to use the class method directly
    client.SystemProfiles.vol_detach(
        vol_unique_id=vol_obj.unique_id, id=prof_obj.id)
    click.echo('Volume detached successfully.')
# vol_detach()

CMDS = [vol_attach, vol_detach]
