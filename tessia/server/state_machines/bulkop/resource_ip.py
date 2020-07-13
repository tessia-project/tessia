# Copyright 2019 IBM Corp.
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
Handler of operations on ip addresses
"""

#
# IMPORTS
#
from tessia.server.db.connection import MANAGER
from tessia.server.db.exceptions import AssociationError
from tessia.server.db.models import IpAddress, Subnet, System, SystemIface
from tessia.server.state_machines.bulkop.resource_base import \
    ResourceHandlerBase

import ipaddress
import logging

#
# CONSTANTS AND DEFINITIONS
#

FIELDS_CSV = (
    'SUBNET', 'ADDRESS', 'SYSTEM', 'OWNER', 'PROJECT', 'DESC'
)

#
# CODE
#


class ResourceHandlerIpAddress(ResourceHandlerBase):
    """
    Handler for operations on ip addresses
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor
        """
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(__name__)
        MANAGER.connect()

    # __init__()

    @staticmethod
    def _assert_address(properties):
        """
        Assert that address is a valid ip address.
        """
        subnet_obj = Subnet.query.filter_by(
            name=properties['subnet']).one_or_none()
        if not subnet_obj:
            msg = 'Subnet {} not found'.format(properties['subnet'])
            raise ValueError(msg)

        try:
            address_obj = ipaddress.ip_address(properties['address'])
        except ValueError as exc:
            msg = "IP address {} has invalid format: {}".format(
                properties['address'], str(exc))
            raise ValueError(msg)

        subnet_py = ipaddress.ip_network(subnet_obj.address, strict=True)
        if address_obj not in subnet_py.hosts():
            msg = "Invalid IP address: IP not within subnet address range"
            raise ValueError(msg)
    # _assert_address()

    def _assert_create(self, properties):
        """
        Validate that the create operation may occur
        """
        # validate action
        self._assert_system(None, properties.get('system'))

        new_item = IpAddress()
        # this can raise AssociationError which gets caught by create()
        try:
            new_item.project = properties['project']
        except AssociationError:
            raise ValueError('Specified project {} not found'.format(
                properties['project']))

        self._perman.can('CREATE', self._requester, new_item)
    # _assert_create()

    def _assert_system(self, ip_obj, system_name):
        """
        Retrieve the system and validate user permissions to it.
        """
        # ip is created with no system or updated without changing system:
        # nothing to check
        if (not ip_obj and not system_name) or (
                ip_obj and ip_obj.system_rel and
                ip_obj.system_rel.name == system_name):
            return

        # ip already assigned to a system: make sure user has permission to
        # withdraw the system
        if ip_obj and ip_obj.system_id:
            try:
                self._perman.can(
                    'UPDATE', self._requester, ip_obj.system_rel)
            except PermissionError:
                msg = ('User has no UPDATE permission for the system '
                       'currently holding the IP address')
                raise PermissionError(msg)

        # user only wants to withdraw system: nothind more to check
        if not system_name:
            return

        # verify permission to the target system
        system_obj = System.query.filter_by(name=system_name).one_or_none()
        # system does not exist: report error
        if system_obj is None:
            raise ValueError(
                'Specified system {} not found'.format(system_name))
        # make sure user has update permission on the system
        self._perman.can('UPDATE', self._requester, system_obj, 'system')
    # _assert_system()

    def _assert_update(self, ip_obj, properties):
        """
        Validate that the update operation may occur
        """
        # validate permission on the object
        self._perman.can('UPDATE', self._requester, ip_obj, 'IP address')

        if 'system' in properties and properties['system'] != ip_obj.system:
            self._assert_system(ip_obj, properties['system'])

            # remove existing system iface association
            ifaces = SystemIface.query.filter_by(ip_address_id=ip_obj.id).all()
            for iface_obj in ifaces:
                iface_obj.ip_address = None

        # project changed: make sure user has permission to new project
        if 'project' in properties:
            dummy_item = IpAddress()
            dummy_item.project = properties['project']
            self._perman.can(
                'UPDATE', self._requester, dummy_item, 'project')
    # _assert_update()

    def _render_ip(self, ip_obj, entry):
        """
        Prepare an IP address object for creation/update
        """
        # update ip: evaluate changes
        if ip_obj:
            # compare fields
            ip_obj_dict = {
                key.lower(): getattr(ip_obj, key.lower())
                for key in FIELDS_CSV
            }
            changes_diff = dict(entry.items() - ip_obj_dict.items())
            # no changes to item: nothing to do
            if not changes_diff:
                self._logger.info(
                    'skipping IP address %s/%s (no changes)',
                    ip_obj.subnet, ip_obj.address)
                return

            # validate action
            self._assert_update(ip_obj, changes_diff)

            desc = ''
            for key, value in changes_diff.items():
                desc += ' {}={}(previous <{}>)'.format(
                    key.upper(), changes_diff[key],
                    getattr(ip_obj, key.lower()))
                setattr(ip_obj, key.lower(), changes_diff[key])

            # mark resource as last modified by requester
            ip_obj.modifier_id = self._requester.id

            desc = 'updating IP address {}/{}:{}'.format(
                ip_obj.subnet, ip_obj.address, desc)
            self._logger.info(desc)

        # create new ip
        else:
            # validate action
            self._assert_create(entry)

            ip_obj = IpAddress()
            ip_obj.modifier_id = self._requester.id
            desc = ''
            for key, value in entry.items():
                desc += ' {}={}'.format(key.upper(), value)
                setattr(ip_obj, key, value)

            desc = 'creating IP address {}/{}:{}'.format(
                entry['subnet'], entry['address'], desc)
            self._logger.info(desc)

        MANAGER.session.add(ip_obj)
    # _render_ip()

    @staticmethod
    def headers_match(headers):
        """
        Return True if the provided headers match the resource type
        """
        return tuple(headers) == tuple(FIELDS_CSV)
    # headers_match()

    def render_item(self, entry):
        """
        Receive an entry in dict format with keys in the header format and
        produce the corresponding database object with the changes applied
        """
        # normalize empty string to None
        if not entry['system']:
            entry['system'] = None

        # sanitize by removing any invalid keys
        entry = {
            key: value for key, value in entry.items()
            if key.upper() in FIELDS_CSV
        }

        # check address early to prevent the query from failing with an invalid
        # address format
        self._assert_address(entry)
        ip_obj = IpAddress.query.join(
            'subnet_rel'
        ).filter(
            Subnet.name == entry['subnet']
        ).filter(
            IpAddress.address == entry['address']
        ).with_for_update().one_or_none()

        if ip_obj:
            if not entry['desc']:
                # do not update the field if empty string != None
                if not ip_obj.desc:
                    entry.pop('desc')
                # normalize empty string to None
                else:
                    entry['desc'] = None
        # for new items, normalize empty string to None
        elif not entry['desc']:
            entry['desc'] = None

        try:
            self._render_ip(ip_obj, entry)
        except Exception:
            self._logger.error('failed to process IP address %s/%s',
                               entry['subnet'], entry['address'])
            raise
    # render_item()
# ResourceHandlerIpAddress
