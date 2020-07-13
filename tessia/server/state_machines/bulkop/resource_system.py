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
Executor of operations on storage volumes
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
import re

#
# CONSTANTS AND DEFINITIONS
#

FIELDS_CSV = (
    'HYPERVISOR', 'NAME', 'TYPE', 'HOSTNAME', 'IP', 'IFACE', 'LAYER2',
    'PORTNO', 'OWNER', 'PROJECT', 'STATE', 'DESC'
)

GUEST_HYP_MATCHES = {
    'KVM': ['LPAR', 'KVM'],
    'ZVM': ['LPAR', 'ZVM'],
    'LPAR': ['CPC'],
    'CPC': [],
}

#
# CODE
#


class ResourceHandlerSystem(ResourceHandlerBase):
    """
    Handler for operations on systems
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor
        """
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(__name__)
        MANAGER.connect()
    # __init__()

    def _assert_iface_create(self, sys_obj, properties):
        """
        Validate that the system iface create operation may occur
        """
        if sys_obj.id:
            self._perman.can('UPDATE', self._requester, sys_obj, 'system')

        # in case system does not exist it will fail anyway on system
        # creation if requester has no permission

        ip_obj = self._assert_ip(sys_obj, properties)

        # update properties with the correct subnet/ip_address entry
        if ip_obj:
            properties['ip_address'] = '{}/{}'.format(
                ip_obj.subnet, ip_obj.address)
    # _assert_iface_create()

    def _assert_iface_update(self, iface_obj, properties):
        """
        Validate that the system iface update operation may occur
        """
        # an iface cannot change its system
        if 'system' in properties and properties['system'] != iface_obj.system:
            raise ValueError('Tried to change system associated to interface')

        # validate permission on the object - use the associated system
        self._perman.can(
            'UPDATE', self._requester, iface_obj.system_rel, 'system')

        ip_obj = self._assert_ip(iface_obj.system_rel, properties)

        # update properties with the correct subnet/ip_address entry
        if ip_obj:
            properties['ip_address'] = '{}/{}'.format(
                ip_obj.subnet, ip_obj.address)
    # _assert_iface_update()

    def _assert_ip(self, sys_obj, properties):
        """
        Verifies the correctness of the subnet/ip_address combination.
        This method will also create the association with the target system in
        the IP address db object if it does not exist yet.
        """
        # no ip address in request: nothing to do
        if not properties.get('ip_address'):
            return None

        # verify if ip address has a valid format
        if '/' in properties['ip_address']:
            try:
                subnet_name, ip_addr = properties['ip_address'].split('/', 1)
                ipaddress.ip_address(ip_addr)
            except ValueError:
                raise ValueError("Invalid IP address '{}'"
                                 .format(properties['ip_address']))

            # retrieve object
            ip_obj = IpAddress.query.join(
                'subnet_rel'
            ).filter(
                Subnet.name == subnet_name
            ).filter(
                IpAddress.address == ip_addr
            ).one_or_none()
            if not ip_obj:
                raise ValueError('IP address specified not found')

        else:
            try:
                ipaddress.ip_address(properties['ip_address'])
            except ValueError:
                raise ValueError("Invalid IP address '{}'"
                                 .format(properties['ip_address']))
            # retrieve object
            ip_obj = IpAddress.query.filter_by(
                address=properties['ip_address']).all()
            if not ip_obj:
                raise ValueError('IP address specified not found')
            if len(ip_obj) > 1:
                msg = ('Multiple IP addresses found; use the format '
                       'subnet_name/ip_address to uniquely identify it')
                raise ValueError(msg)
            ip_obj = ip_obj[0]

        # target ip address has no system assigned yet: create association
        if not ip_obj.system_id:
            self._perman.can('UPDATE', self._requester, ip_obj, 'IP address')
            # create association
            self._logger.info(
                'updating IP address %s/%s: SYSTEM=%s(previous <None>)',
                ip_obj.subnet, ip_obj.address, sys_obj.name)
            ip_obj.system = sys_obj.name
            MANAGER.session.add(ip_obj)

        # ip address assigned to different system: remove existing association
        elif ip_obj.system_id != sys_obj.id:
            # make sure user has permission to withdraw ip from old system
            try:
                self._perman.can(
                    'UPDATE', self._requester, ip_obj.system_rel, 'system')
            except PermissionError:
                msg = ("User has no UPDATE permission for the system '{}' "
                       "currently holding the IP address"
                       .format(ip_obj.system_rel.name))
                raise PermissionError(msg)

            # check permission to current ip
            self._perman.can('UPDATE', self._requester, ip_obj, 'IP address')

            ifaces = SystemIface.query.filter_by(
                ip_address_id=ip_obj.id, system_id=ip_obj.system_id).all()
            if ifaces:
                self._logger.warning(
                    'removing IP address %s/%s from *all* interfaces of '
                    'system %s', ip_obj.subnet, ip_obj.address, ip_obj.system)

                for iface_obj in ifaces:
                    iface_obj.ip_address = None
                    MANAGER.session.add(iface_obj)

            # create new association
            self._logger.info(
                'updating IP address %s/%s: SYSTEM=%s(previous <%s>)',
                ip_obj.subnet, ip_obj.address, sys_obj.name, ip_obj.system)
            ip_obj.system = sys_obj.name
            MANAGER.session.add(ip_obj)

        return ip_obj
    # _assert_ip()

    def _assert_sys_create(self, properties):
        """
        Validate that the system create operation may occur
        """
        guest_match_list = GUEST_HYP_MATCHES.get(properties['type'])
        # specified type is invalid: report error
        if guest_match_list is None:
            raise ValueError('Invalid system type {}'.format(
                properties['type']))

        # make sure hypervisor has correct type (i.e. a lpar cannot belong to
        # a kvm guest)
        hyp = System.query.filter_by(
            name=properties['hypervisor']).one_or_none()
        # hypervisor provided not found: report error
        if hyp is None:
            raise ValueError('Hypervisor specified {} not found'.format(
                properties['hypervisor']))
        if hyp.type not in guest_match_list:
            raise ValueError('Invalid guest/hypervisor combination')

        new_item = System()
        try:
            new_item.project = properties['project']
        except AssociationError:
            raise ValueError('Specified project {} not found'.format(
                properties['project']))

        self._perman.can('CREATE', self._requester, new_item, 'system')
    # _assert_sys_create()

    def _assert_sys_update(self, sys_obj, properties):
        """
        Validate that the system update operation may occur
        """
        # system type changed: not allowed
        if ('type' in properties and
                properties['type'].upper() != sys_obj.type.upper()):
            msg = 'Tried to change system type from {} to {}'.format(
                sys_obj.type, properties['type'])
            raise ValueError(msg)

        # hypervisor changed: not allowed
        if ('hypervisor' in properties and
                properties['hypervisor'] != sys_obj.hypervisor):
            msg = 'Tried to change hypervisor from {} to {}'.format(
                sys_obj.hypervisor, properties['hypervisor'])
            raise ValueError(msg)

        # validate permission on the object
        self._perman.can('UPDATE', self._requester, sys_obj, 'system')

        # project changed: make sure user has permission to new project
        if 'project' in properties:
            dummy_item = System()
            dummy_item.project = properties['project']
            self._perman.can(
                'UPDATE', self._requester, dummy_item, 'project')
    # _assert_sys_update()

    def _render_iface(self, sys_obj, iface_attrs):
        """
        Prepare an iface db object for creation or update
        """
        # TODO: support kvm guest interfaces
        if sys_obj.type.upper() == 'KVM':
            raise ValueError('KVM guest network interfaces are not supported')

        ccw_group = []
        for devno in iface_attrs['iface'].lower().split(','):
            if '.' not in devno:
                devno = '0.0.' + devno
            if not re.match(r"^([a-f0-9]\.){2}[a-f0-9]{4}$", devno):
                raise ValueError('Invalid format for interface ccwgroup')
            ccw_group.append(devno)
        ccw_group = ','.join(ccw_group)

        try:
            layer2 = {'1': True, '0': False}[iface_attrs['layer2']]
        except KeyError:
            raise ValueError('Value for layer2 must be 1 or 0')
        if iface_attrs['portno'] not in ('0', '1'):
            raise ValueError('Value for portno must be 1 or 0')

        entry = {
            'ip_address': iface_attrs['ip'],
            'attributes': {
                'ccwgroup': ccw_group,
                'layer2': layer2,
                'portno': iface_attrs['portno'],
            }
        }

        # new system: interface does not exist yet
        if not sys_obj.id:
            iface_obj = None
        # system already exist: see if interface already exists
        else:
            iface_obj = SystemIface.query.filter_by(
                system_id=sys_obj.id
            ).filter(
                SystemIface.attributes['ccwgroup'].astext == ccw_group
            ).one_or_none()

        if iface_obj:
            # compare fields
            changes_diff = {}
            if not iface_obj.ip_address_rel or (
                    iface_obj.ip_address_rel and
                    entry['ip_address'] != iface_obj.ip_address_rel.address):
                changes_diff['ip_address'] = entry['ip_address']
            # normalize default values
            if entry['attributes']['portno'] == '0' and (
                    'portno' not in iface_obj.attributes):
                entry['attributes'].pop('portno')
            if not entry['attributes']['layer2'] and (
                    'layer2' not in iface_obj.attributes):
                entry['attributes'].pop('layer2')
            # now compare both dicts
            if entry['attributes'] != iface_obj.attributes:
                changes_diff['attributes'] = entry['attributes']

            # no changes to item: nothing to do
            if not changes_diff:
                self._logger.info('skipping iface %s/%s (no changes)',
                                  sys_obj.name, iface_obj.name)
                return

            # validate action
            self._assert_iface_update(iface_obj, changes_diff)

            desc = ''
            for key, value in changes_diff.items():
                desc += ' {}={}(previous <{}>)'.format(
                    key.upper(), changes_diff[key],
                    getattr(iface_obj, key.lower()))
                setattr(iface_obj, key.lower(), changes_diff[key])

            desc = 'updating iface {}/{}:{}'.format(
                sys_obj.name, iface_obj.name, desc)
            self._logger.info(desc)

        # create new iface
        else:
            # validate action
            self._assert_iface_create(sys_obj, entry)

            iface_obj = SystemIface()
            iface_obj.system = sys_obj.name
            iface_obj.type = 'OSA'

            desc = ''
            for key, value in entry.items():
                desc += ' {}={}'.format(key.upper(), value)
                setattr(iface_obj, key, value)

            short_ccw = iface_obj.attributes['ccwgroup'].split(
                ',')[0].replace("0.0.", "")
            iface_obj.name = 'osa-{}'.format(short_ccw)
            iface_obj.osname = 'enc{}'.format(short_ccw)

            desc = 'creating iface {}/{}:{}'.format(
                sys_obj.name, iface_obj.name, desc)
            self._logger.info(desc)

        MANAGER.session.add(iface_obj)
    # _render_iface()

    def _render_system(self, sys_obj, entry):
        """
        Prepare system and iface db objects for creation or update
        """
        # normalize empty string to None
        if not entry['ip']:
            raise ValueError('A system must have an IP address assigned')
        # sanitize by removing any invalid keys
        entry = {
            key: value for key, value in entry.items()
            if key.upper() in FIELDS_CSV
        }

        compare_fields = [field.lower() for field in FIELDS_CSV]
        iface_attrs = {}
        for field in ('ip', 'iface', 'layer2', 'portno'):
            compare_fields.remove(field)
            iface_attrs[field] = entry.pop(field)

        # update system: evaluate changes
        if sys_obj:
            if not entry['desc']:
                # do not update the field if empty string != None
                if not sys_obj.desc:
                    entry.pop('desc')
                # normalize empty string to None
                else:
                    entry['desc'] = None

            # compare fields
            sys_obj_dict = {
                key: getattr(sys_obj, key.lower()) for key in compare_fields
            }
            changes_diff = dict(entry.items() - sys_obj_dict.items())

            self._render_iface(sys_obj, iface_attrs)
            # no changes to item: nothing to do
            if not changes_diff:
                self._logger.info('skipping system %s (no changes)',
                                  sys_obj.name)
                return

            # validate action
            self._assert_sys_update(sys_obj, changes_diff)

            desc = ''
            for key, value in changes_diff.items():
                desc += ' {}={}(previous <{}>)'.format(
                    key.upper(), changes_diff[key],
                    getattr(sys_obj, key.lower()))
                setattr(sys_obj, key.lower(), changes_diff[key])
            desc = 'updating system {}:{}'.format(sys_obj.name, desc)
            self._logger.info(desc)

            # mark resource as last modified by requester
            sys_obj.modifier_id = self._requester.id
            MANAGER.session.add(sys_obj)

        # create new system
        else:
            # validate action
            self._assert_sys_create(entry)

            # normalize empty string to None
            if not entry['desc']:
                entry['desc'] = None

            sys_obj = System()
            sys_obj.model = 'ZGENERIC'
            sys_obj.modifier_id = self._requester.id
            desc = ''
            for key, value in entry.items():
                desc += ' {}={}'.format(key.upper(), value)
                setattr(sys_obj, key, value)
            # add the object to the session early so that _render_iface can
            # see it
            MANAGER.session(  # pylint: disable=not-callable
            ).enable_relationship_loading(sys_obj)
            MANAGER.session.add(sys_obj)

            self._render_iface(sys_obj, iface_attrs)

            desc = 'creating system {}:{}'.format(sys_obj.name, desc)
            self._logger.info(desc)
    # _render_system()

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
        sys_obj = System.query.filter_by(
            name=entry['name']).with_for_update().one_or_none()
        try:
            self._render_system(sys_obj, entry)
        except Exception:
            self._logger.error('failed to process system %s', entry['name'])
            raise
    # render_item()
# ResourceHandlerSystem
