# Copyright 2017 IBM Corp.
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
Custom types for usage in command options
"""

#
# IMPORTS
#
from tessia.cli.utils import str_to_size
import click
import ipaddress
import re

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class ActionType(click.ParamType):
    """
    Represents action types for job requests.
    """
    ALLOWED_TYPES = ('cancel', 'submit')
    name = 'action_type'

    def convert(self, value, param, ctx):
        """
        Make sure value is correct.
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        if value.lower() not in self.ALLOWED_TYPES:
            self.fail('action type must be one of: {}'.format(
                ', '.join(self.ALLOWED_TYPES)), param, ctx)

        return value.upper()
    # convert()

    def get_metavar(self, param):
        """How the value for this type will look at the help page"""
        return '[{}]'.format('|'.join(self.ALLOWED_TYPES))
# ActionType

ACTION_TYPE = ActionType()

class AutoTemplate(click.ParamType):
    """
    Represents an autofile template (i.e. kickstart) content extracted from a
    local file
    """
    name = 'file_path'

    def convert(self, value, param, ctx):
        """
        Read the file and validate the content before returning it.
        """
        with click.open_file(value, 'r') as file_stream:
            content = file_stream.read()

        # TODO: perform some sanity checks
        return content
    # convert()
# AutoTemplate

AUTO_TEMPLATE = AutoTemplate()

class Constant(click.ParamType):
    """
    Represents a string constant, usually used for (storage/system/etc.)
    types.
    """
    name = 'string'

    def convert(self, value, param, ctx):
        """
        Converts to uppercase.
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        return value.upper()
    # convert()
# Constant

CONSTANT = Constant()

class CustomIntRange(click.IntRange):
    """
    Same as cick.IntRange but with a different description
    """
    name = 'integer'
# CustomIntRange

class FcpPath(click.ParamType):
    """
    Represents a FCP path type
    """
    name = 'adapter_devno,wwpn'

    def convert(self, value, param, ctx):
        """
        Validate and convert a string in the format devno,wwpn to a tuple
        after removing possible '0x' prefixes.
        """
        try:
            devno, wwpn = value.lower().split(',')
        except ValueError:
            self.fail('{} is not a valid FCP path'.format(value), param, ctx)

        # save original values for unsuccessful verification output
        orig_devno = devno
        orig_wwpn = wwpn

        # format and validate devno format
        if devno.find('.') < 0:
            devno = '0.0.' + devno
        ret = re.match(r"^(([a-fA-F0-9]\.){2})?[a-fA-F0-9]{4}$", devno)
        if ret is None:
            self.fail('{} is not a valid devno'.format(orig_devno), param, ctx)

        # format and validate wwpn format
        if wwpn.startswith('0x'):
            wwpn = wwpn[2:]
        ret = re.match(r'^[a-f0-9]{16}$', wwpn)
        if ret is None:
            self.fail('{} is not a valid wwpn'.format(orig_wwpn), param, ctx)

        return (devno, wwpn)
    # convert()
# FcpPath

FCP_PATH = FcpPath()

class Hostname(click.ParamType):
    """
    Represents a hostname or ip address
    """
    name = 'hostname'

    def convert(self, value, param, ctx):
        """
        Make sure it follows the pattern accepted by the server
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        ret = re.match(r"^[a-zA-Z0-9_\:\.\-]+$", value)
        if ret is None:
            self.fail(
                "'{}' is not a valid hostname".format(value), param, ctx)

        return value
    # convert()
# Hostname

HOSTNAME = Hostname()

class IPaddress(click.ParamType):
    """
    Represents ip address
    """
    name = 'ip_address'

    def convert(self, value, param, ctx):
        """
        Make sure it follows the pattern accepted by the server
        """
        if not value:
            self.fail('value may not be empty', param, ctx)
        try:
            ipaddress.ip_address(value)
        except ValueError:
            self.fail(
                '{} is not a valid ip address'.format(value), param, ctx)

        return value
    # convert()
#IPaddress

IPADDRESS = IPaddress()

