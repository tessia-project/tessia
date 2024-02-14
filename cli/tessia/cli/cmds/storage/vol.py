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
from tessia.cli.config import CONF
from tessia.cli.cmds.job.job import cancel as job_cancel
from tessia.cli.cmds.job.job import output as job_output
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import print_ver_table
from tessia.cli.output import PrintMode
from tessia.cli.types import CustomIntRange, DEVNO, FCP_PATH, MIB_SIZE, NAME, \
    SCSI_WWID, VERBOSITY_LEVEL, NVME_WWN, VOLUME_ID
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_item
from tessia.cli.utils import size_to_str
from tessia.cli.utils import submit_csv_job

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

FIELDS_TABLE = (
    'volume_id', 'server', 'size', 'type', 'system', 'owner', 'project',
    'system_profiles'
)

PART_FIELDS = (
    'number', 'size', 'type', 'filesystem', 'mount point', 'mount options'
)

SIZE_HELP = ("an integer followed by one of the units KB, MB, GB, "
             "TB, KiB, MiB, GiB, TiB")

TYPE_FIELDS = (
    'name', 'desc'
)

# error messages when fetching a volume
VOL_NOT_FOUND_MSG = 'volume not found.'
VOL_MULTI_MSG = ('multiple volumes match the entered ID, specify the storage '
                 'server with --server')

WRONG_USAGE_FCP_PARAM = (
    "FCP parameters can't be applied to a non FCP disk."
)
WRONG_USAGE_NVME_PARAM = (
    "NVME parameters can't be applied to a non NVME disk."
)
#
# CODE
#

def _fetch_vol(vol_id, server):
    """
    Helper to fetch a volume from the server
    """
    client = Client()
    search_params = {'volume_id': vol_id}
    if server:
        search_params['server'] = server
    item = fetch_item(
        client.StorageVolumes, search_params,
        VOL_NOT_FOUND_MSG, VOL_MULTI_MSG)
    return item
# _fetch_vol()

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
@click.option('--server', type=NAME, help='target storage server')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
@click.option('--size', type=MIB_SIZE, help=SIZE_HELP)
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
    item = _fetch_vol(volume_id, server)
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

