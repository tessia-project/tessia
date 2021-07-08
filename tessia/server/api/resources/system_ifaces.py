# Copyright 2016, 2017, 2018 IBM Corp.
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
Resource definition
"""

#
# IMPORTS
#
from flask import g as flask_global
from flask_potion import fields
from flask_potion.contrib.alchemy.fields import InlineModel
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from tessia.server.api.exceptions import BaseHttpError
from tessia.server.api.exceptions import ItemNotFoundError
from tessia.server.api.resources.secure_resource import NAME_PATTERN
from tessia.server.api.resources.secure_resource import SecureResource
from tessia.server.db.models import IpAddress, Subnet
from tessia.server.db.models import System, SystemIface, SystemProfile

import ipaddress

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Interface name',
    'osname': 'Network device name',
    'ip_address': 'IP address',
    'mac_address': 'MAC address',
    'system': 'System',
    'type': 'Interface type',
    'attributes': 'Attributes',
    'desc': 'Description',
    'system_profiles': 'Associated system profiles',
}

#
# CODE
#


class SystemIfaceResource(SecureResource):
    """
    Resource for system network interfaces
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = SystemIface

        # name of the resource in the url
        name = 'system-ifaces'

        title = 'Network interfaces'
        description = 'System network interfaces'
        # custom attribute to define one or more schema fields that have a
        # human description for an item, used by api exceptions to report
        # db errors.
        human_identifiers = ['system', 'name']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        name = fields.String(
            title=DESC['name'], description=DESC['name'], pattern=NAME_PATTERN)
        osname = fields.String(
            title=DESC['osname'], description=DESC['osname'], max_length=15,
            pattern=r'^[a-zA-Z][a-zA-Z0-9_\.\-]+$')
        attributes = fields.Custom(
            schema=SystemIface.get_schema('attributes'),
            title=DESC['attributes'], description=DESC['attributes'])
        mac_address = fields.String(
            title=DESC['mac_address'], description=DESC['mac_address'],
            nullable=True, pattern=r'^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$')
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        # relations
        ip_address = fields.String(
            title=DESC['ip_address'], description=DESC['ip_address'],
            nullable=True)
        system = fields.String(
            title=DESC['system'], description=DESC['system'])
        type = fields.String(
            title=DESC['type'], description=DESC['type'])
        profiles = fields.List(
            # InlineModel is a way to use a different sa model in a field while
            # specifying which fields should be displayed.
            InlineModel(
                {
                    # try to keep ourselves restful as possible by providing
                    # the link to the referenced item
                    '$uri': fields.ItemUri(
                        'tessia.server.api.resources.system_profiles.'
                        'SystemProfileResource',
                        attribute='id'
                    ),
                    'name': fields.String(),
                    'system': fields.String(),
                },
                model=SystemProfile,
                io='r'
            ),
            # point to the sa's model relationship containing the entries
            attribute='profiles_rel',
            # for json schema
            title=DESC['system_profiles'],
            description=DESC['system_profiles'],
            # read-only field
            io='r'
        )

    def __init__(self, *args, **kwargs):
        """
        Constructor, loads the necessary json schemas for validations
        """
        super().__init__(*args, **kwargs)
        self._schemas_by_type = {
            'macvtap': [],
            'osa': [],
            'hsi': [],
            'roce': [],
        }
        for schema in SystemIface.get_schema('attributes')['anyOf']:
            if schema['title'].lower().startswith('macvtap'):
                self._schemas_by_type['macvtap'].append(schema)
            elif schema['title'].lower().startswith('osa '):
                self._schemas_by_type['osa'].append(schema)
            elif schema['title'].lower().startswith('hipersockets '):
                self._schemas_by_type['hsi'].append(schema)
            elif schema['title'].lower().startswith('roce '):
                self._schemas_by_type['roce'].append(schema)
    # __init__()

    def _assert_attributes(self, properties, iface_obj):
        """
        Make sure the properties specified are match the iface type
        """
        # for an update action there are existing values
        if iface_obj:
            iface_type = iface_obj.type
            iface_attr = iface_obj.attributes
        else:
            iface_type = ''
            iface_attr = ''

        # values from request
        if 'type' in properties:
            iface_type = properties['type']
        if 'attributes' in properties:
            iface_attr = properties['attributes']

        try:
            schemas = self._schemas_by_type[iface_type.lower()]
        except KeyError:
            msg = 'Invalid interface type {}'.format(iface_type)
            raise BaseHttpError(400, msg=msg)

        validated = False
        for schema in schemas:
            try:
                validate(iface_attr, schema)
            except ValidationError:
                continue
            validated = True
            break
        if not validated:
            msg = 'Field "attributes" is not valid under any JSON schema'
            raise BaseHttpError(400, msg=msg)
    # _assert_attributes()

    def _verify_ip(self, properties, system_obj):
        """
        Verifies the correctness of the subnet/ip_address combination.
        This method will also create the association with the target system in
        the IP address db object if it does not exist yet.

        Args:
            properties (dict): field=value combination for the item to be
                               verify
            system_obj (System): target system db object

        Raises:
            BaseHttpError: - if provided address is in invalid format
                           - if address already assigned to another system
            ItemNotFoundError: if provides address does not exist
        """
        # no ip address in request: nothing to do
        if not properties.get('ip_address'):
            return

        # verify if ip address has a valid format
        try:
            subnet_name, ip_addr = properties['ip_address'].split('/', 1)
            ipaddress.ip_address(ip_addr)
        except ValueError as exc:
            msg = "The value '{}={}' is invalid: {}".format(
                'subnet/ip_address', properties['ip_address'], str(exc))
            raise BaseHttpError(code=400, msg=msg)
        # retrieve object
        ip_obj = IpAddress.query.join(
            Subnet, IpAddress.subnet_id == Subnet.id
        ).filter(
            Subnet.name == subnet_name
        ).filter(
            IpAddress.address == ip_addr
        ).one_or_none()
        if ip_obj is None:
            raise ItemNotFoundError(
                'ip_address', properties['ip_address'], self)

        # target ip address has no system assigned yet: check if user has
        # update permission to it
        if not ip_obj.system_id:
            self._perman.can('UPDATE', flask_global.auth_user, ip_obj,
                             'IP address')
            # create association
            ip_obj.system_id = system_obj.id
        # ip address assigned to different system: cannot assign to two systems
        # at the same time
        elif ip_obj.system_id != system_obj.id:
            msg = ('The IP address is already assigned to system <{}>, remove '
                   'the association first'.format(ip_obj.system_rel.name))
            raise BaseHttpError(409, msg=msg)
    # _verify_ip()

    @staticmethod
    def _verify_mac(properties, iface_obj):
        """
        Validate the mac address' value given the combination of network card
        and system types

        Args:
            properties (dict): field=value dict from create/update request
            iface_obj (SystemIface): target SystemIface db object instance

        Raises:
            BaseHttpError: if combination is not allowed
        """
        iface_type = ''
        iface_attr = {}
        iface_mac = None
        # for an update action there are existing values
        if iface_obj:
            iface_type = iface_obj.type
            iface_attr = iface_obj.attributes
            iface_mac = iface_obj.mac_address

        # values from request
        if 'type' in properties:
            iface_type = properties['type']
        if 'attributes' in properties:
            iface_attr = properties['attributes']
        if 'mac_address' in properties:
            iface_mac = properties['mac_address']

        # non osa cards: mac address is always required
        if iface_type.lower() not in ('osa', 'hsi'):
            if not iface_mac:
                msg = 'A MAC address must be defined'
                raise BaseHttpError(code=422, msg=msg)
            # no more verifications, exit
            return

        # layer2 on: mac address is optional so nothing more to check
        if iface_attr.get('layer2'):
            return

        # create action
        if not iface_obj:
            # layer2 off with mac specified: report mistake
            if properties.get('mac_address'):
                msg = 'When layer2 is off no MAC address should be defined'
                raise BaseHttpError(code=422, msg=msg)
            # no more verifications, exit
            return

        # update action with mac specified: report mistake
        if properties.get('mac_address'):
            msg = 'When layer2 is off no MAC address should be defined'
            raise BaseHttpError(code=422, msg=msg)

        # updating layer2 to off: make sure mac is not defined
        if iface_obj.mac_address:
            properties['mac_address'] = None
    # _verify_mac()

    def do_create(self, properties):
        """
        Use the permissions on the system to allow access to the interfaces.

        Args:
            properties (dict): field=value combination for the item to be
                               created

        Raises:
            BaseHttpError: if provided address is invalid
            Forbidden: in case user has no permission to perform action
            ItemNotFoundError: in case hypervisor profile is specified but not
                               found

        Returns:
            int: id of created item
        """
        target_system = System.query.filter(
            System.name == properties['system']).one_or_none()
        if target_system is None:
            raise ItemNotFoundError('system', properties['system'], self)

        self._perman.can('UPDATE', flask_global.auth_user, target_system,
                         'system')

        self._assert_attributes(properties, None)
        self._verify_mac(properties, None)
        self._verify_ip(properties, target_system)

        item = self.manager.create(properties)
        # don't waste resources building the object in the answer,
        # just give the id and let the client decide if it needs more info (in
        # which case it can use the provided id to request the item)
        return item.id
    # do_create()

    # pylint: disable=arguments-renamed
    def do_delete(self, system_iface_id):
        """
        Verify if the user attempting to delete the instance has permission
        on the corresponding system to do so.

        Args:
            system_iface_id (any): system network interface id

        Raises:
            Forbidden: in case user has no permission to perform action

        Returns:
            bool: True
        """
        entry = self.manager.read(system_iface_id)

        # validate user permission on object
        self._perman.can(
            'UPDATE', flask_global.auth_user, entry.system_rel, 'system')

        self.manager.delete_by_id(system_iface_id)
        return True
    # do_delete()

    # pylint: disable=arguments-renamed
    def do_read(self, system_iface_id):
        """
        Custom implementation of iface reading. Use permissions from the
        associated system to validate access.

        Args:
            system_iface_id (any): system network interface id

        Raises:
            Forbidden: in case user has no rights to read iface

        Returns:
            json: json representation of item
        """

        item = self.manager.read(system_iface_id)

        # validate permission on the object - use the associated system
        self._perman.can('READ', flask_global.auth_user, item.system_rel,
                         'system')

        return item
    # do_read()

    # pylint: disable=arguments-renamed
    def do_update(self, properties, system_iface_id):
        """
        Custom implementation of update. Perform some sanity checks and
        and verify permissions on the corresponding system.

        Args:
            properties (dict): field=value combination for the item to be
                               created
            system_iface_id (any): system network interface id

        Raises:
            ItemNotFoundError: in case hypervisor profile is specified but not
                               found
            BaseHttpError: if request tries to change associated system

        Returns:
            int: id of created item
        """

        item = self.manager.read(system_iface_id)

        # validate permission on the object - use the associated system
        self._perman.can(
            'UPDATE', flask_global.auth_user, item.system_rel, 'system')

        # an iface cannot change its system or type as we only allow to set
        # these on creation
        if 'system' in properties and properties['system'] != item.system:
            raise BaseHttpError(
                422, msg='Interfaces cannot change their associated system')
        if 'type' in properties and properties['type'] != item.type:
            raise BaseHttpError(422, msg='Interfaces cannot change their type')

        self._assert_attributes(properties, item)
        self._verify_mac(properties, item)
        self._verify_ip(properties, item.system_rel)

        updated_item = self.manager.update(item, properties)

        # don't waste resources building the object in the answer,
        # just give the id and let the client decide if it needs more info (in
        # which case it can use the provided id to request the item)
        return updated_item.id
    # do_update()

# SystemIfaceResource
