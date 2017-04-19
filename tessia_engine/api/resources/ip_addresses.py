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
from flask_potion import fields
from tessia_engine.api.exceptions import BaseHttpError, ItemNotFoundError
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import IpAddress, Subnet

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
    'system': 'Associated system',
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
            title=DESC['system'], description=DESC['system'], io='r')

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

        return super().do_create(properties)
    # do_create()

    def do_update(self, properties, id):
        # pylint: disable=invalid-name,redefined-builtin
        """
        Overriden method to perform sanity check on the address provided.
        See parent class for complete docstring.
        """
        # address changed: validate it
        if 'address' in properties:
            # subnet was changed: fetch from database
            if 'subnet' in properties:
                subnet = self._fetch_subnet(properties['subnet']).address
            # subnet not changed: refer to current association
            else:
                subnet = self.manager.read(id).subnet_rel.address
            # verify if ip address is valid and fits subnet's range
            self._assert_address(properties['address'], subnet)
        # subnet changed: validate if address is still within range
        elif 'subnet' in properties:
            subnet = self._fetch_subnet(properties['subnet']).address
            address = self.manager.read(id).address
            # verify if ip address is valid and fits subnet's range
            self._assert_address(address, subnet)

        return super().do_update(properties, id)
    # do_update()
# IpAddressResource
