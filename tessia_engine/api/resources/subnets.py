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
from tessia_engine.api.exceptions import BaseHttpError
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import Subnet

import ipaddress

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Subnet name',
    'zone': 'Network zone',
    'address': 'Network address',
    'gateway': 'Gateway',
    'dns_1': 'DNS server 1',
    'dns_2': 'DNS server 2',
    'vlan': 'VLAN',
    'modified': 'Last modified',
    'desc': 'Description',
    'modifier': 'Modified by',
    'project': 'Project',
    'owner': 'Owner',
}

#
# CODE
#
class SubnetResource(SecureResource):
    """
    Resource for subnets
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = Subnet

        # name of the resource in the url
        name = 'subnets'

        title = 'Subnet'
        description = 'A subnet holds a range of IP addresses'
        human_identifiers = ['name']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        name = fields.String(
            title=DESC['name'], description=DESC['name'])
        address = fields.String(
            title=DESC['address'], description=DESC['address'])
        gateway = fields.String(
            title=DESC['gateway'], description=DESC['gateway'], nullable=True)
        dns_1 = fields.String(
            title=DESC['dns_1'], description=DESC['dns_1'], nullable=True)
        dns_2 = fields.String(
            title=DESC['dns_2'], description=DESC['dns_2'], nullable=True)
        vlan = fields.PositiveInteger(
            title=DESC['vlan'], description=DESC['vlan'], nullable=True)
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
        zone = fields.String(
            title=DESC['zone'], description=DESC['zone'])

    @staticmethod
    def _assert_address(address, field_name, network=False):
        """
        Assert that address is a valid ip address.

        Args:
            address (str): network or ip address
            field_name (str): field name to report in case of error
            network (bool): whether it is a network address

        Raises:
            BaseHttpError: in case provided address is invalid

        Returns:
            None
        """
        if address is None:
            return
        try:
            if network:
                ipaddress.ip_network(address, strict=True)
            else:
                ipaddress.ip_address(address)
        except ValueError as exc:
            msg = "The value '{}={}' is invalid: {}".format(
                field_name, address, str(exc))
            raise BaseHttpError(code=400, msg=msg)
    # _assert_address()

    @staticmethod
    def _assert_gw_range(address, gateway, gw_changed):
        """
        Assert that gateway is a valid ip address (i.e. contained in subnet's
        address range)

        Args:
            address (str): network ip address
            gateway (str): gateway ip address
            gw_changed (bool): whether the gateway is being changed or not

        Raises:
            BaseHttpError: in case provided gateway ip is invalid

        Returns:
            None
        """
        if gateway is None:
            return

        address_obj = ipaddress.ip_network(address, strict=True)
        gw_obj = ipaddress.ip_address(gateway)

        # ip within subnet range: nothing to do
        if gw_obj in address_obj.hosts():
            return

        if gw_changed:
            msg = ("The value 'gateway={}' is invalid: ip not within "
                   "subnet address range".format(gateway))
        else:
            msg = (
                "The value 'address={}' is invalid: 'gateway={}' must be "
                "updated too to match new address range".format(
                    address, gateway)
            )

        raise BaseHttpError(code=400, msg=msg)
    # _assert_gw_range()

    def do_create(self, properties):
        """
        Overriden method to perform sanity checks on the address and gateway
        combinations. See parent class for complete docstring.
        """
        for field in ('dns_1', 'dns_2'):
            value = properties.get(field)
            self._assert_address(value, field)

        # verify if address is a valid ip
        self._assert_address(
            properties['address'], 'address', network=True)

        # gateway specified: perform validation
        if 'gateway' in properties:
            gateway = properties['gateway']
            # check if it's a valid ip
            self._assert_address(gateway, 'gateway')
            # validate it's within the subnet address range
            self._assert_gw_range(properties['address'], gateway, True)

        return super().do_create(properties)
    # do_create()

    def do_update(self, properties, id):
        # pylint: disable=invalid-name,redefined-builtin
        """
        Overriden method to perform sanity checks on the address and gateway
        combinations. See parent class for complete docstring.
        """
        for field in ('dns_1', 'dns_2'):
            value = properties.get(field)
            self._assert_address(value, field)

        # network address changed: verify new value
        if 'address' in properties:
            address = properties['address']
            # validate it is a valid network ip
            self._assert_address(address, 'address', network=True)

            # gateway changed: validate new value and subnet range
            if 'gateway' in properties:
                gateway = properties['gateway']
                self._assert_address(gateway, 'gateway')
                self._assert_gw_range(address, gateway, True)
            # gateway not changed: check if gateway is still valid for new
            # network address
            else:
                gateway = self.manager.read(id).gateway
                self._assert_gw_range(address, gateway, False)

        # gateway changed: verify new value and if it fits the subnet's
        # address range
        elif 'gateway' in properties:
            gateway = properties['gateway']
            self._assert_address(gateway, 'gateway')
            # retrieve existing address value
            address = self.manager.read(id).address
            self._assert_gw_range(address, gateway, True)

        return super().do_update(properties, id)
    # do_update()

# SubnetResource
