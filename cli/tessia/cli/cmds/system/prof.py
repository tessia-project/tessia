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
Module for the prof (system activation profiles) commands
"""

#
# IMPORTS
#
from tessia.cli.client import Client
from tessia.cli.filters import dict_to_filter
from tessia.cli.output import print_items
from tessia.cli.output import PrintMode
from tessia.cli.types import CustomIntRange
from tessia.cli.types import LOGIN, MIB_SIZE, NAME, TEXT, USER_PASSWD
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update
from tessia.cli.utils import fetch_item
from tessia.cli.utils import size_to_str

import click

#
# CONSTANTS AND DEFINITIONS
#
MEM_HELP = ("memory size as an integer followed by one of the units KB, MB, "
            "GB, TB, KiB, MiB, GiB, TiB")

PROFILE_FIELDS = (
    'name', 'system', 'hypervisor_profile', 'operating_system', 'default',
    'cpu', 'memory', 'parameters', 'credentials', 'storage_volumes',
    'system_ifaces', 'gateway'
)

PROFILE_FIELDS_TABLE = (
    'name', 'system', 'operating_system', 'cpu', 'memory', 'storage_volumes',
    'system_ifaces'
)

USERNAME_PROMPT = "OS admin's username"
PASSWORD_PROMPT = "OS admin's password"
ZVM_PROMPT = 'z/VM password'

#
# CODE
#

@click.command(name='prof-add')
@click.option('--system', required=True, type=NAME, help='target system')
@click.option('--name', '--profile', required=True, type=NAME, help="profile name")
@click.option('--cpu', default=0, type=CustomIntRange(min=0),
              help="number of cpus")
@click.option('--kargs-installer', 'kargs_installer',
              help=("custom kernel cmdline for the Linux installer"))
@click.option('--kargs-target', 'kargs_target',
              help=("custom kernel cmdline for the installed system"))
@click.option('--memory', default='0', type=MIB_SIZE, help=MEM_HELP)
@click.option('--default', is_flag=True, help="set as default for system")
@click.option('hypervisor_profile', '--hyp', type=NAME,
              help="hypervisor profile required for activation")
@click.option('--liveimg', 'liveimg_url', type=TEXT,
              help="URL to Live image insfile (CPCs in DPM mode only)")
@click.option('--login', type=USER_PASSWD,
              help="set the admin credentials to access the OS")
@click.option('operating_system', '--os', type=NAME,
              help="operating system (if installed manually)")
@click.option('--zvm-pass', 'zvm_pass', type=TEXT,
              help="password for access to zvm hypervisor (zVM guests only)")
@click.option('--ask-zvm-pass', is_flag=True,
              help="prompt for the zvm password (zVM guests only)")
@click.option('--zvm-by', 'zvm_by', type=TEXT,
              help="byuser for access to zvm hypervisor (zVM guests only)")
def prof_add(**kwargs):
    """
    create a new system activation profile
    """
    client = Client()

    # avoid user confusion
    if (kwargs['hypervisor_profile'] is not None and
            kwargs['hypervisor_profile'].find('/') > -1):
        raise click.ClickException(
            'invalid format for hypervisor profile, specify profile name only')

    login = kwargs.pop('login')
    # login not provided: prompt for it
    if not login:
        login = (
            click.prompt(USERNAME_PROMPT, default='root', type=LOGIN),
            click.prompt(PASSWORD_PROMPT, hide_input=True,
                         confirmation_prompt=True, type=TEXT)
        )
    kwargs['credentials'] = {
        'admin-user': login[0], 'admin-password': login[1]}

    zvm_pass = kwargs.pop('zvm_pass')
    zvm_by = kwargs.pop('zvm_by')

    system = fetch_item(
        client.Systems,
        {'name': kwargs['system']},
        'system specified not found.')
    if system.type.lower() == 'zvm':
        if kwargs.pop('ask_zvm_pass'):
            zvm_pass = click.prompt(ZVM_PROMPT, hide_input=True,
                                    confirmation_prompt=True, type=TEXT)
        if not zvm_pass:
            kwargs['credentials']['zvm-password'] = ""
        else:
            kwargs['credentials']['zvm-password'] = zvm_pass
        if zvm_by:
            kwargs['credentials']['zvm-logonby'] = zvm_by
    elif zvm_pass or zvm_by or kwargs.pop('ask_zvm_pass'):
        raise click.ClickException(
            'zVM credentials should be provided for zVM guests only')

    param_fields = {}
    liveimg_url = kwargs.pop('liveimg_url')
    if liveimg_url:
        if system.type.lower() != 'cpc':
            raise click.ClickException(
                'A live image URL can only be provided for CPCs')
        param_fields['liveimg-insfile-url'] = liveimg_url
    kargs_installer = kwargs.pop('kargs_installer')
    if kargs_installer:
        param_fields['linux-kargs-installer'] = kargs_installer
    kargs_target = kwargs.pop('kargs_target')
    if kargs_target:
        param_fields['linux-kargs-target'] = kargs_target
    if param_fields:
        kwargs['parameters'] = param_fields

    item = client.SystemProfiles()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# prof_add()

@click.command(name='prof-del')
@click.option('--system', required=True, type=NAME, help='system name')
@click.option('--name', '--profile', required=True, type=NAME,
              help="profile name to delete")
def prof_del(**kwargs):
    """
    remove an existing system activation profile
    """
    client = Client()

    fetch_and_delete(
        client.SystemProfiles,
        kwargs,
        'system profile not found.'
    )
    click.echo('Item successfully deleted.')
# prof_del()

@click.command(name='prof-edit')
@click.option('--system', required=True, type=NAME, help='system name')
@click.option('cur_name', '--name', '--profile', required=True, type=NAME,
              help="profile name")
@click.option('name', '--newname', type=NAME,
              help="new name (i.e. new-profile-name)")
@click.option('--cpu', type=CustomIntRange(min=0), help="number of cpus")
@click.option('--kargs-installer', 'kargs_installer',
              help=("custom kernel cmdline for the Linux installer"))
@click.option('--kargs-target', 'kargs_target',
              help=("custom kernel cmdline for the installed system"))
@click.option('--memory', type=MIB_SIZE, help=MEM_HELP)
@click.option('--default', is_flag=True, help="set as default for system")
@click.option('--gateway', help='name of interface to use as gateway')
@click.option('hypervisor_profile', '--hyp', type=NAME,
              help="hypervisor profile required for activation")
@click.option('--liveimg', 'liveimg_url',
              help="URL to Live image insfile (CPCs in DPM mode only)")
@click.option('--login', type=USER_PASSWD,
              help="set the admin credentials to access the OS")
@click.option('--ask-login', is_flag=True,
              help="prompt for the OS admin user and password")
@click.option('operating_system', '--os',
              help="operating system (if installed manually)")
@click.option('--zvm-pass', 'zvm_pass', type=TEXT,
              help="password for access to zvm hypervisor (zVM guests only)")
@click.option('--ask-zvm-pass', is_flag=True,
              help="prompt for the zvm password (zVM guests only)")
@click.option('--zvm-by', 'zvm_by',
              help="byuser for access to zvm hypervisor (zVM guests only)")
def prof_edit(system, cur_name, **kwargs):
    """
    change properties of an existing system activation profile
    """
    # avoid user confusion
    if (kwargs['hypervisor_profile'] is not None and
            kwargs['hypervisor_profile'].find('/') > -1):
        raise click.ClickException(
            'invalid format for hypervisor profile, specify profile name only')

    # default not specified: set as none to remove from update request
    if not kwargs['default']:
        kwargs['default'] = None

    client = Client()

    login = kwargs.pop('login')
    if kwargs.pop('ask_login'):
        login = (
            click.prompt(USERNAME_PROMPT, default='root', type=LOGIN),
            click.prompt(PASSWORD_PROMPT, hide_input=True,
                         confirmation_prompt=True, type=TEXT)
        )

    zvm_pass = kwargs.pop('zvm_pass')
    if kwargs.pop('ask_zvm_pass'):
        zvm_pass = click.prompt(ZVM_PROMPT, hide_input=True,
                                confirmation_prompt=True, type=TEXT)
    zvm_by = kwargs.pop('zvm_by')

    creds = {}
    # handle admin credentials
    if login:
        creds['admin-user'] = login[0]
        creds['admin-password'] = login[1]
    # handle zvm password
    if zvm_pass:
        creds['zvm-password'] = zvm_pass
    # handle zvm logonby
    if zvm_by:
        creds['zvm-logonby'] = zvm_by
    # allow unsetting logonby
    elif isinstance(zvm_by, str):
        creds['zvm-logonby'] = None
    # a credential is updated: add to request
    if creds:
        kwargs['credentials'] = creds

    param_fields = []
    liveimg_url = kwargs.pop('liveimg_url')
    if liveimg_url is not None:
        sys_obj = fetch_item(
            client.Systems, {'name': system}, 'system specified not found.')
        if sys_obj.type.lower() != 'cpc':
            raise click.ClickException(
                'A live image URL can only be provided for CPCs')
        param_fields.append(('liveimg-insfile-url', liveimg_url))
    kargs_installer = kwargs.pop('kargs_installer')
    if kargs_installer is not None:
        param_fields.append(('linux-kargs-installer', kargs_installer))
    kargs_target = kwargs.pop('kargs_target')
    if kargs_target is not None:
        param_fields.append(('linux-kargs-target', kargs_target))
    if param_fields:
        sys_prof_obj = fetch_item(
            client.SystemProfiles,
            {'system': system, 'name': cur_name},
            'system profile not found.')
        if isinstance(sys_prof_obj.parameters, dict):
            kwargs['parameters'] = sys_prof_obj.parameters
        else:
            kwargs['parameters'] = {}
        for key, value in param_fields:
            if value:
                kwargs['parameters'][key] = value
            else:
                kwargs['parameters'].pop(key, None)
        # dict is now empty: set field to null (fetch_and_update converts empty
        # string to null)
        if not kwargs['parameters']:
            kwargs['parameters'] = ''

    fetch_and_update(
        client.SystemProfiles,
        {'system': system, 'name': cur_name},
        'system profile not found.',
        kwargs)
    click.echo('Item successfully updated.')
# prof_edit()

@click.command(name='prof-list')
@click.option('--long', 'long_info', help="show extended information",
              is_flag=True, default=False)
@click.option('--system', type=NAME, help="the system to list")
@click.option('--name', '--profile', type=NAME, help="filter by profile-name")
@click.option('--cpu', type=CustomIntRange(min=0),
              help="filter by specified number of cpus")
@click.option('--memory', type=MIB_SIZE, help=MEM_HELP)
@click.option('operating_system', '--os', type=NAME,
              help="filter by associated operating system")
@click.option('--default', is_flag=True, help="list only default profiles")
@click.option('hypervisor_profile', '--hyp', type=NAME,
              help="filter by required hypervisor profile")
def prof_list(**kwargs):
    """
    list the activation profiles of a system
    """
    # default not provided: remove from dict otherwise it will force listing
    # only non defaults
    if kwargs['default'] is False:
        kwargs.pop('default')

    if kwargs['system'] is None and kwargs['operating_system'] is None:
        raise click.ClickException(
            'At least one of --system or --os must be specified')

    # fetch data from server
    client = Client()

    long_info = kwargs.pop('long_info')
    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    parsed_filter['sort'] = {'name': False}
    entries = client.SystemProfiles.instances(**parsed_filter)

    def parse_ifaces(ifaces):
        """Helper function to format output from ifaces list"""
        parsed_ifaces = []
        for iface in ifaces:
            if iface.ip_address is not None:
                ip_address = iface.ip_address.rsplit('/', 1)[-1]
                parsed_ifaces.append('[{}/{}]'.format(iface.name, ip_address))
            else:
                parsed_ifaces.append('[{}]'.format(iface.name))

        return ', '.join(parsed_ifaces)
    # parse_ifaces()

    def parse_vols(vols):
        """Helper function to format output from volumes list"""
        ret_vols = []
        for vol in vols:
            vol_entry = '[{}/{}]'.format(vol.server, vol.volume_id)
            if vol.part_table:
                for part in vol.part_table.get('table', []):
                    if part.get('mp', '') == '/':
                        vol_entry += '(root)'
                    elif part.get('fs', '') == 'swap':
                        vol_entry += '(swap)'
            ret_vols.append(vol_entry)

        return ', '.join(ret_vols)
    # parse_vols()

    parser_map = {
        'memory': size_to_str,
        'storage_volumes': parse_vols,
        'system_ifaces': parse_ifaces,
    }

    # present results
    if long_info:
        print_items(PROFILE_FIELDS, client.SystemProfiles, parser_map, entries,
                    PrintMode.LONG)
    else:
        print_items(PROFILE_FIELDS_TABLE, client.SystemProfiles, parser_map,
                    entries, PrintMode.TABLE)
# prof_list()

CMDS = [prof_add, prof_del, prof_edit, prof_list]
