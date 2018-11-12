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
from tessia.cli.types import CustomIntRange
from tessia.cli.types import LOGIN, NAME, TEXT, USER_PASSWD
from tessia.cli.utils import fetch_and_delete
from tessia.cli.utils import fetch_and_update
from tessia.cli.utils import fetch_item
from tessia.cli.utils import str_to_size
from tessia.cli.utils import size_to_str

import click

#
# CONSTANTS AND DEFINITIONS
#
PROFILE_FIELDS = (
    'name', 'system', 'hypervisor_profile', 'operating_system', 'default',
    'cpu', 'memory', 'parameters', 'credentials', 'storage_volumes',
    'system_ifaces', 'gateway'
)
USERNAME_PROMPT = "OS admin's username"
PASSWORD_PROMPT = "OS admin's password"
ZVM_PROMPT = 'z/VM password'

#
# CODE
#

@click.command(name='prof-add')
@click.option('--system', required=True, type=NAME, help='target system')
@click.option('--name', required=True, type=NAME, help="profile name")
@click.option('--cpu', default=1, type=CustomIntRange(min=1),
              help="number of cpus")
@click.option('--memory', default='1gib', help="memory size (i.e. 1gib)")
@click.option('--default', is_flag=True, help="set as default for system")
@click.option('hypervisor_profile', '--hyp', type=NAME,
              help="hypervisor profile required for activation")
@click.option('--login', type=USER_PASSWD,
              help="set the admin credentials to access the OS")
@click.option('operating_system', '--os', type=NAME,
              help="operating system (if installed manually)")
@click.option('--zvm-pass', 'zvm_pass', type=TEXT,
              help="password for access to zvm hypervisor (zVM guests only)")
@click.option('--zvm-by', 'zvm_by', type=TEXT,
              help="byuser for access to zvm hypervisor (zVM guests only)")
def prof_add(**kwargs):
    """
    create a new system activation profile
    """
    client = Client()

    # convert a human size to integer
    try:
        kwargs['memory'] = str_to_size(kwargs['memory'])
    except ValueError:
        raise click.ClickException('invalid memory size specified.')
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
    kwargs['credentials'] = {'user': login[0], 'passwd': login[1]}

    zvm_pass = kwargs.pop('zvm_pass')
    zvm_by = kwargs.pop('zvm_by')

    system = fetch_item(
        client.Systems,
        {'name': kwargs['system']},
        'system specified not found.')
    if system.type.lower() == 'zvm':
        if not zvm_pass:
            zvm_pass = click.prompt(ZVM_PROMPT, hide_input=True,
                                    confirmation_prompt=True, type=TEXT)
        kwargs['credentials']['host_zvm'] = {'passwd': zvm_pass}
        if zvm_by:
            kwargs['credentials']['host_zvm']['byuser'] = zvm_by
    elif zvm_pass or zvm_by:
        raise click.ClickException(
            'zVM credentials should be provided for zVM guests only')

    item = client.SystemProfiles()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()
    click.echo('Item added successfully.')
# prof_add()

