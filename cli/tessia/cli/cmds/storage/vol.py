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
Module for the vol (storage volumes) commands
"""

#
# IMPORTS
#
from collections import namedtuple
from tessia.cli.client import Client
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import print_ver_table
from tessia.cli.types import CustomIntRange, FCP_PATH, MIB_SIZE, NAME, \
    SCSI_WWID, VOLUME_ID
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_item
from tessia.cli.utils import size_to_str
from tessia.cli.utils import str_to_size

import click

#
# CONSTANTS AND DEFINITIONS
#
EMPTY_PART_MSG = (
    'partition table undefined; initialize it with the part-init '
    'command.')

FIELDS = (
    'volume_id', 'server', 'size', 'specs', 'type', 'system',
    'system_attributes', 'system_profiles', 'pool', 'owner', 'project',
    'modified', 'modifier', 'desc'
)
PART_FIELDS = (
    'number', 'size', 'type', 'filesystem', 'mount point', 'mount options'
)
TYPE_FIELDS = (
    'name', 'desc'
)

WRONG_USAGE_FCP_PARAM = (
    "FCP parameters can't be applied to a non FCP disk."
)

#
# CODE
#

def _process_fcp_path(prop_dict, value):
    """
    Validate a list of fcp paths and add them to the item's properties
    dictionary.

    Args:
        prop_dict (dict): item's properties
        value (list): fcp paths in the form [(devno, wwpn)]
    """
    # add the adapters list to the prop dict in case it's not
    # there yet
    prop_dict['specs'].setdefault('adapters', [])

    for devno, wwpn in value:

        # find the entry with the corresponding devno
        adapter_entry = None
        for check_entry in prop_dict['specs']['adapters']:
            if check_entry.get('devno') == devno:
                adapter_entry = check_entry
                break

        # adapter entry does not exist yet: create one
        if adapter_entry is None:
            adapter_entry = {
                'devno': devno,
                'wwpns': [wwpn]
            }
            prop_dict['specs']['adapters'].append(adapter_entry)
        # adapter entry found: verify if it contains wwpn
        else:
            adapter_entry.setdefault('wwpns', [])
            # wwpn not listed yet: add it
            if wwpn not in adapter_entry['wwpns']:
                adapter_entry['wwpns'].append(wwpn)
# _process_fcp_path()

# partition table related functions
@click.command(name='part-add')
@click.option('--server', required=True, help='target storage server')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
@click.option('--size', type=MIB_SIZE, help="size (i.e. 500mib)")
@click.option('--fs', required=True, help="filesystem type")
@click.option('--mo', default=None, help="mount options")
@click.option('--mp', default=None, help="mount point")
@click.option(
    '--type', default='primary', type=click.Choice(['primary', 'logical']),
    help="partition type (only affects msdos type)")
def part_add(server, volume_id, **kwargs):
    """
    add a partition to volume's partition table
    """
    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')
    part_table = item.part_table
    if (not isinstance(part_table, dict) or not
            isinstance(part_table.get('table'), list)):
        raise click.ClickException(EMPTY_PART_MSG)

    free_size = item.size - sum([part['size'] for part in part_table['table']])
    # size not specified: use available free space if available
    if not kwargs['size']:
        if free_size < 1:
            raise click.ClickException(
                'no available free size to create the partition')
        kwargs['size'] = free_size
    # size specified bigger than available free space: report error
    elif kwargs['size'] > free_size:
        raise click.ClickException(
            'size specified is bigger than available free space {}MiB'
            .format(free_size))

    part_table['table'].append(kwargs.copy())

    item.update({'part_table': part_table})
    click.echo('Partition successfully added.')
# part_add()

@click.command(
    name='part-del',
    # short help is needed to avoid truncation
    short_help="Remove a partition from volume's partition table")
@click.option('--server', required=True,
              help='storage server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
@click.option('--num', required=True, type=CustomIntRange(min=1),
              help="partition's number to delete")
def part_del(server, volume_id, num):
    """
    remove a partition from volume's partition table
    """
    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')
    part_table = item.part_table

    try:
        part_table['table'].pop(num-1)
    except (AttributeError, TypeError):
        raise click.ClickException(EMPTY_PART_MSG)
    except (IndexError, KeyError):
        raise click.ClickException('specified partition not found')

    item.update({'part_table': part_table})
    click.echo('Partition successfully deleted.')
# part_del()

@click.command(name='part-edit')
@click.option('--server', required=True,
              help='storage server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
@click.option('--num', type=CustomIntRange(min=1), required=True,
              help="partition's number to edit")
@click.option('--size', type=MIB_SIZE, help="size (i.e. 500mib)")
@click.option('--fs', help="filesystem")
@click.option('--mo', help="mount options")
@click.option('--mp', help="mount point")
@click.option(
    '--type', type=click.Choice(['primary', 'logical']),
    help="partition type (no effect for gpt)")
def part_edit(server, volume_id, num, **kwargs):
    """
    edit partition properties
    """
    parsed_args = {}
    for key, value in kwargs.items():
        if value is not None:
            # empty value: convert to None to allow field to be unset
            if value == '':
                value = None
            parsed_args[key] = value
    if not parsed_args:
        raise click.ClickException('nothing to update.')

    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')
    part_table = item.part_table

    try:
        part_table['table'][num-1].update(parsed_args)
    except (AttributeError, TypeError):
        raise click.ClickException(EMPTY_PART_MSG)
    except (KeyError, IndexError):
        raise click.ClickException('specified partition not found')

    item.update({'part_table': part_table})
    click.echo('Partition successfully updated.')
# part_edit()

@click.command(name='part-init')
@click.option('--server', required=True,
              help='storage server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
@click.option(
    '--label', required=True, type=click.Choice(['dasd', 'gpt', 'msdos']),
    help="partition table type")
def part_init(server, volume_id, label):
    """
    initialize the volume's partition table
    """
    part_table = {'type': label, 'table': []}

    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')

    item.update({'part_table': part_table})

    click.echo('Partition table successfully initialized.')
# part_init()

@click.command(name='part-list')
@click.option('--server', required=True,
              help='storage server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
def part_list(server, volume_id, **kwargs):
    """
    print the volume's partition table
    """
    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')

    part_table = item.part_table
    if (not isinstance(part_table, dict) or not
            isinstance(part_table.get('table'), list)):
        raise click.ClickException(EMPTY_PART_MSG)

    rows = []
    table_list = part_table.get('table', [])
    fields_map = ['number', 'size', 'type', 'fs', 'mp', 'mo']
    part_table_cls = namedtuple('PartTable', fields_map)
    for index, part in enumerate(table_list):
        row = part_table_cls(
            number=index+1,
            size=size_to_str(part.get('size', 0)),
            type=part.get('type', ''),
            fs=part.get('fs', ''),
            mp=part.get('mp', ''),
            mo=part.get('mo', ''),
        )
        rows.append(row)

    click.echo('\nPartition table type: {}'.format(
        part_table.get('type', 'undefined')))
    print_ver_table(PART_FIELDS, rows, fields_map)
# part_list()

@click.command('vol-add')
# set the parameter name after the model's attribute name to save on typing
@click.option('--server', required=True, help='target storage server')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help='volume id')
@click.option('--size', required=True, help="volume size (i.e. 10gb)")
@click.option('--type', required=True, help="volume type (see vol-types)")
@click.option('--owner', help="owner login")
@click.option('--project', help="project owning volume")
@click.option('--desc', help="free form field describing volume")
# options specific to FCP type
@click.option('--mpath', type=click.BOOL,
              help="enable/disable multipath (FCP only)")
@click.option('--path', multiple=True, type=FCP_PATH,
              help='add a FCP path (FCP only)')
@click.option('--wwid', type=SCSI_WWID,
              help='scsi world wide identifier (FCP only)')
def vol_add(**kwargs):
    """
    create a new storage volume
    """
    # convert a human size to integer
    try:
        kwargs['size'] = str_to_size(kwargs['size'])
    except ValueError:
        raise click.ClickException('invalid size specified.')

    client = Client()
    item = client.StorageVolumes()

    item.attributes = {}
    setattr(item, 'specs', {})
    setattr(item, 'system_attributes', {})
    setattr(item, 'type', kwargs['type'])

    for key, value in kwargs.items():
        # option was not specified: skip it
        if value is None:
            continue

        # process multipath arg
        if key == 'mpath':
            if item['type'] != 'FCP':
                raise click.ClickException(WRONG_USAGE_FCP_PARAM)
            item['specs']['multipath'] = kwargs['mpath']

        # process add fcp path arg
        elif key == 'path':
            # option was not specified: skip it
            if not value:
                continue

            if item['type'] != 'FCP':
                raise click.ClickException(WRONG_USAGE_FCP_PARAM)

            _process_fcp_path(item, value)

        # process wwid arg
        elif key == 'wwid':
            if item['type'] != 'FCP':
                raise click.ClickException(WRONG_USAGE_FCP_PARAM)
            item['specs']['wwid'] = value

        else:
            setattr(item, key, value)

    # check the availability of required FCP parameters
    if item['type'] == 'FCP':
        # multipath not specified: activate by default
        if 'multipath' not in item['specs']:
            item['specs']['multipath'] = True

        # wwid or no fcp path specified: report error
        if 'wwid' not in item['specs'] or 'adapters' not in item['specs']:
            raise click.ClickException('both --path and --wwid must be '
                                       'specified')
    item.save()
    click.echo('Item added successfully.')
# vol_add()

@click.command(name='vol-del')
@click.option('--server', required=True, help='server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help='volume id')
def vol_del(**kwargs):
    """
    remove an existing storage volume
    """
    client = Client()

    fetch_and_delete(
        client.StorageVolumes,
        kwargs,
        'volume not found.'
    )
    click.echo('Item successfully deleted.')
# vol_del()

@click.command(
    'vol-edit',
    short_help='change properties of an existing storage volume')
@click.option('--server', required=True, help='server containing volume')
@click.option('cur_id', '--id', required=True, type=VOLUME_ID,
              help='volume id')
# set the parameter name after the model's attribute name to save on typing
@click.option('volume_id', '--newid', type=VOLUME_ID,
              help="new volume's id in form volume-id")
@click.option('--size',
              help="volume size (i.e. 10gb)")
@click.option('--owner', help="owner login")
@click.option('--project', help="project owning volume")
@click.option('--desc', help="free form field describing volume")
# options specific to FCP type
@click.option('--mpath', type=click.BOOL,
              help="enable/disable multipath (FCP only)")
@click.option(
    '--addpath', multiple=True, type=FCP_PATH,
    help='add a FCP path (FCP only)')
@click.option(
    '--delpath', multiple=True, type=FCP_PATH,
    help='delete a FCP path (FCP only)')
@click.option(
    '--wwid', type=SCSI_WWID,
    help='scsi world wide identifier (FCP only)')
def vol_edit(server, cur_id, **kwargs):
    """
    change properties of an existing storage volume
    """
    try:
        kwargs['size'] = str_to_size(kwargs['size'])
    except ValueError:
        raise click.ClickException('invalid size specified.')

    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': cur_id, 'server': server},
        'volume not found.'
    )
    update_dict = {}

    for key, value in kwargs.items():

        # option was not specified: skip it
        if value is None:
            continue

        # process multipath arg
        if key == 'mpath':
            if item['type'] != 'FCP':
                raise click.ClickException(WRONG_USAGE_FCP_PARAM)

            update_dict.setdefault('specs', item.specs)
            update_dict['specs']['multipath'] = kwargs['mpath']

        # process add fcp path arg
        elif key == 'addpath':
            # option was not specified: skip it
            if not value:
                continue

            if item['type'] != 'FCP':
                raise click.ClickException(WRONG_USAGE_FCP_PARAM)

            # add the key in case it's not there yet
            update_dict.setdefault('specs', item.specs)

            _process_fcp_path(update_dict, value)

        elif key == 'delpath':
            # option was not specified: skip it
            if not value:
                continue

            if item['type'] != 'FCP':
                raise click.ClickException(WRONG_USAGE_FCP_PARAM)

            # add the necessary keys to the update dict in case they are not
            # there yet
            update_dict.setdefault('specs', item.specs)
            update_dict['specs'].setdefault('adapters', [])

            for devno, wwpn in value:
                index = -1
                for i in range(0, len(update_dict['specs']['adapters'])):
                    check_entry = update_dict['specs']['adapters'][i]
                    if check_entry.get('devno') == devno:
                        index = i
                        break
                # adapter not found: nothing to do
                if index == -1:
                    continue

                adapter_entry = update_dict['specs']['adapters'][index]
                try:
                    adapter_entry.get('wwpns', []).remove(wwpn)
                except ValueError:
                    continue

                # no more wwpns listed: remove adapter entry
                if not adapter_entry['wwpns']:
                    update_dict['specs']['adapters'].pop(index)
            # at least one path must be available
            if not update_dict['specs']['adapters']:
                raise click.ClickException(
                    'fcp volume must have at least one path')

        elif key == 'wwid':
            if item['type'] != 'FCP':
                raise click.ClickException(WRONG_USAGE_FCP_PARAM)

            # add the necessary key to the update dict in case they are not
            # there yet
            update_dict.setdefault('specs', item.specs)
            update_dict['specs']['wwid'] = value

        # normal arg: just add to the dict
        else:
            update_dict[key] = value

    if not update_dict:
        raise click.ClickException('no update criteria provided.')
    item.update(**update_dict)

    click.echo('Item successfully updated.')
# vol_edit()

@click.command(name='vol-list')
# set the parameter name after the model's attribute name to save on typing
@click.option('--server', help='the storage server to list')
@click.option('volume_id', '--id', type=VOLUME_ID, help='filter by volume id')
@click.option('--owner', help="filter by specified owner login")
@click.option('--pool', help="list volumes assigned to this pool")
@click.option('--project', help="filter by specified project")
@click.option('--system', type=NAME,
              help="list volumes assigned to this system")
@click.option('--type', help="filter by specified volume type")
def vol_list(**kwargs):
    """
    list registered storage volumes
    """
    # at least one qualifier must be specified so that we don't have to
    # retrieve the full list
    if kwargs['server'] is None and kwargs['volume_id'] is None:
        raise click.ClickException(
            'at least one of --server or --id must be specified')

    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.StorageVolumes.instances(**parsed_filter)

    # present results
    print_items(
        FIELDS,
        client.StorageVolumes,
        {'size': size_to_str,
         'system_profiles':
         lambda prof_list: ', '.join(
             ['[{}]'.format(prof.name) for prof in prof_list]),
        },
        entries
    )

# vol_list()

@click.command(name='vol-types')
def vol_types():
    """
    list the supported volume types
    """
    # fetch data from server
    client = Client()
    entries = client.VolumeTypes.instances()

    # present results
    print_items(
        TYPE_FIELDS, client.VolumeTypes, None, entries)

# vol_types()

CMDS = [
    vol_add, vol_del, vol_edit, vol_list, vol_types, part_add, part_del,
    part_edit, part_init, part_list
]