class JobType(click.ParamType):
    """
    Represents job types.
    """
    ALLOWED_TYPES = ('ansible', 'autoinstall', 'echo', 'powerman')
    name = 'job_type'

    def convert(self, value, param, ctx):
        """
        Make sure value is correct.
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        value = value.lower()
        if value not in self.ALLOWED_TYPES:
            self.fail("job type must be one of: {}".format(
                ', '.join(self.ALLOWED_TYPES)), param, ctx)

        return value
    # convert()

    def get_metavar(self, param):
        """How the value for this type will look at the help page"""
        return '[{}]'.format('|'.join(self.ALLOWED_TYPES))
# JobType

JOB_TYPE = JobType()

class Libvirtxml(click.ParamType):
    """
    Represents a libvirt xml content extracted from a local file
    """
    name = 'xml_file'

    def convert(self, value, param, ctx):
        """
        Read the file and validate the xml content before returning it.
        """
        # no file specified: return empty string so that the caller can
        # interpret it as unsetting the parameter.
        if not value:
            return value

        with click.open_file(value, 'r') as file_stream:
            xml_content = file_stream.read()

        # TODO: perform some sanity checks
        return xml_content
    # convert()
# Libvirtxml

LIBVIRT_XML = Libvirtxml()

class Login(click.ParamType):
    """
    Represents a user's login
    """
    name = 'login'

    def convert(self, value, param, ctx):
        """
        Make sure it follows the pattern accepted by the server
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        ret = re.match(r"^[a-zA-Z0-9_\:\@\.\-]+$", value)
        if ret is None:
            msg = ("'{}' is not a valid login, it may only contain "
                   "letters, numbers, '@', '.', and '-'".format(value))
            self.fail(msg, param, ctx)

        return value
    # convert()
# Login

LOGIN = Login()

class MACaddress(click.ParamType):
    """
    Represents mac address
    """
    name = 'mac_address'

    def convert(self, value, param, ctx):
        """
        Make sure it follows the pattern accepted by the server
        """
        if not value:
            # value is empty and context allows it: just return
            if ctx.meta.get('MACaddress.allow_empty'):
                return value
            self.fail('value may not be empty', param, ctx)

        ret = re.match(r"^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$", value)
        if ret is None:
            msg = ("{} is not a valid mac address".format(value))
            self.fail(msg, param, ctx)

        return value
    # convert()
# MACaddress
MACADDRESS = MACaddress()

class MibSize(click.ParamType):
    """
    A representation of a size in mebibytes
    """
    name = 'size'

    def convert(self, value, param, ctx):
        """
        Receives a human size (i.e. 10GB) and converts to an integer size in
        mebibytes.
        """
        try:
            int_value = str_to_size(value)
        except ValueError:
            self.fail('{} is not a valid size'.format(value), param, ctx)

        return int_value
    # convert()
# MibSize
MIB_SIZE = MibSize()

class MountPoint(click.ParamType):
    """
    A mount point for a partition
    """
    name = 'mount_point'

    def convert(self, value, param, ctx):
        """
        Validates that the value is a valid mount point.
        """
        if not value:
            # value is empty and context allows it: just return
            if ctx.meta.get('MountPoint.allow_empty'):
                return value
            self.fail('value may not be empty', param, ctx)

        ret = re.match(r"^/[a-z0-9A-Z/\-\._]*$", value)
        if ret is None:
            self.fail(
                '{} is not a valid mount point'.format(value), param, ctx)

        return value
    # convert()
# MountPoint
MOUNT_POINT = MountPoint()