@click.command(name='prof-del')
@click.option('--system', required=True, type=NAME, help='system name')
@click.option('--name', required=True, type=NAME,
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
@click.option('cur_name', '--name', required=True, type=NAME,
              help="profile name")
@click.option('name', '--newname', type=NAME,
              help="new name (i.e. new-profile-name)")
@click.option('--cpu', type=CustomIntRange(min=1), help="number of cpus")
@click.option('--memory', help="memory size (i.e. 1gib)")
@click.option('--default', is_flag=True, help="set as default for system")
@click.option('--gateway', help='name of interface to use as gateway')
@click.option('hypervisor_profile', '--hyp', type=NAME,
              help="hypervisor profile required for activation")
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
    # convert a human size to integer
    try:
        kwargs['memory'] = str_to_size(kwargs['memory'])
    except ValueError:
        raise click.ClickException('invalid memory size specified.')
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
    # no credentials updated: nothing more to check, perform update
    if not login and not zvm_pass and (zvm_by is None):
        fetch_and_update(
            client.SystemProfiles,
            {'system': system, 'name': cur_name},
            'system profile not found.',
            kwargs)
        click.echo('Item successfully updated.')
        return

    # to update the credentials field the existing data must be merged with
    # new data
    item = fetch_item(
        client.SystemProfiles,
        {'system': system, 'name': cur_name},
        'system profile not found.')
    if item.credentials:
        merged_creds = item.credentials.copy()
    else:
        merged_creds = {}

    # login provided: parse it to json format expected by API
    if login:
        merged_creds['user'] = login[0]
        merged_creds['passwd'] = login[1]

    # process the zvm specific credentials
    host_zvm = merged_creds.get('host_zvm', {})
    if zvm_pass:
        host_zvm['passwd'] = zvm_pass
    # empty value: unset byuser parameter
    if not zvm_by and isinstance(zvm_by, str):
        try:
            host_zvm.pop('byuser')
        except KeyError:
            pass
    # byuser specified: add to credentials
    elif zvm_by:
        host_zvm['byuser'] = zvm_by

    # zvm byuser specified but passwd not present: invalid combination
    if host_zvm.get('byuser') and not host_zvm.get('passwd'):
        raise click.ClickException('--zvm-by requires a zvm password to '
                                   'be set (use --zvm-pass)')

    # zvm information was specified but os wasn't: invalid combination
    if host_zvm and not merged_creds.get('user'):
        raise click.ClickException('OS login is required when zvm credentials '
                                   'are specified (use --login)')

    if host_zvm:
        merged_creds['host_zvm'] = host_zvm
    kwargs['credentials'] = merged_creds

    # remove fields not set before sending the update request
    parsed_dict = {}
    for key, value in kwargs.items():
        if value is not None:
            if value:
                parsed_dict[key] = value
            # allow unsetting parameter when value is an empty string
            else:
                parsed_dict[key] = None
        # value not being updated: remove from object to prevent being part of
        # request
        elif hasattr(item, key):
            del item[key]
    item.update(parsed_dict)
    click.echo('Item successfully updated.')
# prof_edit()

@click.command(name='prof-list')
@click.option('--system', required=True, type=NAME, help="the system to list")
@click.option('--name', type=NAME, help="filter by profile-name")
@click.option('--cpu', type=CustomIntRange(min=1),
              help="filter by specified number of cpus")
@click.option('--memory', help="filter by specified memory size (i.e. 1gib)")
@click.option('--default', is_flag=True, help="list only default profiles")
@click.option('hypervisor_profile', '--hyp', type=NAME,
              help="filter by required hypervisor profile")
def prof_list(**kwargs):
    """
    list the activation profiles of a system
    """
    # convert a human size to integer
    try:
        kwargs['memory'] = str_to_size(kwargs['memory'])
    except ValueError:
        raise click.ClickException('invalid memory size specified.')

    # default not provided: remove from dict otherwise it will force listing
    # only non defaults
    if kwargs['default'] is False:
        kwargs.pop('default')

    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
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

    def translate_credentials(credentials):
        """
        Helper function to rename credentials fields to meaningful names
        """
        if not credentials:
            return ''
        elif isinstance(credentials, str):
            return credentials

        zvm_map = {'passwd': 'password', 'byuser': 'logonby'}
        for key in zvm_map:
            try:
                credentials['host_zvm'][zvm_map[key]] = (
                    credentials['host_zvm'].pop(key))
            except KeyError:
                pass

        trans_map = {
            'host_zvm': 'zvm-credentials',
            'user': 'admin-user',
            'passwd': 'admin-password'
        }
        for key in trans_map:
            try:
                credentials[trans_map[key]] = credentials.pop(key)
            except KeyError:
                pass
        return credentials
    # translate_credentials()

    parser_map = {
        'credentials': translate_credentials,
        'memory': size_to_str,
        'storage_volumes': lambda vols: ', '.join(
            ['[{}/{}]'.format(vol.server, vol.volume_id) for vol in vols]),
        'system_ifaces': parse_ifaces,
    }

    # present results
    print_items(
        PROFILE_FIELDS, client.SystemProfiles, parser_map, entries)

# prof_list()

CMDS = [prof_add, prof_del, prof_edit, prof_list]
