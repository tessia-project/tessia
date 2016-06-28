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
from flask_potion.contrib.alchemy.fields import InlineModel
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import StorageVolume
from tessia_engine.db.models import SystemProfile

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'unique_id': 'Unique id',
    'volume_id': 'Volume id',
    'size': 'Volume size',
    'part_table': 'Partition table',
    'specs': 'Volume specifications',
    'type': 'Volume type',
    'system': 'Attached to system',
    'system_profiles': 'Associated system profiles',
    'pool': 'Attached to storage pool',
    'server': 'Storage server',
    'modified': 'Last modified',
    'desc': 'Description',
    'modifier': 'Modified by',
    'project': 'Project',
    'owner': 'Owner',
}

#
# CODE
#
class StorageVolumeResource(SecureResource):
    """
    Resource for storage volumes
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = StorageVolume

        # name of the resource in the url
        name = 'storage-volumes'

        # internal usage fields
        exclude_fields = ['system_attributes']

        title = 'Storage volume'
        description = 'Storage volume for use by Systems'
        # custom attribute to define one or more schema fields that have a
        # human description for an item, used by api exceptions to report
        # db errors.
        human_identifiers = ['volume_id', 'server']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        unique_id = fields.String(
            title=DESC['unique_id'], description=DESC['unique_id'],
            attribute='id', io='r')
        volume_id = fields.String(
            title=DESC['volume_id'], description=DESC['volume_id'])
        size = fields.PositiveInteger(
            title=DESC['size'], description=DESC['size'])
        # TODO: add format= to specify the json schema for part tables
        part_table = fields.Any(
            title=DESC['part_table'], description=DESC['part_table'],
            nullable=True)
        specs = fields.Object(
            title=DESC['specs'], description=DESC['specs'], nullable=True)
        modified = fields.DateTime(
            title=DESC['modified'], description=DESC['modified'], io='r')
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        # relations
        pool = fields.String(
            title=DESC['pool'], description=DESC['pool'], nullable=True)
        type = fields.String(
            title=DESC['type'], description=DESC['type'])
        server = fields.String(
            title=DESC['server'], description=DESC['server'])
        system = fields.String(
            title=DESC['system'], description=DESC['system'], nullable=True)
        modifier = fields.String(
            title=DESC['modifier'], description=DESC['modifier'], io='r')
        owner = fields.String(
            title=DESC['owner'], description=DESC['owner'], nullable=True)
        project = fields.String(
            title=DESC['project'], description=DESC['project'], nullable=True)
        system_profiles = fields.List(
            # InlineModel is a way to use a different sa model in a field while
            # specifying which fields should be displayed.
            InlineModel(
                {
                    # try to keep ourselves restful as possible by providing
                    # the link to the referenced item
                    '$uri': fields.ItemUri(
                        'tessia_engine.api.resources.system_profiles.'
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

    # TODO: validate if volume type matches server type
    # TODO: demand server to be provided when deleting/updating as there might
    # be more than one volume with same id
# StorageVolumeResource