class Name(click.ParamType):
    """
    Represents the name of an entity
    """
    name = 'name'

    def convert(self, value, param, ctx):
        """
        Make sure it follows the pattern accepted by the server
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        ret = re.match(r'^\w+[\w\s\.\-]+$', value)
        if ret is None:
            msg = ("'{}' is not a valid name, it must start with a letter or "
                   "number, have at least 2 characters and may only contain "
                   "letters, numbers, blanks, '.', and '-'".format(value))
            self.fail(msg, param, ctx)

        return value
    # convert()
# Name

NAME = Name()

class QethGroup(click.ParamType):
    """
    Represents a qeth group for use with OSA cards
    """
    name = 'read,write,data'

    def convert(self, value, param, ctx):
        """
        Validate and convert a string in the format read_id,write_id,data_id
        to a tuple after removing possible '0x' prefixes.
        """
        try:
            devnos = value.lower().split(',')
            if len(devnos) != 3:
                raise ValueError
        except ValueError:
            self.fail(
                '{} is not a valid qeth ccwgroup'.format(value), param, ctx)

        # format and validate for devno format
        result = []
        for devno in devnos:
            orig_devno = devno
            if devno.startswith('0x'):
                devno = '0.0.' + devno[2:]
            elif devno.find('.') < 0:
                devno = '0.0.' + devno
            ret = re.match(r"^([a-fA-F0-9]\.){2}[a-fA-F0-9]{4}$", devno)
            if ret is None:
                self.fail(
                    '{} is not a valid devno'.format(orig_devno), param, ctx)
            result.append(devno)

        return ','.join(result)
    # convert()
# QethGroup

QETH_GROUP = QethGroup()

class ScsiWwid(click.ParamType):
    """
    Represents a SCSI's World Wide Identifier
    """
    name = 'scsi_wwid'

    def convert(self, value, param, ctx):
        """
        Make sure it follows the pattern accepted by the server
        """
        orig_value = value
        value = value.lower()
        ret = re.match(r"^[a-z0-9]+$", value)
        if ret is None:
            self.fail('{} is not a valid wwid'.format(orig_value), param, ctx)

        return value
    # convert()
# ScsiWwid
SCSI_WWID = ScsiWwid()

class Subnet(click.ParamType):
    """
    Represents a subnet
    """
    name = 'subnet'

    def convert(self, value, param, ctx):
        """
        Make sure it follows the pattern accepted by the server
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        ret = re.match(r"^\w+[\w\s\.\-]+$", value)
        if ret is None:
            self.fail('{} is not a valid subnet'.format(value), param, ctx)

        return value
    # convert()
# Subnet
SUBNET = Subnet()

class Text(click.ParamType):
    """
    Represents any non-empty text.
    """
    name = 'text'

    def convert(self, value, param, ctx):
        """
        Make sure the value accepted by the server
        """
        if not value:
            # value is empty and context allows it: just return
            if ctx.meta.get('Text.allow_empty'):
                return value
            self.fail('value may not be empty', param, ctx)

        return value
# Text

TEXT = Text()

class Url(click.ParamType):
    """
    Represents any url.
    """
    name = 'url'

    def convert(self, value, param, ctx):
        """
        Make sure it follows the pattern accepted by the server
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        ret = re.match(r"^[a-zA-Z0-9_\:\@\.\/\-]+$", value)
        if ret is None:
            self.fail(
                "'{}' is not a valid url".format(value), param, ctx)

        return value
    # convert()
# Url

URL = Url()

class VerbosityLevel(click.ParamType):
    """
    Represents verbosity levels for jobs.
    """
    ALLOWED_LEVELS = ("critical", "error", "warning", "info", "debug")
    name = 'verbosity_level'

    def convert(self, value, param, ctx):
        """
        Convert values to uppercase
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        if value.lower() not in self.ALLOWED_LEVELS:
            self.fail('verbosity level must be one of: {}'.format(
                ', '.join(self.ALLOWED_LEVELS)), param, ctx)

        return value.upper()
    # convert

    def get_metavar(self, param):
        """How the value for this type will look at the help page"""
        return '[{}]'.format('|'.join(self.ALLOWED_LEVELS))

# VerbosityLevel

VERBOSITY_LEVEL = VerbosityLevel()

class VolumeId(click.ParamType):
    """
    Represents the id of a storage volume
    """
    name = 'volume_id'

    def convert(self, value, param, ctx):
        """
        Make sure it follows the pattern accepted by the server
        """
        if not value:
            self.fail('value may not be empty', param, ctx)

        value = value.lower()
        ret = re.match(r"^[a-z0-9_\.\-]+$", value)
        if ret is None:
            self.fail(
                "'{}' is not a valid volume id".format(value), param, ctx)

        return value
    # convert()
# VolumeId

VOLUME_ID = VolumeId()
