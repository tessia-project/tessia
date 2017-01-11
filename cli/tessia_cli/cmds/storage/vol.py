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
from tessia_cli.client import Client
from tessia_cli.filters import dict_to_filter
from tessia_cli.output import print_items
from tessia_cli.output import print_ver_table
from tessia_cli.utils import fetch_and_delete
from tessia_cli.utils import fetch_and_update
from tessia_cli.utils import fetch_item
from tessia_cli.utils import size_to_str
from tessia_cli.utils import str_to_size

import click

#
# CONSTANTS AND DEFINITIONS
#
FIELDS = (
    'volume_id', 'server', 'size', 'specs', 'type', 'system',
    'system_profiles', 'pool', 'owner', 'project', 'modified', 'modifier',
    'desc'
)
PART_FIELDS = (
    'number', 'size', 'type', 'filesystem', 'mount point', 'mount options'
)
TYPE_FIELDS = (
    'name', 'desc'
)

#
# CODE
#

# partition table related functions
@click.command(name='part-add')
@click.option('volume_id', '--id', required=True,
              help="volume id in the form server-name/volume-id")
@click.option('--size', required=True, help="size (i.e. 500mb)")
@click.option('--fs', default='', help="filesystem")
@click.option('--mo', default='', help="mount options")
@click.option('--mp', default='', help="mount point")
@click.option(
    '--type', default='primary', type=click.Choice(['primary', 'logical']),
    help="partition type (no effect for gpt)")
def part_add(volume_id, **kwargs):
    """
    add a partition to volume's partition table
    """
    # break name parts
    try:
        server, volume_id = volume_id.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume id')
    try:
        kwargs['size'] = str_to_size(kwargs['size'])
    except ValueError:
        raise click.ClickException('invalid size specified.')

    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')
    part_table = item.part_table
    if (not isinstance(part_table, dict) or not
            isinstance(part_table.get('table'), list)):
        part_table = {'type': 'msdos', 'table': kwargs.copy()}
    else:
        part_table['table'] = part_table.get('table', [])
        part_table['table'].append(kwargs.copy())

    item.update({'part_table': part_table})
    click.echo('Partition successfully added.')
# part_add()

@click.command(
    name='part-del',
    # short help is needed to avoid truncation
    short_help="Remove a partition from volume's partition table")
@click.option('volume_id', '--id', required=True,
              help="volume id in the form server-name/volume-id")
@click.option('--num', required=True, type=click.IntRange(min=1),
              help="partition's number to delete")
def part_del(volume_id, num):
    """
    remove a partition from volume's partition table
    """
    # break name parts
    try:
        server, volume_id = volume_id.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume id')

    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')
    part_table = item.part_table

    try:
        part_table['table'].pop(num-1)
    except AttributeError:
        raise click.ClickException(
            'partition table undefined; initialize it with the part-init '
            'command.')
    except (IndexError, KeyError):
        raise click.ClickException('specified partition not found')

    item.update({'part_table': part_table})
    click.echo('Partition successfully deleted.')
# part_del()

@click.command(name='part-edit')
@click.option('volume_id', '--id', required=True,
              help="volume id in the form server-name/volume-id")
@click.option('--num', type=click.IntRange(min=1), required=True,
              help="partition's number to edit")
@click.option('--size', help="size (i.e. 500mb)")
@click.option('--fs', help="filesystem")
@click.option('--mo', help="mount options")
@click.option('--mp', help="mount point")
@click.option(
    '--type', default='primary', type=click.Choice(['primary', 'logical']),
    help="partition type (no effect for gpt)")
def part_edit(volume_id, num, **kwargs):
    """
    edit partition properties
    """
    # break name parts
    try:
        server, volume_id = volume_id.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume id')
    try:
        kwargs['size'] = str_to_size(kwargs['size'])
    except ValueError:
        raise click.ClickException('invalid size specified.')

    parsed_args = {}
    for key, value in kwargs.items():
        if value is not None:
            parsed_args[key] = value
    if len(parsed_args) == 0:
        raise click.ClickException('nothing to update.')

    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')
    part_table = item.part_table

    try:
        part_table['table'][num-1].update(parsed_args)
    except AttributeError:
        raise click.ClickException(
            'partition table undefined; initialize it with the part-init '
            'command.')
    except (KeyError, IndexError):
        raise click.ClickException('specified partition not found')

    item.update({'part_table': part_table})
    click.echo('Partition successfully updated.')
# part_edit()

@click.command(name='part-init')
@click.option('volume_id', '--id', required=True,
              help="volume id in the form server-name/volume-id")
@click.option('--label', required=True, type=click.Choice(['msdos', 'gpt']),
              help="partition table type (i.e. msdos, gpt)")
def part_init(volume_id, label):
    """
    initialize the volume's partition table
    """
    # break name parts
    try:
        server, volume_id = volume_id.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume id')

    part_table = {'type': label, 'table': []}

    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')

    item.update({'part_table': part_table})

    click.echo('Partition table successfully initialized.')
# part_init()

