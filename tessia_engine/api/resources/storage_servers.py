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
from tessia_engine.api.resources.secure_resource import NAME_PATTERN
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import StorageServer

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Name',
    'hostname': 'Hostname',
    'model': 'Model',
    'type': 'Server type',
    'fw_level': 'Firmware level',
    'modified': 'Last modified',
    'desc': 'Description',
    'modifier': 'Modified by',
    'project': 'Project',
    'owner': 'Owner',
}

#
# CODE
#
class StorageServerResource(SecureResource):
    """
    Resource for storage servers
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = StorageServer

        # name of the resource in the url
        name = 'storage-servers'

        # not used at the moment
        exclude_fields = ['attributes', 'username', 'password']

        title = 'Storage Server'
        description = 'A storage server contains many storage volumes'
        # custom attribute to define one or more schema fields that have a
        # human description for an item, used by integrity exceptions to
        # parse db errors.
        human_identifiers = ['name']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        name = fields.String(
            title=DESC['name'], description=DESC['name'], pattern=NAME_PATTERN)
        hostname = fields.String(
            title=DESC['hostname'], description=DESC['hostname'],
            nullable=True)
        model = fields.String(
            title=DESC['model'], description=DESC['model'])
        fw_level = fields.String(
            title=DESC['fw_level'], description=DESC['fw_level'],
            nullable=True)
        modified = fields.DateTime(
            title=DESC['modified'], description=DESC['modified'], io='r')
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        # relations
        type = fields.String(title=DESC['type'], description=DESC['type'])
        modifier = fields.String(
            title=DESC['modifier'], description=DESC['modifier'], io='r')
        project = fields.String(
            title=DESC['project'], nullable=True, description=DESC['project'])
        owner = fields.String(
            title=DESC['owner'], nullable=True, description=DESC['owner'])

# StorageServerResource
