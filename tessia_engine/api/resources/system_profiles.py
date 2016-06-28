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
from flask_potion.routes import Route
from flask_potion.contrib.alchemy.fields import InlineModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from tessia_engine.api.app import API
from tessia_engine.api.exceptions import BaseHttpError
from tessia_engine.api.exceptions import ConflictError
from tessia_engine.api.exceptions import ItemNotFoundError
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import System
from tessia_engine.db.models import SystemIface
from tessia_engine.db.models import SystemIfaceProfileAssociation
from tessia_engine.db.models import SystemProfile
from tessia_engine.db.models import StorageVolume
from tessia_engine.db.models import StorageVolumeProfileAssociation

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Profile name',
    'system': 'System',
    'hypervisor': 'Required hypervisor profile',
    'os': 'Operating system',
    'default': 'Default',
    'cpu': 'CPU(s)',
    'memory': 'Memory',
    'parameters': 'Parameters',
    'credentials': 'Credentials',
    'storage_volumes': 'Storage volumes',
    'system_ifaces': 'Network interfaces',
}

#
# CODE
#
class SystemProfileResource(SecureResource):
    """
    Resource for system profiles
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = SystemProfile

        # name of the resource in the url
        name = 'system-profiles'

        title = 'System activation profile'
        description = (
            'A system activation profile has volumes, network interfaces and '
            'parameters associated')

        # custom attribute to define one or more schema fields that have a
        # human description for an item, used by integrity exceptions to
        # parse db errors.
        human_identifiers = ['system', 'name']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        name = fields.String(
            title=DESC['name'], description=DESC['name'])
        default = fields.Boolean(
            title=DESC['default'], description=DESC['default'])
        cpu = fields.Integer(
            title=DESC['cpu'], description=DESC['cpu'])
        memory = fields.PositiveInteger(
            title=DESC['memory'], description=DESC['memory'])
        parameters = fields.Object(
            title=DESC['parameters'], description=DESC['parameters'],
            nullable=True)
        credentials = fields.Any(
            title=DESC['credentials'], description=DESC['credentials'],
            nullable=True)
        # relations
        hypervisor_profile = fields.String(
            title=DESC['hypervisor'], description=DESC['hypervisor'],
            nullable=True)
        system = fields.String(
            title=DESC['system'], description=DESC['system'])
        # operating system is a read-only property; it's set by the engine
        # during installation operations
        operating_system = fields.String(
            title=DESC['os'], description=DESC['os'], io='r')
        storage_volumes = fields.List(
            # InlineModel is a way to use a different sa model in a field while
            # specifying which fields should be displayed.
            InlineModel(
                {
                    # try to keep ourselves restful as possible by providing
                    # the link to the referenced item
                    '$uri': fields.ItemUri(
                        'tessia_engine.api.resources.storage_volumes.'
                        'StorageVolumeResource',
                        attribute='id'
                    ),
                    'id': fields.Integer(),
                    'volume_id': fields.String(),
                    'server': fields.String(),
                },
                model=StorageVolume,
                io='r'
            ),
            # point to the sa's model relationship containing the entries
            attribute='storage_volumes_rel',
            # for json schema
            title=DESC['storage_volumes'],
            description=DESC['storage_volumes'],
            # read-only field
            io='r'
        )
        system_ifaces = fields.List(
            # InlineModel is a way to use a different sa model in a field while
            # specifying which fields should be displayed.
            InlineModel(
                {
                    # try to keep ourselves restful as possible by providing
                    # the link to the referenced item
                    '$uri': fields.ItemUri(
                        'tessia_engine.api.resources.system_ifaces.'
                        'SystemIfaceResource',
                        attribute='id'
                    ),
                    'id': fields.Integer(),
                    'name': fields.String(),
                    'ip_address': fields.String(),
                    'system': fields.String(),
                },
                model=SystemIface,
                io='r'
            ),
            # point to the sa's model relationship containing the entries
            attribute='system_ifaces_rel',
            # for json schema
            title=DESC['system_ifaces'],
            description=DESC['system_ifaces'],
            # read-only field
            io='r'
        )

    # section for storage volumes collection operations

    def _fetch_and_assert_item(self, model, item_id, item_id_key,
                               item_desc, prof_id):
        """
        Retrieve the item and system rows and validate user permissions on
        them.
        """
        # retrieve the item for permission verification
        item = model.query.filter_by(id=item_id).one_or_none()
        # row does not exist: report error
        if item is None:
            raise ItemNotFoundError(item_id_key, item_id, None)
        # make sure user has update permission on the item
        if hasattr(item, 'project'):
            self._assert_permission('UPDATE', item, item_desc)

        # retrieve the system row for permission verification
        # first we need the profile object
        system = System.query.join(
            SystemProfile, System.id == SystemProfile.system_id
        ).filter(
            SystemProfile.id == prof_id
        ).one_or_none()
        # row does not exist: report error
        if system is None:
            raise ItemNotFoundError('profile_id', prof_id, None)
        # make sure user has update permission on the system
        self._assert_permission('UPDATE', system, 'system')

        return item, system
    # _fetch_and_assert_item()

    def do_create(self, properties):
        """
        Custom implementation of creation. Perform some sanity checks and
        add sensitive defaults to values not provided.

        Args:
            properties (dict): field=value combination for the item to be
                               created

        Raises:
            ItemNotFoundError: in case hypervisor profile is specified but not
                               found

        Returns:
            int: id of created item
        """
        hyp_prof_name = properties['hypervisor_profile']
        if hyp_prof_name == '':
            hyp_prof_name = None
        if hyp_prof_name is not None:
            parent = aliased(SystemProfile)
            match = SystemProfile.query.join(
                parent, parent.id == SystemProfile.hypervisor_profile_id
            ).join(
                System, System.id == SystemProfile.system_id
            ).filter(
                parent.name == hyp_prof_name
            ).filter(
                SystemProfile.name == properties['name']
            ).filter(
                SystemProfile.system == properties['system']
            ).filter(
                System.hypervisor_id == parent.system_id
            ).one_or_none()
            # no profile for hypervisor with that name or system has another
            # hypervisor: report input as invalid
            if match is None:
                raise ItemNotFoundError(
                    'hypervisor_profile', hyp_prof_name, self)
            properties['hypervisor_profile'] = '{}/{}'.format(
                match.system_rel.hypervisor, hyp_prof_name)

        return super().do_create(properties)
    # do_create()

    def do_update(self, properties, id):
        """
        Custom implementation of update. Perform some sanity checks and
        add sensitive defaults to values not provided.

        Args:
            properties (dict): field=value combination for the item to be
                               created
            id (any): id of the profile item to be updated

        Raises:
            ItemNotFoundError: in case hypervisor profile is specified but not
                               found

        Returns:
            int: id of created item
        """
        # pylint: disable=invalid-name,redefined-builtin
        hyp_prof_name = properties.get('hypervisor_profile')
        if hyp_prof_name == '':
            hyp_prof_name = None
        if hyp_prof_name is not None:
            # an appropriate exception will be raised by the manager in case
            # the item is not found
            item = self.manager.read(id)

            parent = aliased(SystemProfile)
            match = SystemProfile.query.join(
                parent, parent.id == SystemProfile.hypervisor_profile_id
            ).join(
                System, System.id == SystemProfile.system_id
            ).filter(
                parent.name == hyp_prof_name
            ).filter(
                SystemProfile.name == item.name
            ).filter(
                SystemProfile.system == item.system
            ).filter(
                System.hypervisor_id == parent.system_id
            ).one_or_none()
            # no profile for hypervisor with that name or system has another
            # hypervisor: report input as invalid
            if match is None:
                raise ItemNotFoundError(
                    'hypervisor_profile', hyp_prof_name, self)
            properties['hypervisor_profile'] = '{}/{}'.format(
                match.system_rel.hypervisor, hyp_prof_name)

        return super().do_update(properties, id)
    # do_update()

    # pylint: disable=invalid-name,redefined-builtin
    @Route.POST(
        lambda r: '/<{}:id>/storage_volumes'.format(r.meta.id_converter),
        rel="vol_attach")
    def attach_storage_volume(self, properties, id):
        """
        Attach a storage volume to a system activation profile.
        """
        # validate existence and permissions
        svol, system = self._fetch_and_assert_item(
            StorageVolume, properties['unique_id'], 'volume_id',
            'storage volume', id)

        # volume not associated to the system yet: do it
        if svol.system_id is None:
            svol.system_id = system.id
        # volume attached to different system: cannot attach to two systems at
        # the same time
        elif svol.system_id != system.id:
            msg = 'The volume is already attached to system {}'.format(
                svol.system)
            raise BaseHttpError(409, msg=msg)

        # create association
        new_attach = StorageVolumeProfileAssociation(
            profile_id=id, volume_id=properties['unique_id'])
        API.db.session.add(new_attach)
        try:
            API.db.session.commit()
        # duplicate entry
        except IntegrityError as exc:
            raise ConflictError(exc, None)

        return new_attach
    # attach_storage_volume()
    attach_storage_volume.request_schema = fields.Object(
        {'unique_id': fields.Integer()})
    attach_storage_volume.response_schema = InlineModel(
        {'profile_id': fields.Integer(), 'volume_id': fields.Integer()},
        model=StorageVolumeProfileAssociation)

    @Route.DELETE(
        lambda r: '/<{}:id>/storage_volumes/<vol_unique_id>'.format(
            r.meta.id_converter),
        rel="vol_detach")
    def detach_storage_volume(self, id, vol_unique_id):
        """
        Detach a storage volume from a system activation profile.
        """
        # validate existence and permissions
        self._fetch_and_assert_item(
            StorageVolume, vol_unique_id, 'volume_id', 'storage volume', id)

        # remove association
        match = StorageVolumeProfileAssociation.query.filter_by(
            profile_id=id, volume_id=vol_unique_id,
        ).one_or_none()
        if match is None:
            value = '{},{}'.format(id, vol_unique_id)
            # TODO: create a schema to have human-readable content in the error
            # message
            raise ItemNotFoundError('profile_id,volume_id', value, None)
        API.db.session.delete(match)

        last = StorageVolumeProfileAssociation.query.filter_by(
            volume_id=vol_unique_id,
        ).first()
        # no more associations for this volume: remove system attribute
        if last is None:
            StorageVolume.query.filter_by(id=vol_unique_id).update(
                {'system_id': None})

        API.db.session.commit()
        return True
    # detach_storage_volume
    detach_storage_volume.request_schema = None
    detach_storage_volume.response_schema = fields.Boolean()

    # section for system iface collection operations
    @Route.POST(
        lambda r: '/<{}:id>/system_ifaces'.format(r.meta.id_converter),
        rel="iface_attach")
    def attach_iface(self, properties, id):
        """
        Attach a network interface to a system activation profile.
        """
        # validate existence and permissions
        iface, system = self._fetch_and_assert_item(
            SystemIface, properties['id'], 'iface_id', 'network interface', id)

        # iface and profile have different systems: cannot associate them
        if iface.system_id != system.id:
            msg = 'Profile and network interface belong to different systems'
            raise BaseHttpError(409, msg=msg)

        # create association
        new_attach = SystemIfaceProfileAssociation(
            profile_id=id, iface_id=properties['id'])
        API.db.session.add(new_attach)
        try:
            API.db.session.commit()
        # duplicate entry
        except IntegrityError as exc:
            raise ConflictError(exc, None)

        return new_attach
    # attach_iface()
    attach_iface.request_schema = fields.Object(
        {'id': fields.Integer()})
    attach_iface.response_schema = InlineModel(
        {'profile_id': fields.Integer(), 'iface_id': fields.Integer()},
        model=SystemIfaceProfileAssociation)

    @Route.DELETE(
        lambda r: '/<{}:id>/system_ifaces/<iface_id>'.format(
            r.meta.id_converter),
        rel="iface_detach")
    def detach_iface(self, id, iface_id):
        """
        Detach a network interface from a system activation profile.
        """
        # validate existence and permissions
        self._fetch_and_assert_item(
            SystemIface, iface_id, 'iface_id', 'network interface', id)

        # remove association
        match = SystemIfaceProfileAssociation.query.filter_by(
            profile_id=id, iface_id=iface_id,
        ).one_or_none()
        if match is None:
            value = '{},{}'.format(id, iface_id)
            # TODO: create a schema to have human-readable content in the error
            # message
            raise ItemNotFoundError('profile_id,iface_id', value, None)
        API.db.session.delete(match)

        API.db.session.commit()
        return True
    # detach_iface
    detach_iface.request_schema = None
    detach_iface.response_schema = fields.Boolean()

# SystemProfileResource
