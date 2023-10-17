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
from flask_potion.contrib.alchemy.fields import InlineModel
from flask_potion.instances import Instances
from flask_potion.routes import Route
from tessia.server.api.exceptions import BaseHttpError, ItemNotFoundError
from tessia.server.api.resources.secure_resource import SecureResource
from tessia.server.db.models import StorageVolume
from tessia.server.db.models import StorageVolumeProfileAssociation
from tessia.server.db.models import StorageServer
from tessia.server.db.models import System
from tessia.server.db.models import SystemProfile

import csv
import io
import re

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
    'system': 'Assigned to system',
    'system_attributes': 'System related attributes',
    'system_profiles': 'Associated system profiles',
    'pool': 'Attached to storage pool',
    'server': 'Storage server',
    'modified': 'Last modified',
    'desc': 'Description',
    'modifier': 'Modified by',
    'project': 'Project',
    'owner': 'Owner',
}

FIELDS_CSV = (
    'SERVER', 'VOLUME_ID', 'TYPE', 'SIZE', 'SYSTEM', 'FCP_PATHS', 'WWID',
    'WWN', 'OWNER', 'PROJECT', 'DESC'
)

HPAV_PATTERN = re.compile(r"^[a-f0-9]{4}$")

MSG_PTABLE_DASD_PARTS = (
    "The value 'part_table' is invalid: a dasd partition table cannot have "
    "more than 3 partitions"
)

MSG_PTABLE_BAD_PLACE = (
    "The value 'part_table' is invalid: logical partitions are not in a "
    "contiguous area"
)

MSG_PTABLE_MANY_PARTS = (
    "The value 'part_table' is invalid: a msdos partition table cannot "
    "have more than 4 primary/extended partitions"
)

MSG_PTABLE_SIZE_MISMATCH = (
    "The value 'part_table' is invalid: sum of partitions sizes ({}) is "
    "bigger than volume's size ({})"
)

MSG_INVALID_TYPE = (
    "The value 'type={}' is invalid: it does not match storage server "
    "type '{}'"
)
MSG_INVALID_PTABLE = (
    "DASD is not applicable as Table type for an non DASD-Volume"
)

# when the volume is assigned to a system and the user has permission to update
# that system they are entitled to update these attributes on the volume
# (note that modifier is actually set by secure_resource and not by user)
SYS_DERIVED_PERMS = set(
    ('part_table', 'system_attributes', 'modifier'))