@click.command(name='part-clear')
@click.option('--server', type=NAME, help='storage server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
def part_clear(server, volume_id):
    """
    clear (remove) a volume's partition table
    """
    item = _fetch_vol(volume_id, server)
    item.update({'part_table': None})

    click.echo('partition table cleared; to initialize it, use the part-init '
               'command.')
# part_clear()

@click.command(
    name='part-del',
    # short help is needed to avoid truncation
    short_help="Remove a partition from volume's partition table")
@click.option('--server', type=NAME, help='storage server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
@click.option('--num', required=True, type=CustomIntRange(min=1),
              help="partition's number to delete")
def part_del(server, volume_id, num):
    """
    remove a partition from volume's partition table
    """
    item = _fetch_vol(volume_id, server)
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
@click.option('--server', type=NAME, help='storage server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
@click.option('--num', type=CustomIntRange(min=1), required=True,
              help="partition's number to edit")
@click.option('--size', type=MIB_SIZE, help=SIZE_HELP)
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
            if not value and isinstance(value, str):
                value = None
            parsed_args[key] = value
    if not parsed_args:
        raise click.ClickException('nothing to update.')

    item = _fetch_vol(volume_id, server)
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
@click.option('--server', type=NAME, help='storage server containing volume')
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

    item = _fetch_vol(volume_id, server)
    item.update({'part_table': part_table})

    click.echo('Partition table successfully initialized.')
# part_init()

@click.command(name='part-list')
@click.option('--server', type=NAME, help='storage server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help="volume id")
def part_list(server, volume_id):
    """
    print the volume's partition table
    """
    item = _fetch_vol(volume_id, server)

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
@click.option('--server', type=NAME, required=True,
              help='target storage server')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help='volume id')
@click.option('--size', type=MIB_SIZE, help=SIZE_HELP)
@click.option('--type', required=True, help="volume type (see vol-types)")
@click.option('--system', type=NAME, help="assign volume to this system")
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
@click.option('--wwn', type=NVME_WWN,
              help='NVME world wide name (NVMe only)')
def vol_add(**kwargs):
    """
    create a new storage volume
    """
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

        elif key == 'wwn':
            if item['type'] != 'NVME':
                raise click.ClickException(WRONG_USAGE_NVME_PARAM)
            item['specs']['wwn'] = value

        else:
            setattr(item, key, value)

    if item['type'] == 'HPAV':
        item['volume_id'] = DEVNO.convert(kwargs['volume_id'], None, None)
        if 'size' in item:
            raise click.ClickException('HPAV type does not support --size')
        item['size'] = 0
    elif not 'size' in item:
        raise click.UsageError('Missing option "--size".')

    # check the availability of required NVME parameters
    if item['type'] == 'NVME':
        # wwn not specified: report error
        if 'wwn' not in item['specs']:
            raise click.ClickException('--wwn must be specified')

    # check the availability of required FCP parameters
    if item['type'] == 'FCP':
        # multipath not specified: activate by default
        if 'multipath' not in item['specs']:
            item['specs']['multipath'] = True

        # wwid or no fcp path specified: report error
        if 'wwid' not in item['specs']:
            raise click.ClickException('--wwid must be specified')
        if 'adapters' not in item['specs']:
            click.echo(
                'Note: there are no paths to this volume.'
                ' FCP volumes without configured paths'
                ' may be inaccessible.'
                )
    item.save()
    click.echo('Item added successfully.')
# vol_add()

@click.command(name='vol-del')
@click.option('--server', type=NAME, help='server containing volume')
@click.option('volume_id', '--id', required=True, type=VOLUME_ID,
              help='volume id')
def vol_del(server, volume_id):
    """
    remove an existing storage volume
    """
    client = Client()

    search_params = {'volume_id': volume_id}
    if server:
        search_params['server'] = server
    fetch_and_delete(client.StorageVolumes, search_params,
                     VOL_NOT_FOUND_MSG, VOL_MULTI_MSG)
    click.echo('Item successfully deleted.')
# vol_del()

@click.command(
    'vol-edit',
    short_help='change properties of an existing storage volume')
@click.option('--server', type=NAME, help='server containing volume')
@click.option('cur_id', '--id', required=True, type=VOLUME_ID,
              help='volume id')
@click.option('volume_id', '--newid', type=VOLUME_ID,
              help="new volume's id in form volume-id")
@click.option('--size', type=MIB_SIZE, help=SIZE_HELP)
@click.option('--system', help="assign volume to this system")
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
@click.option('--wwn', type=NVME_WWN,
              help='NVME world wide name (NVMe only)')
def vol_edit(server, cur_id, **kwargs):
    """
    change properties of an existing storage volume
    """
    item = _fetch_vol(cur_id, server)
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
                click.echo(
                    'Note: there are no more paths to this volume.'
                    ' FCP volumes without configured paths'
                    ' may be inaccessible.'
                    )

        elif key == 'wwid':
            if item['type'] != 'FCP':
                raise click.ClickException(WRONG_USAGE_FCP_PARAM)

            # add the necessary key to the update dict in case they are not
            # there yet
            update_dict.setdefault('specs', item.specs)
            update_dict['specs']['wwid'] = value

        elif key == 'wwn':
            if item['type'] != 'NVME':
                raise click.ClickException(WRONG_USAGE_NVME_PARAM)

            # add the necessary key to the update dict in case they are not
            # there yet
            update_dict.setdefault('specs', item.specs)
            update_dict['specs']['wwn'] = value

        # system must be validated
        elif key == 'system':
            if value:
                update_dict[key] = NAME.convert(value, None, None)
            else:
                update_dict[key] = None

        # normal arg: just add to the dict
        else:
            update_dict[key] = value

    if item['type'] == 'HPAV':
        if 'size' in update_dict:
            raise click.ClickException('HPAV type does not support --size')
        if 'volume_id' in update_dict:
            update_dict['volume_id'] = DEVNO.convert(
                update_dict['volume_id'], None, None)

    if not update_dict:
        raise click.ClickException('no update criteria provided.')
    item.update(**update_dict)

    click.echo('Item successfully updated.')
# vol_edit()

@click.command(name='vol-export')
@click.option('--server', type=NAME, help='filter by storage server')
@click.option('volume_id', '--id', type=VOLUME_ID, help='filter by volume id')
@click.option('--owner', help="filter by specified owner login")
@click.option('--pool', help="list volumes assigned to this pool")
@click.option('--project', help="filter by specified project")
@click.option('--system', type=NAME,
              help="list volumes assigned to this system")
@click.option('--type', help="filter by specified volume type")
def vol_export(**kwargs):
    """
    export data in CSV format
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'volume_id': False}

    click.echo('preparing data, this might take some time ... (specially if '
               'no filters were specified)', err=True)
    result = client.StorageVolumes.bulk(**parsed_filter)
    click.echo(result, nl=False)
# vol_export()

@click.command(name='vol-import')
@click.pass_context
@click.option('--commit', is_flag=True, default=False,
              help='commit changes to database (USE WITH CARE)')
@click.option('file_content', '--file', type=click.File('r'), required=True,
              help="csv file")
@click.option('--verbosity', type=VERBOSITY_LEVEL,
              help='output verbosity level')
@click.option('force', '--yes', is_flag=True, default=False,
              help='answer yes to confirmation question')
def vol_import(ctx, **kwargs):
    """
    submit a job for importing data in CSV format
    """
    # pass down the job commands used
    ctx.obj = {'CANCEL': job_cancel, 'OUTPUT': job_output}
    kwargs['resource_type'] = 'svol'
    submit_csv_job(Client(), ctx, **kwargs)
# vol_import()

@click.command(name='vol-list')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--my', help="show only my own volumes", is_flag=True,
              default=False)
@click.option('--server', type=NAME, help='filter by storage server')
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
    # fetch data from server
    client = Client()

    long_info = kwargs.pop('long_info')
    only_mine = kwargs.pop('my')
    if only_mine:
        kwargs.update({'owner': CONF.get_login()})
    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'volume_id': False}
    entries = client.StorageVolumes.instances(**parsed_filter)
    parser_map = {'size': size_to_str,
                  'system_profiles':
                  lambda prof_list: ', '.join(
                      ['[{}]'.format(prof.name) for prof in prof_list]),
                 }
    # present results
    if long_info:
        print_items(FIELDS, client.StorageVolumes, parser_map, entries,
                    PrintMode.LONG)
    else:
        print_items(FIELDS_TABLE, client.StorageVolumes, parser_map, entries,
                    PrintMode.TABLE)

# vol_list()

@click.command(name='vol-types')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
def vol_types(**kwargs):
    """
    list the supported volume types
    """
    # fetch data from server
    client = Client()
    entries = client.VolumeTypes.instances()

    # present results
    if kwargs.pop('long_info'):
        print_items(TYPE_FIELDS, client.VolumeTypes, None, entries,
                    PrintMode.LONG)
    else:
        print_items(TYPE_FIELDS, client.VolumeTypes, None, entries,
                    PrintMode.TABLE)

# vol_types()

CMDS = [
    vol_add, vol_del, vol_edit, vol_export, vol_import, vol_list, vol_types,
    part_add, part_clear, part_del, part_edit, part_init, part_list
]
