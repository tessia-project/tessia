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
from tessia_engine.db.models import IpAddress

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

# IpAddressResource
