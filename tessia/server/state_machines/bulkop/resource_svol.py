# Copyright 2019 IBM Corp.
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
Handler of operations on storage volumes
"""

#
# IMPORTS
#
from tessia.server.db.connection import MANAGER
from tessia.server.db.exceptions import AssociationError
from tessia.server.db.models import StorageServer
from tessia.server.db.models import StorageVolume
from tessia.server.db.models import StorageVolumeProfileAssociation
from tessia.server.db.models import System
from tessia.server.state_machines.bulkop.resource_base import \
    ResourceHandlerBase

import logging
import re

#
# CONSTANTS AND DEFINITIONS
#

FIELDS_CSV = (
    'SERVER', 'VOLUME_ID', 'TYPE', 'SIZE', 'SYSTEM', 'FCP_PATHS', 'WWID',
    'OWNER', 'PROJECT', 'DESC'
)

# map between storage servers and volumes types
VOL_SERVER_MAP = {
    'DASD-FCP': ['DASD', 'FCP'],
}

#
# CODE
#


class ResourceHandlerStorageVolume(ResourceHandlerBase):
    """
    Handler for operations on storage volumes
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor
        """
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(__name__)
        MANAGER.connect()

        self._compare_fields = [field.lower() for field in FIELDS_CSV]
        self._compare_fields.remove('fcp_paths')
        self._compare_fields.remove('wwid')
    # __init__()

    def _assert_create(self, properties):
        """
        Validate that the create operation may occur
        """
        # make sure type matches selected storage server
        try:
            server_obj = StorageServer.query.filter_by(
                name=properties['server']).one()
        except:
            raise ValueError('Storage server {} not found'.format(
                properties['server']))
        try:
            server_map = VOL_SERVER_MAP[server_obj.type]
        except KeyError:
            raise ValueError('Storage server type {} not supported'.format(
                server_obj.type))
        # types do not match: report invalid
        if properties['type'].upper() not in server_map:
            msg = 'Specified type {} does not match storage server'.format(
                properties['type'])
            raise ValueError(msg)

        self._assert_system(None, properties['system'])

        new_item = StorageVolume()
        try:
            new_item.project = properties['project']
        except AssociationError:
            raise ValueError('Specified project {} not found'.format(
                properties['project']))

        self._perman.can('CREATE', self._requester, new_item)
    # _assert_create()

    def _assert_system(self, item, system_name):
        """
        Retrieve the system and validate user permissions to it.

        Args:
            item (StorageVolume): provided in case of an update, None for
                                  create
            system_name (str): target system to assign volume

        Raises:
            ValueError: if system does not exist
            PermissionError: if user has no permission to current system
        """
        # volume is created with no system or updated without changing system:
        # nothing to check
        if (not item and not system_name) or (
                item and item.system_rel and
                item.system_rel.name == system_name):
            return

        # volume already assigned to a system: make sure user has permission
        # to withdraw the volume from it
        if item and item.system_id:
            try:
                self._perman.can('UPDATE', self._requester, item.system_rel)
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
            msg = 'System {} not found'.format(system_name)
            raise ValueError(msg)
        # make sure user has update permission on the system
        self._perman.can('UPDATE', self._requester, system_obj, 'system')
    # _assert_system()

    def _assert_update(self, vol_obj, properties):
        """
        Validate that the update operation may occur
        """
        self._perman.can('UPDATE', self._requester, vol_obj, 'volume')

        # volume type changed: not allowed
        if ('type' in properties and
                properties['type'].upper() != vol_obj.type.upper()):
            msg = 'Tried to change volume type from {} to {}'.format(
                vol_obj.type, properties['type'])
            raise ValueError(msg)

        # TODO: try to adjust partition size

        # system assignment changed: validate permissions and remove any
        # profiles attached
        if 'system' in properties and properties['system'] != vol_obj.system:
            self._assert_system(vol_obj, properties['system'])

            # remove any existing profile associations
            StorageVolumeProfileAssociation.query.filter_by(
                volume_id=vol_obj.id).delete()

        # project changed: make sure user has permission to new project
        if ('project' in properties and
                properties['project'] != vol_obj.project):
            dummy_item = StorageVolume()
            dummy_item.project = properties['project']
            self._perman.can('UPDATE', self._requester, dummy_item, 'project')
    # _assert_update()

    @staticmethod
    def _fcp_to_spec(fcp_paths):
        """
        Convert fcp paths in csv format to database format
        """
        specs = {'adapters': []}
        if not fcp_paths:
            return specs

        # keep track of used devnos to avoid repetitions
        devnos = {}

        for fcp_path in fcp_paths.split():
            re_match = re.search(r'^(.*)\((.*)\)', fcp_path)
            if not re_match or len(re_match.groups()) != 2:
                raise ValueError('FCP paths in invalid format')
            devno, wwpns = re_match.groups()
            if not '.' in devno:
                devno = '0.0.{}'.format(devno)
            if devno in devnos:
                raise ValueError('FCP paths invalid: devno {} appears twice'
                                 .format(devno))
            devnos[devno] = True
            wwpns = wwpns.split(',')
            specs['adapters'].append({'devno': devno, 'wwpns': wwpns})

        return specs
    # _fcp_to_spec()

    def _render_dasd(self, vol_obj, entry):
        """
        Prepare a DASD volume object for creation/update
        """
        # not used for DASDs
        entry.pop('fcp_paths')
        entry.pop('wwid')

        str_size = entry['size']
        try:
            entry['size'] = int(str_size)
        except ValueError:
            raise ValueError("Invalid size: '{}'".format(str_size)) from None

        # update volume: evaluate changes
        if vol_obj:
            # compare fields
            vol_obj_dict = {
                key: getattr(vol_obj, key.lower())
                for key in self._compare_fields
            }
            changes_diff = dict(entry.items() - vol_obj_dict.items())
            # no changes to item: nothing to do
            if not changes_diff:
                self._logger.info(
                    'skipping volume %s/%s (no changes)',
                    vol_obj.server, vol_obj.volume_id)
                return

            # validate action
            self._assert_update(vol_obj, changes_diff)

            desc = ''
            for key, value in changes_diff.items():
                desc += ' {}={}(previous <{}>)'.format(
                    key.upper(), changes_diff[key],
                    getattr(vol_obj, key.lower()))
                setattr(vol_obj, key.lower(), changes_diff[key])

            # mark resource as last modified by requester
            vol_obj.modifier_id = self._requester.id

            desc = 'updating volume {}/{}:{}'.format(
                vol_obj.server, vol_obj.volume_id, desc)
            self._logger.info(desc)

        # create new volume
        else:
            # validate action
            self._assert_create(entry)

            vol_obj = StorageVolume()
            vol_obj.part_table = {}
            vol_obj.modifier_id = self._requester.id
            vol_obj.specs = {}
            vol_obj.system_attributes = {}
            desc = ''
            for key, value in entry.items():
                desc += ' {}={}'.format(key.upper(), value)
                setattr(vol_obj, key, value)

            desc = 'creating volume {}/{}:{}'.format(
                entry['server'], entry['volume_id'], desc)
            self._logger.info(desc)

        MANAGER.session.add(vol_obj)
    # _render_dasd()

    def _render_fcp(self, vol_obj, entry):
        """
        Prepare a FCP volume object for creation/update
        """
        fcp_paths = entry.pop('fcp_paths')
        specs_new = self._fcp_to_spec(fcp_paths)
        specs_new['wwid'] = entry.pop('wwid')
        specs_new['multipath'] = True

        str_size = entry['size']
        try:
            entry['size'] = int(str_size)
        except ValueError:
            raise ValueError("Invalid size: '{}'".format(str_size)) from None

        # update volume: evaluate changes
        if vol_obj:
            # compare fields
            vol_obj_dict = {
                key: getattr(vol_obj, key.lower())
                for key in self._compare_fields
            }
            changes_diff = dict(entry.items() - vol_obj_dict.items())

            # specs must be compared separately, sort all lists to make the
            # comparison work
            sorted_new = sorted(specs_new['adapters'],
                                key=lambda item: item['devno'])
            for fcp_path in sorted_new:
                fcp_path['wwpns'].sort()
            sorted_old = sorted(vol_obj.specs['adapters'],
                                key=lambda item: item['devno'])
            for fcp_path in sorted_old:
                fcp_path['wwpns'].sort()
            if (sorted_old != sorted_new or specs_new['wwid'] !=
                    vol_obj.specs.get('wwid', '')):
                changes_diff['specs'] = specs_new
            # no changes to item: nothing to do
            elif not changes_diff:
                self._logger.info(
                    'skipping volume %s/%s (no changes)',
                    vol_obj.server, vol_obj.volume_id)
                return

            # validate action
            self._assert_update(vol_obj, changes_diff)

            desc = ''
            for key, value in changes_diff.items():
                if key != 'specs':
                    desc += ' {}={}(previous <{}>)'.format(
                        key.upper(), changes_diff[key],
                        getattr(vol_obj, key.lower()))
                else:
                    # report which fields changed
                    if sorted_old != sorted_new:
                        desc += ' FCP_PATHS={}'.format(fcp_paths)
                    if specs_new['wwid'] != vol_obj.specs.get('wwid', ''):
                        desc += ' WWID={}(previous <{}>)'.format(
                            specs_new['wwid'], vol_obj.specs.get('wwid', ''))
                setattr(vol_obj, key.lower(), changes_diff[key])

            # mark resource as last modified by requester
            vol_obj.modifier_id = self._requester.id

            desc = 'updating volume {}/{}:{}'.format(
                vol_obj.server, vol_obj.volume_id, desc)
            self._logger.info(desc)

        # create new volume
        else:
            # validate action
            self._assert_create(entry)

            vol_obj = StorageVolume()
            vol_obj.part_table = {}
            vol_obj.modifier_id = self._requester.id
            vol_obj.system_attributes = {}
            desc = ''
            for key, value in entry.items():
                desc += ' {}={}'.format(key.upper(), value)
                setattr(vol_obj, key, value)

            # handle specs separately
            setattr(vol_obj, 'specs', specs_new)
            desc += ' FCP_PATHS={}'.format(fcp_paths)
            desc += ' WWID={}'.format(specs_new['wwid'])
            desc = 'creating volume {}/{}:{}'.format(
                entry['server'], entry['volume_id'], desc)
            self._logger.info(desc)

        MANAGER.session.add(vol_obj)
    # _render_fcp()

    @staticmethod
    def headers_match(headers):
        """
        Return True if the provided headers match the resource type
        """
        return tuple(headers) == tuple(FIELDS_CSV)
    # headers_match()

    def render_item(self, entry):
        """
        Receive an entry in dict format with keys in the header format and
        produce the corresponding database object with the changes applied
        """
        # normalize empty string to None
        if not entry['system']:
            entry['system'] = None

        # sanitize by removing any invalid keys
        entry = {
            key: value for key, value in entry.items()
            if key.upper() in FIELDS_CSV
        }
        # volume ids are stored in db as lowercase
        entry['volume_id'] = entry['volume_id'].lower()

        vol_obj = StorageVolume.query.join(
            'server_rel'
        ).filter(
            StorageServer.name == entry['server']
        ).filter(
            StorageVolume.volume_id == entry['volume_id']
        ).with_for_update().one_or_none()

        if vol_obj:
            if not entry['desc']:
                # do not update the field if empty string != None
                if not vol_obj.desc:
                    entry.pop('desc')
                # normalize empty string to None
                else:
                    entry['desc'] = None
            # determine which method to use
            if vol_obj.type == 'FCP':
                method = self._render_fcp
            else:
                method = self._render_dasd
        else:
            # normalize empty string to None
            if not entry['desc']:
                entry['desc'] = None
            # determine which method to use
            if entry['type'].upper() == 'FCP':
                method = self._render_fcp
            else:
                method = self._render_dasd

        try:
            method(vol_obj, entry)
        except Exception:
            self._logger.error('failed to process volume %s/%s',
                               entry['server'], entry['volume_id'])
            raise
    # render_item()
# ResourceHandlerStorageVolume
