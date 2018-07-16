# Copyright 2018 IBM Corp.
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
Module for the system wizard command
"""

#
# IMPORTS
#
from potion_client.exceptions import ItemNotFound
from tessia.cli import types
from tessia.cli.client import Client
from tessia.cli.output import print_hor_table
from tessia.cli.output import print_ver_table
from tessia.cli.cmds.net import ip as ip_cmds
from tessia.cli.cmds.system import iface as iface_cmds
from tessia.cli.cmds.system import prof as prof_cmds
from tessia.cli.cmds.system import system as sys_cmds
from tessia.cli.cmds.system import vol as sys_vol_cmds
from tessia.cli.cmds.storage import vol as vol_cmds
from tessia.cli.utils import size_to_str, parse_error_resp

import click
import requests

#
# CONSTANTS AND DEFINITIONS
#

FS_OPTIONS = ('btrfs', 'ext2', 'ext3', 'ext4', 'reiserfs', 'swap', 'xfs')

WIZ_START = (
    "This wizard will help you get your system properly registered in the "
    "tool so that you can perform operating system's installations.\n"
    "Let's start by collecting information about your system."
)
# system step related messages
WIZ_SYS_NAME = "Enter your system name"
WIZ_SYS_CONFIRM = (
    "A system already exists with that name (see above), do you want to use "
    "it?"
)
WIZ_SYS_TYPE = "Enter the system type (LPAR, KVM, ZVM)"
WIZ_SYS_HYP = (
    "What's the name of the hypervisor system? Hint: for an LPAR this is the "
    "CEC/box where it is hosted.\nEnter the hypervisor name"
)
WIZ_SYS_HYP_NOT_FOUND = (
    "No hypervisor exists with that name, try a different name."
)
WIZ_SYS_HOSTNAME = (
    "Enter the system's resolvable hostname or an IP address which can be "
    "used by the server to reach the system in the network.\nEnter hostname"
)
WIZ_SYS_DESC = (
    "You may enter a description for your system, for example 'system used "
    "for performance tests'.\nEnter description"
)
WIZ_SYS_CREATING = (
    "Submitting request to create your system..."
)
WIZ_SYS_FAIL = (
    "The system creation failed, try to fix the error(s) reported above and "
    "try again."
)

# profile step related messages
WIZ_PROF_CREATING = (
    "Submitting request to create your profile..."
)
WIZ_PROF_FAIL = (
    "The profile creation failed, try to fix the error(s) reported above and "
    "try again."
)
WIZ_PROF_START = (
    "* Profile section: here you define a system activation profile. "
    "An activation profile contains all the information required (disks, "
    "network interfaces, etc.) to power on a system."
)
WIZ_PROF_NAME = "Enter the desired profile name"
WIZ_PROF_EXISTS = (
    "A profile with that name already exists, try a different name."
)
WIZ_PROF_CPU = (
    "How many CPUs should be assigned to this profile? Enter the CPU quantity"
)
WIZ_PROF_MEM = (
    "How much memory should be assigned to this profile? Enter memory"
)
WIZ_PROF_DEF = (
    "Should this profile be set as the default?"
)
WIZ_PROF_PASSWD = (
    "Enter the password to be used for the root account when installing a "
    "new operating system"
)
WIZ_PROF_ZVM_BY = (
    "For zVM guests it's necessary to enter the zVM credentials. Do you "
    "require 'logon by' for this guest? If not, leave the field "
    "blank.\nEnter logon by user"
)
WIZ_PROF_ZVM_PASSWD = (
    "Enter the zVM user password"
)

# storage step related messages
WIZ_ST_START = (
    "* Storage section: in this section you specify the volumes (disks) to "
    "be used in the activation profile."
)
WIZ_ST_SERVER_TITLE = (
    "Storage servers available:"
)
WIZ_ST_SERVER_ASK = (
    "Enter the number that corresponds to the server where your volume "
    "is located (if you are unsure, ask your storage administrator)"
)
WIZ_ST_VOL_ID = (
    "Which volume (disk) do you want to use? For example, it should be "
    "something like '0a0a' for a DASD disk or '400000000000000' for a "
    "FCP-SCSI disk.\nEnter the volume identifier"
)
WIZ_ST_VOL_CHOICE = (
    "The volumes above match the identifier provided, you can choose one of "
    "them by typing the matching number or press Enter to get back to "
    "the prompt and type another identifier"
)
WIZ_ST_VOL_PATH_START = (
    "For FCP disks it's necessary to enter the ADAPTER_DEVNO,WWPN paths."
)
WIZ_ST_VOL_PATH = (
    "Enter a FCP path in the form ADAPTER_DEVNO,WWPN"
)
WIZ_ST_VOL_PATH_LIST = (
    "FCP paths currently added: "
)
WIZ_ST_VOL_PATH_MORE = (
    "Do you want to add more paths? You can also type 'r' to reset the "
    "current list"
)
WIZ_ST_VOL_WWID = (
    "In order to uniquely identify this volume in a multipath setup, we also "
    "need its World Wide Identifier (WWID). If you don't have it, ask the "
    "storage administrator.\nEnter the WWID"
)
WIZ_ST_VOL_MPATH = "Enable multipath for this volume?"
WIZ_ST_VOL_TYPE_TITLE = (
    "Volume types available:"
)
WIZ_ST_VOL_TYPE_ASK = (
    "Enter the number that corresponds to your volume's type"
)
WIZ_ST_VOL_CREATE_CONFIRM = (
    "No existing volume matches the identifier entered, do you want to "
    "register it as a new volume? (you might need special permissions "
    "in order to do that)"
)
WIZ_ST_VOL_SIZE = (
    "What is the size of your volume? Hint: if you are unsure, try a small "
    "value first, perform an installation and then adjust it based on the "
    "actual value reported by the installation. Pay attention to the unit "
    "used as some tools like 'lsdasd' report sizes as MB (powers of 10) when "
    "they actually mean MiB (powers of 2).\nEnter the volume size"
)
WIZ_ST_VOL_CREATING = (
    "Submitting request to create your volume..."
)
WIZ_ST_VOL_FAIL = (
    "The volume creation failed, try to fix the error(s) reported above and "
    "try again."
)
WIZ_ST_VOL_PART_RESET = (
    'reset partition table'
)
WIZ_ST_VOL_PART_QUIT = (
    'quit partitioning'
)
WIZ_ST_VOL_PART_SHOW = (
    'show partition table'
)
WIZ_ST_VOL_PART_END = (
    "Partitioning finished."
)
WIZ_ST_VOL_PART_CONTINUE = (
    "Press any key to continue adding partitions..."
)
WIZ_ST_VOL_PART_RESET_CONFIRM = (
    "This volume has the above partition table defined. Do you want to reset "
    "it and recreate?"
)
WIZ_ST_VOL_PART_START = (
    "Now you are going to define partitions for your volume. Remember that a "
    "valid setup must define at least one root partition and in most cases "
    "it is also recommended to have a swap partition (which can be set on "
    "another volume if desired)."
)
WIZ_ST_VOL_PART_SIZE = (
    "What is the partitions's size? Hint: pay attention to the unit used (MB "
    "being powers of 10 and MiB being powers of 2)"
)
WIZ_ST_VOL_PART_EXCEEDS = (
    "Error: size specified exceeds available free size ({}MiB)."
)
WIZ_ST_VOL_PART_FS_TITLE = (
    "Create new partition - filesystem types available:"
)
WIZ_ST_VOL_PART_FS_ASK = (
    "Enter the number matching the filesystem you want to use for the new "
    "partition, or choose one of the actions 'show', 'reset', 'quit'"
)
WIZ_ST_VOL_PART_MP = (
    "Enter the mount point for this partition, beginning with '/'. Leave it "
    "blank if the partition shouldn't be mounted on the installed system.\n"
    "Enter mount point"
)
WIZ_ST_VOL_PART_CREATING = (
    "Submitting request to create your partition..."
)
WIZ_ST_VOL_PART_FAIL = (
    "It was not possible to add the partition, try to fix the error(s) "
    "reported above and try again."
)
WIZ_ST_VOL_PART_TYPE_TITLE = (
    "Partition types for MBR (msdos) partition tables:"
)
WIZ_ST_VOL_PART_TYPE_ASK = (
    "For MBR (msdos) partition tables the partition type must be specified "
    ". Hint: you can only have a maximum of 4 primary partitions,"
    " if you need more use logicals instead.\nEnter the partition type number"
)
WIZ_ST_VOL_MORE = (
    "Do you want to add more disks to the profile?"
)
WIZ_ST_VOL_DESC = (
    "You can enter a description to provide additional information about this "
    "volume.\nEnter description"
)

# network step related messages
WIZ_NET_START = (
    "* Network section: define the network interfaces to be used in the "
    "activation profile"
)
WIZ_NET_IFACE_MORE = (
    "Do you want to add more interfaces?"
)
WIZ_NET_IFACE_NAME = (
    "Enter a name for your interface. This is not the name of the interface "
    "in the operating system, but rather an identifier like 'external-iface'."
    "\nEnter the interface name"
)
WIZ_NET_IFACE_CONFIRM = (
    "An interface already exists with that name (see above), do you want to "
    "use it?"
)
WIZ_NET_IFACE_CREATE_CONFIRM = (
    "No existing interface matches the identifier entered, do you want to "
    "register it as a new interface?"
)
WIZ_NET_IFACE_TYPE_TITLE = (
    "Interface types available:"
)
WIZ_NET_IFACE_TYPE_ASK = (
    "Enter the number matching your interface type"
)
WIZ_NET_IFACE_OSNAME = (
    "How should the interface be named in the operating system? Hint: for "
    "channel based cards you can use the convention encXXXX.\nEnter the "
    "OS name"
)
WIZ_NET_IFACE_LAYER2 = (
    "Do you want to enable layer2 mode?"
)
WIZ_NET_IFACE_CCWGROUP = (
    "Enter the interface's CCW channels (i.e. f500,f501,f502)"
)
WIZ_NET_IFACE_PORTNO = (
    "Do you require to set the alternative portno '1' instead of the "
    "default '0' port?"
)
WIZ_NET_IFACE_HOST_IFACE_TITLE = (
    "Network interfaces available on the hypervisor:"
)
WIZ_NET_IFACE_HOST_IFACE_ASK = (
    "Macvtap interfaces are bound to a network interface on the host "
    "hypervisor. Enter the number matching the host interface you want to "
    "bind to. If the list is empty it means an interface must be defined for "
    "the host first before you can continue.\nEnter number"
)
WIZ_NET_IFACE_MAC = (
    "Enter the MAC address for your interface, leave it blank if you "
    "prefer to have it dynamically generated during installation time.\n"
    "Enter MAC address"
)
WIZ_NET_IFACE_DESC = (
    "You can enter a description to provide additonal information about this "
    "interface.\nEnter description"
)
WIZ_NET_IFACE_CREATING = (
    "Submitting request to create your network interface..."
)
WIZ_NET_IFACE_FAIL = (
    "The interface creation failed, try to fix the error(s) reported above "
    "and try again."
)
WIZ_NET_IFACE_IP_CONFIRM = (
    "Your interface has no IP address assigned, do you want to assign one?"
)
WIZ_NET_IFACE_IP_CREATE_CONFIRM = (
    "The address does not match any existing entry, do you want to register "
    "it as a new IP? (you might need special permissions in order to do that)"
)
WIZ_NET_IFACE_IP_CHOICE = (
    "The entries above match the address provided, you can choose one of "
    "them by typing the matching number or press Enter to get back to "
    "the prompt and type another address"
)
WIZ_NET_IFACE_IP_ADDR = (
    "Enter the desired IP address"
)
WIZ_NET_IFACE_SUBNET_TITLE = (
    "Network subnets available:"
)
WIZ_NET_IFACE_SUBNET_ASK = (
    "Enter the number matching the subnet you want to use (if you are unsure, "
    "ask your network administrator)"
)
WIZ_NET_IFACE_IP_DESC = (
    "You can enter a description to provide additonal information about the "
    "usage of this IP address.\nEnter description"
)
WIZ_NET_IFACE_IP_CREATING = (
    "Submitting request to create your IP address..."
)
WIZ_NET_IFACE_IP_CREATE_FAIL = (
    "The IP address creation failed, try to fix the error(s) reported above "
    "and try again."
)
WIZ_NET_IFACE_IP_ASSIGN_FAIL = (
    "It was not possible to assign the IP to the network interface, try to "
    "fix the error(s) reported above and try again."
)
WIZ_NET_IFACE_IP_ASSIGNING = (
    "Submitting request to assign the IP address to the network interface..."
)
WIZ_NET_IFACE_ATTACHING = (
    "Submitting request to attach the network interface to the activation "
    "profile..."
)
WIZ_NET_IFACE_ATTACH_FAIL = (
    "Attaching the interface to the profile failed, try to fix the error(s) "
    "reported above and try again."
)

# misc messages
WIZ_PROF_SUMMARY = (
    "Here's a summary of the activation profile you just created:"
)
WIZ_INSTALL_CONFIRM = (
    "Do you want to perform an installation using this profile now?"
)
WIZ_INSTALL_OS_TITLE = (
    "Operating systems available:"
)
WIZ_INSTALL_OS_ASK = (
    "Enter the number matching the operating system you want to install"
)
WIZ_END = (
    "Wizard finished. You can install your system using the newly created "
    "activation profile at any time with the 'tess system autoinstall' "
    "command."
)

#
# CODE
#

def _confirm(*args, **kwargs):
    """Helper to print a breakline before prompting for confirmation"""
    click.echo()
    return click.confirm(*args, **kwargs)
# _confirm()

def _get_headers(fields, item):
    """
    Return the description (docstring) of each specified field in a given
    model which can be used as table headers.

    Args:
        fields (list): field names
        item (any): an object containing the attributes listed in fields

    Returns:
        list: fields' descriptions
    """
    headers = []
    for attr in fields:
        field = getattr(item, attr)
        headers.append(field.__doc__)
    return headers
# _get_headers()

def _prompt(*args, allow_empty=False, **kwargs):
    """
    Print a breakline before prompting for input and normalize values to accept
    empty input when requested by caller.

    Args:
        args (any): arguments to click.prompt
        allow_empty (boolean): whether to allow prompt to accept empty as input
        kwargs (any): arguments to click.prompt

    Returns:
        str: input text
    """
    # allow empty input: check if default value must be normalized
    if allow_empty:
        def_value = kwargs.get('default')
        # def_value is empty string or None: make sure it's set to empty string
        # so that click.prompt will accept empty input
        if not def_value:
            def_value = ''
        kwargs['default'] = def_value

    click.echo()
    ret = click.prompt(*args, **kwargs)

    # input was empty and flag is set: convert back to None
    if allow_empty and not ret:
        ret = None
    return ret
# _prompt()

def _invoke(ctx, invoke_cmd, params, error_msg):
    """
    Wrapper to invoke other click commands.

    Args:
        ctx (Context): click's context object
        invoke_cmd (click.Command): command to be invoked
        params (dict): kwargs for command
        error_msg (str): to be displayed in case of failure

    Returns:
        bool: True if command succeeded, False otherwise
    """
    # convert params to a list of strings
    params_list = []
    for key, item in params.items():
        if isinstance(item, bool):
            params_list.append('--{}={}'.format(key, str(item).lower()))
        elif isinstance(item, list):
            for item_entry in item:
                params_list.append('--{}={}'.format(key, item_entry))
        # empty values are not set
        elif item in ('', None):
            continue
        # special case: parameter is set without value
        elif item == 'is_flag':
            params_list.append('--{}'.format(key))
        else:
            params_list.append('--{}={}'.format(key, item))

    try:
        new_ctx = invoke_cmd.make_context(
            invoke_cmd.name, args=params_list, parent=ctx)
        invoke_cmd.invoke(new_ctx)
    except click.ClickException as exc:
        exc.show()
        click.echo('Error: {}'.format(error_msg))
        return False
    except requests.exceptions.HTTPError as exc:
        click.echo('Error: {}'.format(parse_error_resp(exc.response)))
        click.echo(error_msg)
        return False

    return True
# _invoke()

def _choice_menu(entries, fields, choice_msg, title=None, headers=None):
    """
    Auxiliar function which shows a list of numbered options to the user and
    return the item selected.

    Args:
        entries (list): list of objects to display
        fields (list): entries' attributes to display
        choice_msg (str): message to display when requesting user's choice
        title (str): message to display as the table's title
        headers (list): custom table headers

    Returns:
        any: the picked item from the list, or None if none selected or wrong
             number entered
    """
    if not entries:
        return None
    # no custom headers: extract from object's class definition
    if not headers:
        headers = _get_headers(fields, entries[0].__class__)

    # add a label with a number so that the user can pick one
    # from the list
    choice_map = {'': None}
    for index, item in enumerate(entries):
        choice_map[str(index+1)] = item
        item.label = str(index+1)
    headers.insert(0, 'Number')
    fields.insert(0, 'label')

    # list entries
    if title:
        click.echo('\n' + title)
    print_ver_table(headers, entries, fields)

    choice_index = _prompt(choice_msg, default='', show_default=False,
                           type=click.Choice(choice_map.keys()))
    choice_item = choice_map[choice_index]

    return choice_item
# _choice_menu()

def _create_disk(client, ctx, sys_item, prof_item):
    """
    Perform the steps required to reach the point where a disk is created or
    reused, partitioned and assigned to the target activation profile.

    Args:
        client (Client): potion client to perform server requests
        ctx (Context): click's context object
        sys_item (System): target system object
        prof_item (SystemProfile): system activation profile object
    """
    # vol-add request params
    params = {
        'server': None,
        'id': None,
        'type': None,
        'size': '7gib',
        'desc': None,
    }
    do_part = True
    vol_item = None
    while not vol_item:
        params['id'] = _prompt(
            WIZ_ST_VOL_ID, default=params['id'], type=types.VOLUME_ID)

        # see if volume entered exists
        entries = client.StorageVolumes.instances(
            where={'volume_id': params['id']})
        # volume exists: show list and ask user to pick one
        if entries:
            vol_fields = ['volume_id', 'server', 'size', 'type', 'system']
            vol_headers = _get_headers(vol_fields, client.StorageVolumes)
            vol_fields[2] = 'size_str'
            for entry in entries:
                entry.size_str = size_to_str(entry.size)
            vol_item = _choice_menu(entries, vol_fields, WIZ_ST_VOL_CHOICE,
                                    headers=vol_headers)
            # nothing picked: start over, ask for volume again
            if not vol_item:
                continue

            # attach the disk to the profile
            attach_params = {
                'system': sys_item.name, 'profile': prof_item.name,
                'server': vol_item.server, 'vol': vol_item.volume_id}
            # command failed: start over
            if not _invoke(ctx, sys_vol_cmds.vol_attach, attach_params,
                           WIZ_ST_VOL_FAIL):
                vol_item = None
                continue

            # show existing ptable and confirm reset
            if vol_item.part_table:
                ctx.invoke(vol_cmds.part_list, server=vol_item.server,
                           volume_id=vol_item.volume_id)
                do_part = _confirm(WIZ_ST_VOL_PART_RESET_CONFIRM)
            else:
                do_part = True
            # break from loop
            break

        # confirm user wants to create new volume
        if not _confirm(WIZ_ST_VOL_CREATE_CONFIRM):
            continue

        # choose volume type
        type_list = client.VolumeTypes.instances()
        vol_type_item = None
        while not vol_type_item:
            vol_type_item = _choice_menu(
                type_list, ['name', 'desc'], WIZ_ST_VOL_TYPE_ASK,
                WIZ_ST_VOL_TYPE_TITLE)
        params['type'] = vol_type_item.name

        # choose storage server to use
        server_list = client.StorageServers.instances()
        st_server_item = None
        while not st_server_item:
            st_server_item = _choice_menu(
                server_list, ['name', 'type', 'desc'], WIZ_ST_SERVER_ASK,
                WIZ_ST_SERVER_TITLE)
        params['server'] = st_server_item.name

        # collect disk information
        params['size'] = _prompt(WIZ_ST_VOL_SIZE, default=params['size'],
                                 type=types.MIB_SIZE)
        # fcp disk: collect specific info
        if params['type'].lower() == 'fcp':
            click.echo('\n' + WIZ_ST_VOL_PATH_START)
            params['path'] = params.setdefault('path', [])
            while True:
                # input for another path
                fcp_path = _prompt(WIZ_ST_VOL_PATH, type=types.FCP_PATH)
                params['path'].append('{},{}'.format(*fcp_path))

                # show the list of paths added so far
                click.echo('\n' + WIZ_ST_VOL_PATH_LIST +
                           ' | '.join(params['path']))

                fcp_choice = _prompt(
                    WIZ_ST_VOL_PATH_MORE, type=click.Choice(['y', 'n', 'r']))
                # reset command: clear list
                if fcp_choice == 'r':
                    params['path'] = []
                # finish collecting paths
                elif fcp_choice == 'n':
                    break

            params['wwid'] = _prompt(
                WIZ_ST_VOL_WWID, default=params.get('wwid'),
                type=types.SCSI_WWID)
            params['mpath'] = _confirm(
                WIZ_ST_VOL_MPATH, default=params.get('mpath', True))
        params['desc'] = _prompt(
            WIZ_ST_VOL_DESC, default=params['desc'], allow_empty=True)
        # execute storage vol-add command
        click.echo('\n' + WIZ_ST_VOL_CREATING)
        # command failed: start over
        if not _invoke(ctx, vol_cmds.vol_add, params, WIZ_ST_VOL_FAIL):
            continue
        vol_item = client.StorageVolumes.first(
            where={'server': params['server'], 'volume_id': params['id']})
        # attach the disk to the profile
        attach_params = {
            'system': sys_item.name, 'profile': prof_item.name,
            'server': vol_item.server, 'vol': vol_item.volume_id}
        # command failed: start over
        if not _invoke(ctx, sys_vol_cmds.vol_attach, attach_params,
                       WIZ_ST_VOL_FAIL):
            vol_item = None
            continue

    # disk partitioning
    if do_part:
        if vol_item.type.lower() == 'dasd':
            vol_label = 'dasd'
        else:
            vol_label = 'msdos'
        # execute storage part-init command
        ctx.invoke(vol_cmds.part_init, server=vol_item.server,
                   volume_id=vol_item.volume_id, label=vol_label)

        class MenuItem(object):
            """Simple menu item entry"""
            def __init__(self, name):
                self._name = name
            @property
            def name(self):
                """Name"""
                return self._name
        # list of filesystems
        fs_entries = [MenuItem(fs) for fs in FS_OPTIONS]
        fs_entries.append(MenuItem(name=WIZ_ST_VOL_PART_SHOW))
        fs_entries.append(MenuItem(name=WIZ_ST_VOL_PART_RESET))
        fs_entries.append(MenuItem(name=WIZ_ST_VOL_PART_QUIT))
        # list of partition types
        type_entries = [MenuItem(p_type) for p_type in ['primary', 'logical']]
        # part-add request params
        params = {
            'server': vol_item.server,
            'id': vol_item.volume_id,
            'size': None,
            'fs': None,
            'mp': None,
            'type': None,
        }
        # track sizes to prevent users from exceeding the disk size
        free_size = vol_item.size
        click.echo('\n' + WIZ_ST_VOL_PART_START)
        while True:
            fs_item = None
            while not fs_item:
                fs_item = _choice_menu(
                    fs_entries, ['name'], WIZ_ST_VOL_PART_FS_ASK,
                    WIZ_ST_VOL_PART_FS_TITLE)
            # quit adding partitions
            if fs_item.name == WIZ_ST_VOL_PART_QUIT:
                click.echo('\nPartitioning finished.')
                break
            # reset partition table
            elif fs_item.name == WIZ_ST_VOL_PART_RESET:
                # execute storage part-init command
                ctx.invoke(vol_cmds.part_init, server=vol_item.server,
                           volume_id=vol_item.volume_id, label=vol_label)
                # reset the available size
                free_size = vol_item.size
                continue
            # show current partition table
            elif fs_item.name == WIZ_ST_VOL_PART_SHOW:
                ctx.invoke(vol_cmds.part_list, server=vol_item.server,
                           volume_id=vol_item.volume_id)
                click.pause(info=WIZ_ST_VOL_PART_CONTINUE)
                continue
            params['fs'] = fs_item.name

            # input size: do not allow size bigger than disk size
            while True:
                params['size'] = _prompt(
                    WIZ_ST_VOL_PART_SIZE, default=params['size'],
                    type=types.MIB_SIZE)
                if free_size - params['size'] < 0:
                    params['size'] = None
                    click.echo(
                        '\n' + WIZ_ST_VOL_PART_EXCEEDS.format(free_size))
                    continue
                break
            # swap partition: no mount point required
            if params['fs'].lower() == 'swap':
                params['mp'] = None
            else:
                ctx.meta['MountPoint.allow_empty'] = True
                params['mp'] = _prompt(
                    WIZ_ST_VOL_PART_MP, default=params['mp'],
                    type=types.MOUNT_POINT, allow_empty=True)
                ctx.meta['MountPoint.allow_empty'] = False
            if vol_label == 'msdos':
                type_item = None
                while not type_item:
                    type_item = _choice_menu(
                        type_entries, ['name'],
                        WIZ_ST_VOL_PART_TYPE_ASK, WIZ_ST_VOL_PART_TYPE_TITLE)
                params['type'] = type_item.name
            # execute storage part-add command
            click.echo('\n' + WIZ_ST_VOL_PART_CREATING)
            if _invoke(ctx, vol_cmds.part_add, params, WIZ_ST_VOL_PART_FAIL):
                # update available size counter
                free_size -= params['size']
                # restore some defaults, it doesn't make sense to reuse them
                params['mp'] = None
                params['size'] = None
# _create_disk()

def _create_iface(client, ctx, sys_item, prof_item):
    """
    Perform the steps required to reach the point where a network interface
    is created or reused, optionally gets an IP assigned and the interface is
    assigned to the target activation profile.

    Args:
        client (Client): potion client to perform server requests
        ctx (Context): click's context object
        sys_item (System): target system object
        prof_item (SystemProfile): system activation profile object
    """
    iface_fields = ['name', 'osname', 'type', 'ip_address', 'mac_address']

    # iface-add request params
    params = {
        'system': sys_item.name,
        'name': None,
        'osname': None,
        'type': None,
        'mac': None,
        'desc': None,
    }
    iface_item = None
    while not iface_item:
        params['name'] = _prompt(
            WIZ_NET_IFACE_NAME, default=params['name'], type=types.NAME)

        # check if iface entered already exists
        try:
            iface_item = client.SystemIfaces.first(
                where={'system': sys_item.name, 'name': params['name']})
        except ItemNotFound:
            iface_item = None
        # iface already exists: confirm before using it
        if iface_item:
            print_ver_table(_get_headers(iface_fields, client.SystemIfaces),
                            [iface_item], iface_fields)
            if _confirm(WIZ_NET_IFACE_CONFIRM):
                break
            iface_item = None
            continue

        # confirm user wants to create new iface
        if not _confirm(WIZ_NET_IFACE_CREATE_CONFIRM):
            continue

        # choose iface type
        type_list = client.IfaceTypes.instances()
        iface_type_item = None
        while not iface_type_item:
            iface_type_item = _choice_menu(
                type_list, ['name', 'desc'],
                WIZ_NET_IFACE_TYPE_ASK, WIZ_NET_IFACE_TYPE_TITLE)
        params['type'] = iface_type_item.name

        params['osname'] = _prompt(
            WIZ_NET_IFACE_OSNAME, default=params['osname'], type=types.NAME)

        # osa card: gather specific info
        if params['type'].lower() == 'osa':
            params['layer2'] = _confirm(
                WIZ_NET_IFACE_LAYER2, default=params.get('layer2'))
            params['ccwgroup'] = _prompt(
                WIZ_NET_IFACE_CCWGROUP, default=params.get('ccwgroup'),
                type=types.QETH_GROUP)
            params['portno'] = {True: '1', False: None}[_confirm(
                WIZ_NET_IFACE_PORTNO,
                default={'1': True, None: False}[params.get('portno')]
            )]
        else:
            params['layer2'] = None
            params['ccwgroup'] = None
            params['portno'] = None

        # kvm macvtap: need to choose a host interface
        if params['type'].lower() == 'macvtap':
            hyp_ifaces = client.SystemIfaces.instances(
                where={'system': sys_item.hypervisor})
            host_iface_item = None
            while not host_iface_item:
                host_iface_item = _choice_menu(
                    hyp_ifaces, iface_fields, WIZ_NET_IFACE_HOST_IFACE_ASK,
                    WIZ_NET_IFACE_HOST_IFACE_TITLE)
            params['hostiface'] = host_iface_item.osname
        else:
            params['hostiface'] = None

        if params['type'].lower() != 'osa':
            params['mac'] = _prompt(WIZ_NET_IFACE_MAC, default=params['mac'],
                                    type=types.MACADDRESS)
        # zvm guest or layer3: no mac should be entered
        elif sys_item.type.lower() == 'zvm' or not params.get('layer2'):
            params['mac'] = None
        # osa card with layer 2 enabled: mac is optional
        else:
            ctx.meta['MACaddress.allow_empty'] = True
            params['mac'] = _prompt(WIZ_NET_IFACE_MAC, default=params['mac'],
                                    type=types.MACADDRESS, allow_empty=True)
            ctx.meta['MACaddress.allow_empty'] = False
        params['desc'] = _prompt(
            WIZ_NET_IFACE_DESC, default=params['desc'], allow_empty=True)

        click.echo('\n' + WIZ_NET_IFACE_CREATING)
        if not _invoke(ctx, iface_cmds.iface_add, params, WIZ_NET_IFACE_FAIL):
            continue

        iface_item = client.SystemIfaces.first(
            where={'system': sys_item.name, 'name': params['name']})

    # iface already has ip or user doesn't want one: attach iface and
    # finish
    if iface_item.ip_address or not _confirm(WIZ_NET_IFACE_IP_CONFIRM):
        # last step, attach the iface to the profile
        _invoke(ctx, iface_cmds.iface_attach,
                {'system': sys_item.name, 'profile': prof_item.name,
                 'iface': iface_item.name}, WIZ_NET_IFACE_ATTACH_FAIL)
        return

    # user wants to create/choose an IP address
    do_assign = True
    while do_assign:
        params = {
            'subnet': None,
            'ip': None,
            'desc': None,
        }
        ip_item = None
        while not ip_item:
            params['ip'] = _prompt(
                WIZ_NET_IFACE_IP_ADDR, default=params['ip'],
                type=types.IPADDRESS)

            # see if address entered exists
            entries = client.IpAddresses.instances(
                where={'address': params['ip']})
            # address exists: show list and ask user to choose one
            if entries:
                ip_item = _choice_menu(entries, ['address', 'subnet', 'desc'],
                                       WIZ_NET_IFACE_IP_CHOICE)
                # nothing chosen: start over, ask for ip again
                if not ip_item:
                    continue
                # break from loop
                break

            # confirm user wants to create new ip
            if not _confirm(WIZ_NET_IFACE_IP_CREATE_CONFIRM):
                continue

            # choose subnet where IP will be created
            subnet_list = client.Subnets.instances()
            subnet_fields = ['name', 'zone', 'address', 'gateway', 'desc']
            subnet_item = None
            while not subnet_item:
                subnet_item = _choice_menu(
                    subnet_list, subnet_fields,
                    WIZ_NET_IFACE_SUBNET_ASK, WIZ_NET_IFACE_SUBNET_TITLE)
            params['subnet'] = subnet_item.name

            params['desc'] = _prompt(WIZ_NET_IFACE_IP_DESC,
                                     default=params['desc'], allow_empty=True)
            # failed to create ip: start over and try again
            click.echo('\n' + WIZ_NET_IFACE_IP_CREATING)
            if not _invoke(ctx, ip_cmds.ip_add,
                           params, WIZ_NET_IFACE_IP_CREATE_FAIL):
                continue

            ip_item = client.IpAddresses.first(
                where={'subnet': subnet_item.name, 'address': params['ip']})

        # assign the picked/newly created IP to the iface
        assign_params = {
            'system': sys_item.name, 'name': iface_item.name,
            'subnet': ip_item.subnet, 'ip': ip_item.address
        }
        click.echo(WIZ_NET_IFACE_IP_ASSIGNING)
        # assignment failed: start over
        do_assign = not _invoke(ctx, iface_cmds.iface_edit, assign_params,
                                WIZ_NET_IFACE_IP_ASSIGN_FAIL)

    # last step, attach the iface to the profile
    click.echo(WIZ_NET_IFACE_ATTACHING)
    _invoke(ctx, iface_cmds.iface_attach,
            {'system': sys_item.name, 'profile': prof_item.name,
             'iface': iface_item.name}, WIZ_NET_IFACE_ATTACH_FAIL)
# _create_iface()

def _create_prof(client, ctx, sys_item):
    """
    Perform the steps required to reach the point where the target system's
    activation profile object is available.

    Args:
        client (Client): potion client to perform server requests
        ctx (Context): click's context object
        sys_item (System): target system object

    Returns:
        SystemProfile: target system's activation profile
    """
    index = 1
    name_prefix = 'wizard-profile{}'
    # params for prof-add command
    params = {
        'system': sys_item.name,
        'default': None,
        'name': name_prefix.format(index),
        'cpu': '1',
        'memory': '1gib',
        'zvm-pass': None,
        'zvm-by': None,
    }
    prof_item = None
    while not prof_item:
        params['name'] = _prompt(WIZ_PROF_NAME, default=params['name'],
                                 type=types.NAME)
        # make sure this profile does not exist yet
        try:
            client.SystemProfiles.first(
                where={'system': sys_item.name, 'name': params['name']})
        except ItemNotFound:
            pass
        else:
            # user attempted suggested name: try to suggest a new name
            # with increased number
            if params['name'] == name_prefix.format(index):
                index += 1
            params['name'] = name_prefix.format(index)
            # report profile already exists and try again
            click.echo(WIZ_PROF_EXISTS)
            continue

        params['cpu'] = _prompt(WIZ_PROF_CPU, default=params['cpu'],
                                type=types.CustomIntRange(min=1))
        params['memory'] = _prompt(WIZ_PROF_MEM, default=params['memory'],
                                   type=types.MIB_SIZE)
        # other profiles exist: choose whether to set as default
        if client.SystemProfiles.instances(where={'system': sys_item.name}):
            params['default'] = {True: 'is_flag', False: None}[_confirm(
                WIZ_PROF_DEF, default=False)]
        # first profile being created: no point is asking as it will be the
        # default anyway
        else:
            params['default'] = None
        params['login'] = 'root:{}'.format(
            _prompt(WIZ_PROF_PASSWD, hide_input=True, confirmation_prompt=True)
        )
        # zvm system: need zvm credentials
        if sys_item.type.lower() == 'zvm':
            ctx.meta['Text.allow_empty'] = True
            params['zvm-by'] = _prompt(
                WIZ_PROF_ZVM_BY, default=params['zvm-by'], type=types.TEXT,
                allow_empty=True)
            ctx.meta['Text.allow_empty'] = False
            params['zvm-pass'] = _prompt(
                WIZ_PROF_ZVM_PASSWD, hide_input=True, confirmation_prompt=True)
        click.echo('\n' + WIZ_PROF_CREATING)
        # prof-add failed: start over and try again
        if not _invoke(ctx, prof_cmds.prof_add, params, WIZ_PROF_FAIL):
            continue
        prof_item = client.SystemProfiles.first(
            where={'system': sys_item.name, 'name': params['name']})

    return prof_item
# _create_prof()

def _create_sys(client, ctx):
    """
    Perform the steps required to reach the point where the target system
    object is available.

    Args:
        client (Client): potion client to perform server requests
        ctx (Context): click's context object

    Returns:
        System: target system
    """
    # params for system add command
    params = {
        'name': None,
        'type': 'lpar',
        'hyp': None,
        'hostname': None,
        'desc': None
    }
    system_item = None
    while not system_item:
        params['name'] = _prompt(
            WIZ_SYS_NAME, default=params['name'], type=types.NAME)
        try:
            system_item = client.Systems.first(where={'name': params['name']})
        # system name does exist: proceed to creation
        except ItemNotFound:
            system_item = None

        if system_item:
            sys_fields = [
                'name', 'hypervisor', 'type', 'owner', 'project', 'desc']
            print_ver_table(_get_headers(sys_fields, client.Systems),
                            [system_item], sys_fields)
            # system already exists: confirm before using it
            if _confirm(WIZ_SYS_CONFIRM):
                break
            system_item = None
            continue

        # collect system parameters
        params['type'] = _prompt(
            WIZ_SYS_TYPE, default=params['type'], type=types.CONSTANT)
        # make sure user enters an existing hypervisor
        while True:
            params['hyp'] = _prompt(
                WIZ_SYS_HYP, default=params['hyp'], type=types.NAME)
            try:
                client.Systems.first(where={'name': params['hyp']})
            except ItemNotFound:
                params['hyp'] = None
                click.echo(WIZ_SYS_HYP_NOT_FOUND)
                continue
            break
        params['hostname'] = _prompt(
            WIZ_SYS_HOSTNAME, default=params['hostname'], type=types.HOSTNAME)
        params['desc'] = _prompt(WIZ_SYS_DESC, default=params['desc'],
                                 allow_empty=True)

        # try to create the new system
        click.echo('\n' + WIZ_SYS_CREATING)
        if not _invoke(ctx, sys_cmds.add, params, WIZ_SYS_FAIL):
            continue
        system_item = client.Systems.first(where={'name': params['name']})

    return system_item
# _create_sys()

@click.command(
    name='wizard',
    short_help='help to set a system for installation through a '
               'setup wizard')
@click.pass_context
def wizard(ctx):
    """
    help to set a system for installation through a setup wizard
    """
    client = Client()

    # get the target system
    click.echo('\n' + WIZ_START)
    sys_item = _create_sys(client, ctx)

    # get the target activation profile
    click.echo('\n' + WIZ_PROF_START)
    prof_item = _create_prof(client, ctx, sys_item)

    # storage (disks) section
    click.echo('\n' + WIZ_ST_START)
    do_storage = True
    while do_storage:
        _create_disk(client, ctx, sys_item, prof_item)
        # add more disks?
        do_storage = _confirm(WIZ_ST_VOL_MORE)

    # system iface
    click.echo('\n' + WIZ_NET_START)
    do_iface = True
    while do_iface:
        _create_iface(client, ctx, sys_item, prof_item)
        # add more ifaces?
        do_iface = _confirm(WIZ_NET_IFACE_MORE)

    # show a summary of the profile created
    prof_item = prof_item.fetch(prof_item.id)
    prof_item.vols_str = ', '.join(
        ['[{}/{}]'.format(vol.server, vol.volume_id) for vol in
         prof_item.storage_volumes])
    prof_item.mem_str = size_to_str(prof_item.memory)
    parsed_ifaces = []
    for iface in prof_item.system_ifaces:
        if iface.ip_address is not None:
            ip_address = iface.ip_address.rsplit('/', 1)[-1]
            parsed_ifaces.append(
                '[{}/{}]'.format(iface.name, ip_address))
        else:
            parsed_ifaces.append('[{}]'.format(iface.name))
    prof_item.ifaces_str = ', '.join(parsed_ifaces)
    click.echo()
    click.echo(WIZ_PROF_SUMMARY)
    print_hor_table(
        ('System', 'Profile', 'CPU', 'Memory', 'Volumes', 'Interfaces'),
        ((prof_item.system, prof_item.name, prof_item.cpu, prof_item.mem_str,
          prof_item.vols_str, prof_item.ifaces_str),)
    )

    # perform installation or finish wizard
    if not _confirm(WIZ_INSTALL_CONFIRM):
        click.echo(WIZ_END)
        return

    os_instances = [entry for entry in client.OperatingSystems.instances() if
                    entry.name.lower() != 'cms']
    os_fields = ['name', 'pretty_name']
    os_item = None
    while not os_item:
        os_item = _choice_menu(
            os_instances, os_fields, WIZ_INSTALL_OS_ASK, WIZ_INSTALL_OS_TITLE)

    ctx.invoke(
        sys_cmds.autoinstall, os=os_item.name, system=sys_item.name,
        profile=prof_item.name)
# wizard

CMDS = [wizard]
