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
from tessia_engine.api.exceptions import BaseHttpError, ItemNotFoundError
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import StorageVolume
from tessia_engine.db.models import StorageServer
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

MSG_INVALID_PTABLE = (
    "The value 'part_table' is invalid: sum of partitions sizes ({}) is "
    "bigger than volume's size ({})"
)

MSG_INVALID_TYPE = (
    "The value 'type={}' is invalid: it does not match storage server "
    "type '{}'"
)

# support map between storage servers and volumes types
VOL_SERVER_MAP = {
    'DASD-FCP': ['DASD', 'FCP'],
    'ISCSI': ['ISCSI'],
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

        # some fields do make sense to be searchable so we disable them
        filters = {
            'part_table': False,
            'spec': False,
            '*': True
        }

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
        part_table = fields.Custom(
            schema=StorageVolume.get_schema('part_table'),
            title=DESC['part_table'], description=DESC['part_table'],
            nullable=True)
        specs = fields.Custom(
            schema=StorageVolume.get_schema('specs'),
            title=DESC['specs'], description=DESC['specs'], nullable=True)
        modified = fields.DateTime(
            title=DESC['modified'], description=DESC['modified'], io='r')
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        # relations
        # association with a pool is done via pool's entry point
        pool = fields.String(
            title=DESC['pool'], description=DESC['pool'], io='r')
        type = fields.String(
            title=DESC['type'], description=DESC['type'])
        server = fields.String(
            title=DESC['server'], description=DESC['server'])
        # association with a system is done via system profiles
        system = fields.String(
            title=DESC['system'], description=DESC['system'], io='r')
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

    @staticmethod
    def _assert_ptable(part_table, vol_size):
        """
        Assert that the total size of the partitions do not exceed the volume's
        assigned size.

        Args:
            part_table (dict): partition table
            vol_size (int): volume size

        Raises:
            BaseHttpError: in case types do not match

        Returns:
            None
        """
        if part_table is None:
            return

        # dict format was already validated by schema
        table_size = sum([part['size'] for part in part_table['table']])

        if table_size > vol_size:
            msg = MSG_INVALID_PTABLE.format(table_size, vol_size)
            raise BaseHttpError(code=400, msg=msg)
    # _assert_ptable()

    def _assert_type(self, server, vol_type):
        """
        Assert that the volume type selected is the same as the selected
        storage server.

        Args:
            server (str): storage server's name or instance
            vol_type (str): volume type

        Raises:
            BaseHttpError: in case types do not match
            ItemNotFoundError: in case storage server instance is not found

        Returns:
            None
        """
        # server name provided: fetch instance from db
        if isinstance(server, str):
            try:
                server_obj = StorageServer.query.filter_by(name=server).one()
            except:
                raise ItemNotFoundError('server', server, self.Schema)
        else:
            server_obj = server
        server_map = VOL_SERVER_MAP[server_obj.type]
        # types do not match: report invalid request
        if vol_type not in server_map:
            msg = MSG_INVALID_TYPE.format(vol_type, server_obj.type)
            raise BaseHttpError(code=400, msg=msg)
    # _assert_type()

    def do_create(self, properties):
        """
        Overriden method to perform sanity checks. See parent class for
        complete docstring.
        """
        # make sure type matches selected storage server
        self._assert_type(properties['server'], properties['type'])

        self._assert_ptable(
            properties.get('part_table'), properties['size'])

        return super().do_create(properties)
    # do_create()

    def do_update(self, properties, id):
        # pylint: disable=invalid-name,redefined-builtin
        """
        Overriden method to perform sanity checks. See parent class for
        complete docstring.
        """
        # cache the item's instance to avoid unnecessary queries on the db
        cached_item = None

        # server changed: verify if vol type matches it
        if 'server' in properties:
            # vol type also changed: use provided value
            if 'type' in properties:
                type_value = properties['type']
            # vol type not changed: use existing value from db
            else:
                cached_item = self.manager.read(id)
                type_value = cached_item.type
            self._assert_type(properties['server'], type_value)

        # volume type changed: verify if new type matches storage server
        elif 'type' in properties:
            self._assert_type(
                self.manager.read(id).server_rel, properties['type'])

        # partition table changed: validate partitions' sizes
        if 'part_table' in properties:
            if 'size' in properties:
                size = properties['size']
            elif cached_item is not None:
                size = cached_item.size
            else:
                cached_item = self.manager.read(id)
                size = cached_item.size
            self._assert_ptable(properties.get('part_table'), size)

        return super().do_update(properties, id)
    # do_update()

# StorageVolumeResource
