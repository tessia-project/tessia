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
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import Subnet

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
        address = fields.Uri(
            title=DESC['address'], description=DESC['address'])
        gateway = fields.Uri(
            title=DESC['gateway'], description=DESC['gateway'], nullable=True)
        dns_1 = fields.Uri(
            title=DESC['dns_1'], description=DESC['dns_1'], nullable=True)
        dns_2 = fields.Uri(
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

# SubnetResource