@click.command(name='part-show')
@click.option('volume_id', '--id', required=True, help="volume's id")
def part_show(volume_id, **kwargs):
    """
    display the volume's partition table
    """
    # break name parts
    try:
        server, volume_id = volume_id.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume id')

    client = Client()
    item = fetch_item(
        client.StorageVolumes,
        {'volume_id': volume_id, 'server': server},
        'volume not found.')

    part_table = item.part_table
    if (not isinstance(part_table, dict) or not
            isinstance(part_table.get('table'), list)):
        raise click.ClickException(
            'partition table undefined; initialize it with the part-init '
            'command.')

    rows = []
    table_list = part_table.get('table', [])
    for i in range(0, len(table_list)):
        part = table_list[i]
        row = [
            i+1,
            size_to_str(part.get('size', 0)),
            part.get('type', ''),
            part.get('fs', ''),
            part.get('mp', ''),
            part.get('mo', ''),
        ]
        rows.append(row)

    click.echo('\nPartition table type: {}'.format(
        part_table.get('type', 'undefined')))
    print_ver_table(PART_FIELDS, rows)
# part_show()

@click.command('vol-add')
# set the parameter name after the model's attribute name to save on typing
@click.option('vol_id', '--id', required=True,
              help="volume id in the form server-name/volume-id")
@click.option('--size', required=True, help="volume size (i.e. 10gb)")
@click.option('--type', required=True, help="volume type (see vol-types)")
@click.option('--pool', help="assign volume to this storage pool")
@click.option('--specs', help="volume specification (json)")
@click.option('--project', help="project owning volume")
@click.option('--desc', help="free form field describing volume")
def vol_add(vol_id, **kwargs):
    """
    create a new storage volume
    """
    # break name parts
    try:
        kwargs['server'], kwargs['volume_id'] = vol_id.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume id')
    # convert a human size to integer
    try:
        kwargs['size'] = str_to_size(kwargs['size'])
    except ValueError:
        raise click.ClickException('invalid size specified.')

    client = Client()
    item = client.StorageVolumes()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# vol_add()

@click.command(name='vol-del')
@click.option('vol_id', '--id', required=True,
              help="volume id in the form server-name/volume-id")
def vol_del(vol_id):
    """
    remove an existing storage volume
    """
    # break name parts
    try:
        server, vol_id = vol_id.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume id')
    client = Client()

    fetch_and_delete(
        client.StorageVolumes,
        {'volume_id': vol_id, 'server': server},
        'volume not found.'
    )
    click.echo('Item successfully deleted.')
# vol_del()

@click.command(
    'vol-edit',
    short_help='change properties of an existing storage volume')
@click.option('cur_id', '--id', required=True,
              help="volume id in the form server-name/volume-id")
# set the parameter name after the model's attribute name to save on typing
@click.option('volume_id', '--newid', help="new volume's id in form volume-id")
@click.option('--size',
              help="volume size (i.e. 10gb)")
@click.option('--type', help="volume type (see vol-types)")
@click.option('--pool', help="assign volume to this storage pool")
@click.option('--specs', help="volume specification (json)")
@click.option('--owner', help="volume's owner login")
@click.option('--project', help="project owning volume")
@click.option('--desc', help="free form field describing volume")
def vol_edit(cur_id, **kwargs):
    """
    change properties of an existing storage volume
    """
    # break name parts
    try:
        server, cur_id = cur_id.split('/', 1)
    except:
        raise click.ClickException('invalid format for volume id')
    try:
        kwargs['size'] = str_to_size(kwargs['size'])
    except ValueError:
        raise click.ClickException('invalid size specified.')

    client = Client()
    fetch_and_update(
        client.StorageVolumes,
        {'volume_id': cur_id, 'server': server},
        'volume not found.',
        kwargs)
    click.echo('Item successfully updated.')
# vol_edit()

@click.command(name='vol-show')
# set the parameter name after the model's attribute name to save on typing
@click.option(
    'volume_id', '--id',
    help="show specified server-name/volume-id only or filter by volume-id")
@click.option('--owner', help="filter by specified owner login")
@click.option('--pool', help="show volumes assigned to this pool")
@click.option('--project', help="filter by specified project")
@click.option('--server', help="filter by specified server")
@click.option('--system', help="show volumes assigned to this system")
@click.option('--type', help="filter by specified volume type")
def vol_show(**kwargs):
    """
    show registered storage volumes
    """
    # server/id format specified: split it
    if kwargs['volume_id'] is not None and kwargs['volume_id'].find('/') > -1:
        # server dedicated parameter also specified: report conflict
        if kwargs['server'] is not None:
            raise click.ClickException(
                'server specified twice (--id and --server)')
        try:
            kwargs['server'], kwargs['volume_id'] = \
                kwargs['volume_id'].split('/', 1)
        except:
            raise click.ClickException('invalid format for volume id')
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

# vol_show()

@click.command(name='vol-types')
def vol_types():
    """
    show the supported volume types
    """
    # fetch data from server
    client = Client()
    entries = client.VolumeTypes.instances()

    # present results
    print_items(
        TYPE_FIELDS, client.VolumeTypes, None, entries)

# vol_types()

CMDS = [
    vol_add, vol_del, vol_edit, vol_show, vol_types, part_add, part_del,
    part_edit, part_init, part_show
]