# support map between storage servers and volumes types
VOL_SERVER_MAP = {
    'DASD-FCP': ['DASD', 'FCP', 'HPAV'],
    'ISCSI': ['ISCSI'],
    'NVME': ['NVME'],
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
            pattern=r'^[a-z0-9_\.\-]+$',
            title=DESC['volume_id'], description=DESC['volume_id'])
        size = fields.Integer(
            minimum=0, title=DESC['size'], description=DESC['size'])
        part_table = fields.Custom(
            schema=StorageVolume.get_schema('part_table'),
            title=DESC['part_table'], description=DESC['part_table'],
            nullable=True)
        specs = fields.Custom(
            schema=StorageVolume.get_schema('specs'),
            title=DESC['specs'], description=DESC['specs'])
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
        system = fields.String(
            title=DESC['system'], description=DESC['system'], nullable=True)
        system_attributes = fields.Custom(
            schema=StorageVolume.get_schema('system_attributes'),
            title=DESC['system_attributes'],
            description=DESC['system_attributes'])
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

    @staticmethod
    def _assert_hpav(vol_obj, properties):
        """
        Validate correctness of hpav entry
        """
        # not a hpav type: nothing to check
        if (vol_obj and vol_obj.type != 'HPAV') or (
                not vol_obj and properties['type'].upper() != 'HPAV'):
            return

        if 'volume_id' in properties and (
                not HPAV_PATTERN.search(properties['volume_id'])):
            msg = 'HPAV alias {} is not in valid format'.format(
                properties['volume_id'])
            raise BaseHttpError(code=400, msg=msg)

        if 'size' in properties and properties['size'] != 0:
            msg = 'HPAV type must have size 0'
            raise BaseHttpError(code=400, msg=msg)
        if properties.get('part_table'):
            msg = 'HPAV type cannot have partition table'
            raise BaseHttpError(code=400, msg=msg)
        if properties.get('specs'):
            msg = 'HPAV type cannot have specs'
            raise BaseHttpError(code=400, msg=msg)
        if properties.get('system_attributes'):
            msg = 'HPAV type cannot have system_attributes'
            raise BaseHttpError(code=400, msg=msg)
    # _assert_hpav()

    @staticmethod
    def _assert_ptable(part_table, vol_size, vol_type):
        """
        Perform validations to make sure the partition table is valid.

        Args:
            part_table (dict): partition table
            vol_size (int): volume size
            vol_type (str): volume type
        Raises:
            BaseHttpError: in case of validation errors
        """
        if part_table is None:
            return

        # asserting that dasd is not used as a parttable for an fcp volume
        if part_table['type'] == 'dasd' and vol_type != 'DASD':
            raise BaseHttpError(code=400, msg=MSG_INVALID_PTABLE)

        # dict format was already validated by schema
        table_size = sum([part['size'] for part in part_table['table']])

        # assert that the total size of the partitions do not exceed the
        # volume's assigned size
        if table_size > vol_size:
            msg = MSG_PTABLE_SIZE_MISMATCH.format(table_size, vol_size)
            raise BaseHttpError(code=400, msg=msg)

        # dasd type: make sure it has 3 partitions maximum
        if part_table['type'] == 'dasd' and len(part_table['table']) > 3:
            raise BaseHttpError(code=400, msg=MSG_PTABLE_DASD_PARTS)
        # msdos type: perform checks on the primary/logical
        # combinations
        if part_table['type'] == 'msdos':
            len_ptable = len(part_table['table'])
            # empty partition: nothing to check
            if len_ptable == 0:
                return

            num_primary = 0
            logical_found = False
            if part_table['table'][0]['type'] == 'primary':
                num_primary += 1
            else:
                logical_found = True
                # a logical partition demands an extended which counts as
                # primary
                num_primary += 1

            for i in range(1, len_ptable):
                last_part = part_table['table'][i-1]
                cur_part = part_table['table'][i]
                if cur_part['type'] == 'primary':
                    num_primary += 1
                else:
                    # logicals found in non contiguous areas: this is not
                    # possible, report error
                    if logical_found and last_part['type'] != 'logical':
                        raise BaseHttpError(code=400, msg=MSG_PTABLE_BAD_PLACE)

                    # first logical found: set flag and increase primary count
                    # as a logical demands an extended to contain it
                    if not logical_found:
                        logical_found = True
                        num_primary += 1

                # more than 4 primary parts in a msdos table: report error
                if num_primary > 4:
                    raise BaseHttpError(code=400, msg=MSG_PTABLE_MANY_PARTS)

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
        """
        # server name provided: fetch instance from db
        if isinstance(server, str):
            try:
                server_obj = StorageServer.query.filter_by(name=server).one()
            except:
                raise ItemNotFoundError('server', server, self)
        else:
            server_obj = server
        server_map = VOL_SERVER_MAP[server_obj.type]
        # types do not match: report invalid request
        if vol_type not in server_map:
            msg = MSG_INVALID_TYPE.format(vol_type, server_obj.type)
            raise BaseHttpError(code=400, msg=msg)
    # _assert_type()

    def _assert_system(self, item, system_name):
        """
        Retrieve the system and validate user permissions to it.

        Args:
            item (StorageVolume): provided in case of an update, None for
                                  create
            system_name (str): target system to assign volume

        Raises:
            ItemNotFoundError: if system does not exist
            PermissionError: if user has no permission to current system
        """
        # volume is created with no system or updated without changing system:
        # nothing to check
        if (not item and not system_name) or (
                item and item.system_rel and
                item.system_rel.name == system_name):
            return

        # volume already assigned to a system: make sure user has permission
        # to unassign a volume from it
        if item and item.system_id:
            try:
                self._perman.can('UPDATE', flask_global.auth_user,
                                 item.system_rel)
            except PermissionError:
                msg = ('User has no UPDATE permission for the system '
                       'currently holding the volume')
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

    @Route.GET('/bulk', rel='bulk')
    def bulk(self, **kwargs):
        """
        Bulk export operation
        """
        result = io.StringIO()
        csv_writer = csv.writer(result, quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(FIELDS_CSV)

        for entry in self.manager.instances(kwargs.get('where'),
                                            kwargs.get('sort')):
            try:
                self._perman.can(
                    'READ', flask_global.auth_user, entry)
            except PermissionError:
                continue

            if entry.type != 'FCP' and entry.type != 'NVME':
                entry.fcp_paths = None
                entry.wwid = None
                entry.wwn = None
            elif entry.type == 'NVME':
                entry.fcp_paths = None
                entry.wwid = None
                entry.wwn = entry.specs.get('wwn')
            else:
                fcp_paths = []
                for adapter in entry.specs.get('adapters', []):
                    fcp_path = '{}('.format(
                        adapter['devno'].replace('0.0.', ''))
                    fcp_path += ','.join(adapter['wwpns'])
                    fcp_path += ')'
                    fcp_paths.append(fcp_path)
                entry.fcp_paths = ' '.join(fcp_paths)
                entry.wwid = entry.specs.get('wwid')
                entry.wwn = None

            csv_writer.writerow(
                [getattr(entry, attr.lower()) for attr in FIELDS_CSV])

        result.seek(0)
        return result.read()
    # bulk()
    bulk.request_schema = Instances()
    bulk.response_schema = fields.String(
        title="result output", description="content in csv format")

    @Route.GET('/schema', rel="describedBy", attribute="schema")
    def described_by(self, *args, **kwargs):
        schema, http_code, content_type = super().described_by(*args, **kwargs)
        # we don't want to advertise pagination for the bulk endpoint
        link_found = False
        for link in schema['links']:
            if link['rel'] == 'bulk':
                link_found = True
                link['schema']['properties'].pop('page')
                link['schema']['properties'].pop('per_page')
                break
        if not link_found:
            raise SystemError(
                'JSON schema for endpoint /{}/bulk not found'
                .format(self.Meta.name))
        return schema, http_code, content_type
    # described_by()

    def do_create(self, properties):
        """
        Overriden method to perform sanity checks. See parent class for
        complete docstring.
        """
        # make sure type matches selected storage server
        self._assert_type(properties['server'], properties['type'])

        self._assert_hpav(None, properties)

        self._assert_ptable(properties.get('part_table'),
                            properties['size'],
                            properties['type'])

        self._assert_system(None, properties.get('system'))

        return super().do_create(properties)
    # do_create()

    # pylint: disable=arguments-renamed
    def do_read(self, svol_id):
        """
        Custom implementation of item reading. Use permissions from the
        associated system to validate access if necessary.

        Args:
            svol_id (any): storage volume id

        Raises:
            PermissionError: if user has no permission to the item

        Returns:
            json: json representation of item
        """
        item = self.manager.read(svol_id)
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

    # pylint: disable=arguments-renamed
    def do_update(self, properties, svol_id):
        """
        Overriden method to perform sanity checks. See parent class for
        complete docstring.
        """
        vol_obj = self.manager.read(svol_id)
        # determine which kind of permission the user has
        try:
            self._perman.can(
                'UPDATE', flask_global.auth_user, vol_obj, 'volume')
        except PermissionError as no_disk_perm:
            # volume is not assigned to a system: no more permissions to
            # check
            if not vol_obj.system_rel:
                raise no_disk_perm
            # when a volume is assigned to a system and the user has update
            # permission to that system then it's allowed to update certain
            # attributes
            try:
                self._perman.can('UPDATE', flask_global.auth_user,
                                 vol_obj.system_rel, 'system')
            except PermissionError:
                raise no_disk_perm
            # abort if attempting to update a protected attribute
            for prop in properties:
                if prop not in SYS_DERIVED_PERMS:
                    raise

            # partition table changed: validate partitions' sizes
            if 'part_table' in properties:
                if 'type' in properties:
                    vol_type = properties['type']
                else:
                    vol_type = vol_obj.type
                self._assert_ptable(properties.get('part_table'),
                                    properties.get('size', vol_obj.size),
                                    vol_type)

            updated_item = self.manager.update(vol_obj, properties)
            return updated_item.id

        # server changed: verify if vol type matches it
        if 'server' in properties:
            # vol type also changed: use provided value
            if 'type' in properties:
                type_value = properties['type']
            # vol type not changed: use existing value from db
            else:
                type_value = vol_obj.type
            self._assert_type(properties['server'], type_value)

        # volume type changed: verify if new type matches storage server
        elif 'type' in properties:
            self._assert_type(vol_obj.server_rel, properties['type'])

        self._assert_hpav(vol_obj, properties)

        # partition table changed: validate partitions' sizes
        if 'part_table' in properties:
            if 'size' in properties:
                size = properties['size']
            else:
                size = vol_obj.size
            if 'type' in properties:
                vol_type = properties['type']
            else:
                vol_type = vol_obj.type
            self._assert_ptable(properties.get('part_table'),
                                size,
                                vol_type)

        # system assignment changed: validate permissions and remove any
        # profiles attached
        if 'system' in properties and properties['system'] != vol_obj.system:
            self._assert_system(vol_obj, properties['system'])

            # remove any existing profile associations
            StorageVolumeProfileAssociation.query.filter_by(
                volume_id=svol_id).delete()

        # project changed: make sure user has permission to new project
        if 'project' in properties:
            dummy_item = self.meta.model()
            dummy_item.project = properties['project']
            self._perman.can('UPDATE', flask_global.auth_user, dummy_item,
                             'project')

        updated_item = self.manager.update(vol_obj, properties)

        # don't waste resources building the object in the answer,
        # just give the id and let the client decide if it needs more info (in
        # which case it can use the provided id to request the item)
        return updated_item.id
    # do_update()
# StorageVolumeResource
