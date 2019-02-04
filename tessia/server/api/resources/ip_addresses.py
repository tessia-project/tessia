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
Resource definition
"""

#
# IMPORTS
#
from flask import g as flask_global
from flask_potion import fields
from flask_potion.instances import Pagination
from tessia.server.api.exceptions import BaseHttpError, ItemNotFoundError
from tessia.server.api.resources.secure_resource import SecureResource
from tessia.server.db.models import IpAddress, Subnet, System, SystemIface

import ipaddress

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'address': 'IP address',
    'subnet': 'Part of subnet',
    'modified': 'Last modified',
    'desc': 'Description',
    'modifier': 'Modified by',
    'project': 'Project',
    'owner': 'Owner',
    'system': 'Assigned to system',
}

#
# CODE
#
class IpAddressResource(SecureResource):
    """
    Resource for ip addresses
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = IpAddress

        # name of the resource in the url
        name = 'ip-addresses'

        title = 'IP address'
        description = 'An IP address that belongs to a subnet '
        human_identifiers = ['address', 'subnet']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        address = fields.String(
            title=DESC['address'], description=DESC['address'])
        modified = fields.DateTime(
            title=DESC['modified'], description=DESC['modified'], io='r')
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        modifier = fields.String(
            title=DESC['modifier'], description=DESC['modifier'], io='r')
        owner = fields.String(
            title=DESC['owner'], description=DESC['owner'], nullable=True)
        project = fields.String(
            title=DESC['project'], description=DESC['project'], nullable=True)
        # relations
        subnet = fields.String(
            title=DESC['subnet'], description=DESC['subnet'])
        system = fields.String(
            title=DESC['system'], description=DESC['system'], nullable=True)

    @staticmethod
    def _assert_address(address, subnet):
        """
        Assert that address is a valid ip address.

        Args:
            address (str): ip address
            subnet (str): subnet's address

        Raises:
            BaseHttpError: in case provided address is invalid
        """
        try:
            address_obj = ipaddress.ip_address(address)
        except ValueError as exc:
            msg = "The value '{}={}' is invalid: {}".format(
                'address', address, str(exc))
            raise BaseHttpError(code=400, msg=msg)

        subnet_obj = ipaddress.ip_network(subnet, strict=True)
        if address_obj not in subnet_obj.hosts():
            msg = ("The value 'address={}' is invalid: ip not within "
                   "subnet address range".format(address))
            raise BaseHttpError(code=400, msg=msg)
    # _assert_address()

    def _assert_system(self, item, system_name):
        """
        Retrieve the system and validate user permissions to it.

        Args:
            item (IpAddress): provided in case of an update, None for
                                  create
            system_name (str): target system to assign volume

        Raises:
            ItemNotFoundError: if system does not exist
            PermissionError: if user has no permission to current system
        """
        # ip is created with no system or updated without changing system:
        # nothing to check
        if (not item and not system_name) or (
                item and item.system_rel and
                item.system_rel.name == system_name):
            return

        # ip already assigned to a system: make sure user has permission to
        # withdraw the system
        if item and item.system_id:
            try:
                self._perman.can('UPDATE', flask_global.auth_user,
                                 item.system_rel)
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
            raise ItemNotFoundError('system', system_name, self)
        # make sure user has update permission on the system
        self._perman.can('UPDATE', flask_global.auth_user, system_obj,
                         'system')
    # _assert_system()

    def _fetch_subnet(self, name):
        """
        Helper method to fetch a subnet instance.

        Args:
            name (str): subnet's name

        Raises:
            ItemNotFoundError: in case instance is not in db

        Returns:
            Subnet: db's instance
        """
        try:
            subnet = Subnet.query.filter_by(name=name).one()
        except:
            raise ItemNotFoundError('subnet', name, self)

        return subnet
    # _fetch_subnet()

    def do_create(self, properties):
        """
        Overriden method to perform sanity check on the address provided.
        See parent class for complete docstring.
        """
        self._assert_address(
            properties['address'],
            self._fetch_subnet(properties['subnet']).address
        )

        self._assert_system(None, properties.get('system'))

        return super().do_create(properties)
    # do_create()

    def do_list(self, **kwargs):
        """
        Verify if the user attempting to list has permissions to do so.

        Args:
            kwargs (dict): contains keys like 'where' (filtering) and
                           'per_page' (pagination), see potion doc for details

        Returns:
            list: list of items retrieved, can be an empty in case no items are
                  found or a restricted user has no permission to see them
        """
        if not flask_global.auth_user.restricted:
            return self.manager.paginated_instances(**kwargs)

        ret_instances = []
        for instance in self.manager.instances(kwargs.get('where'),
                                               kwargs.get('sort')):
            # restricted user may list if they have a role in the project
            try:
                self._perman.can(
                    'READ', flask_global.auth_user, instance)
            except PermissionError:
                if not instance.system_id:
                    continue
                # they can list if the disk is assigned to a system they have
                # access
                try:
                    self._perman.can('READ', flask_global.auth_user,
                                     instance.system_rel, 'system')
                except PermissionError:
                    continue
            ret_instances.append(instance)

        return Pagination.from_list(
            ret_instances, kwargs['page'], kwargs['per_page'])
    # do_list()

    def do_read(self, id):
        """
        Custom implementation of item reading. Use permissions from the
        associated system to validate access if necessary.

        Args:
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Raises:
            PermissionError: if user has no permission to the item

        Returns:
            json: json representation of item
        """
        # pylint: disable=redefined-builtin
        item = self.manager.read(id)
        if not flask_global.auth_user.restricted:
            return item

        # restricted user may read if they have a role in the project
        try:
            self._perman.can('READ', flask_global.auth_user, item)
        except PermissionError:
            if not item.system_id:
                raise
            # they can read if the disk is assigned to a system they have
            # access
            self._perman.can('READ', flask_global.auth_user,
                             item.system_rel, 'system')

        return item
    # do_read()

    def do_update(self, properties, id):
        # pylint: disable=invalid-name,redefined-builtin
        """
        Overriden method to perform sanity check on the address provided.
        See parent class for complete docstring.
        """
        if 'subnet' in properties:
            raise BaseHttpError(
                422, msg='IP addresses cannot change their subnet')

        ip_obj = self.manager.read(id)

        # address changed: verify if it's valid and fits subnet's range
        if 'address' in properties:
            self._assert_address(properties['address'],
                                 ip_obj.subnet_rel.address)

        # system assignment changed: validate permissions and remove any
        # interfaces assigned
        if 'system' in properties and properties['system'] != ip_obj.system:
            self._assert_system(ip_obj, properties['system'])

            # remove existing system iface association
            ifaces = SystemIface.query.filter_by(ip_address_id=id).all()
            for iface_obj in ifaces:
                iface_obj.ip_address = None

        return super().do_update(properties, id)
    # do_update()
# IpAddressResource
