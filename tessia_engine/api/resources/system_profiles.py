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
from flask_potion.routes import Route
from flask_potion.contrib.alchemy.fields import InlineModel
from flask_potion.instances import Pagination
from sqlalchemy.exc import IntegrityError
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
from werkzeug.exceptions import Forbidden

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Profile name',
    'system': 'System',
    'hypervisor_profile': 'Required hypervisor profile',
    'os': 'Operating system',
    'default': 'Default',
    'cpu': 'CPU(s)',
    'memory': 'Memory',
    'parameters': 'Parameters',
    'credentials': 'Credentials',
    'storage_volumes': 'Storage volumes',
    'system_ifaces': 'Network interfaces',
    'gateway': 'Gateway interface',
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
        credentials = fields.Custom(
            schema=SystemProfile.get_schema('credentials'),
            title=DESC['credentials'], description=DESC['credentials'])
        # relations
        hypervisor_profile = fields.String(
            title=DESC['hypervisor_profile'],
            description=DESC['hypervisor_profile'], nullable=True)
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
        gateway = fields.String(
            title=DESC['gateway'], description=DESC['gateway'], nullable=True)

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
            BaseHttpError: in case provided hypervisor profile is invalid

        Returns:
            int: id of created item
        """
        target_system = System.query.filter(
            System.name == properties['system']
        ).one_or_none()
        if target_system is None:
            raise ItemNotFoundError(
                'system', properties['system'], self)

        # we don't need the actual project, only the verification. In case of
        # invalid permissions an exception will be raised.
        self._get_project_for_create(
            System.__tablename__, target_system.project_rel.name)

        # check if this is the first profile and make it the default
        if properties.get('default', False) is False:
            profile = SystemProfile.query.filter(
                SystemProfile.system_id == target_system.id
            ).first()
            # confirmed it's the first profile: make it default
            if profile is None:
                properties['default'] = True

        hyp_prof_name = properties.get('hypervisor_profile')
        if hyp_prof_name is not None:
            if target_system.hypervisor_rel is None:
                raise BaseHttpError(
                    400, msg='System has no hypervisor, '
                             'you need to define one first')
            match = SystemProfile.query.join(
                System, System.id == target_system.hypervisor_rel.id
            ).filter(
                SystemProfile.name == hyp_prof_name
            ).one_or_none()
            # no profile for hypervisor with that name or system has another
            # hypervisor: report input as invalid
            if match is None:
                raise ItemNotFoundError(
                    'hypervisor_profile', hyp_prof_name, self)
            properties['hypervisor_profile'] = '{}/{}'.format(
                target_system.hypervisor_rel.name, hyp_prof_name)

        item = self.manager.create(properties)
        # don't waste resources building the object in the answer,
        # just give the id and let the client decide if it needs more info (in
        # which case it can use the provided id to request the item)
        return item.id
    # do_create()

    def do_delete(self, id): # pylint: disable=invalid-name,redefined-builtin
        """
        Verify if the user attempting to delete the instance has permission
        on the corresponding system to do so.

        Args:
            id (any): id of the item in the table's database

        Raises:
            Forbidden: in case user has no permission to perform action

        Returns:
            bool: True
        """
        entry = self.manager.read(id)

        # validate user permission on object
        self._assert_permission('DELETE', entry.system_rel, 'system')

        self.manager.delete_by_id(id)
        return True
    # do_delete()

    def do_list(self, **kwargs):
        """
        Verify if the user attempting to list has permissions to do so.

        Args:
            kwargs (dict): contains keys like 'where' (filtering) and
                           'per_page' (pagination), see potion doc for details

        Returns:
            list: list of items retrieved, can be an empty in case no items are
                  found or a restricted user has no permission to see them
        """
        # non restricted user: regular resource listing is allowed
        if not flask_global.auth_user.restricted:
            return self.manager.paginated_instances(**kwargs)

        # for restricted users, filter the list by the projects they have
        # access or if they own the resource
        allowed_instances = []
        for instance in self.manager.instances(kwargs.get('where'),
                                               kwargs.get('sort')):
            # user is not the resource's owner or an administrator: verify if
            # they have a role in resource's project
            if not self._is_owner_or_admin(instance.system_rel):
                # no role in system's project: cannot list
                if self._get_role_for_project(
                        instance.system_rel.project_id) is None:
                    continue

            allowed_instances.append(instance)

        return Pagination.from_list(
            allowed_instances, kwargs['page'], kwargs['per_page'])
    # do_list()

    def do_read(self, id):
        """
        Custom implementation of profile reading. Use permissions from the
        associated system to validate access.

        Args:
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Raises:
            Forbidden: in case user has no rights to read profile

        Returns:
            json: json representation of item
        """
        # pylint: disable=redefined-builtin

        item = self.manager.read(id)

        # non restricted user: regular resource reading is allowed
        if not flask_global.auth_user.restricted:
            return item

        # validate permission on the object - use the associated system
        # user is not the system's owner or an administrator: verify if
        # they have a role in system's project
        if not self._is_owner_or_admin(item.system_rel):
            # no role in system's project: access forbidden
            if self._get_role_for_project(item.system_rel.project_id) is None:
                msg = 'User has no READ permission for the specified resource'
                raise Forbidden(description=msg)

        return item
    # do_read()

    def do_update(self, properties, id):
        """
        Custom implementation of update. Perform some sanity checks and
        and verify permissions on the corresponding system.

        Args:
            properties (dict): field=value combination for the item to be
                               created
            id (any): id of the profile item to be updated

        Raises:
            ItemNotFoundError: in case hypervisor profile is specified but not
                               found
            BaseHttpError: if request tries to change associated system

        Returns:
            int: id of created item
        """
        # pylint: disable=invalid-name,redefined-builtin

        item = self.manager.read(id)

        # validate permission on the object - use the associated system
        self._assert_permission('UPDATE', item.system_rel, 'system')

        # a profile cannot change its system so we only allow to set it on
        # creation
        if 'system' in properties and properties['system'] != item.system:
            raise BaseHttpError(
                422, msg='Profiles cannot change their associated system')

        hyp_prof_name = properties.get('hypervisor_profile')
        if hyp_prof_name is not None:
            if item.system_rel.hypervisor_rel is None:
                raise BaseHttpError(
                    400, msg='System has no hypervisor, '
                             'you need to define one first')
            match = SystemProfile.query.join(
                System, System.id == item.system_rel.hypervisor_rel.id
            ).filter(
                SystemProfile.name == hyp_prof_name
            ).one_or_none()
            # no profile for hypervisor with that name or system has another
            # hypervisor: report input as invalid
            if match is None:
                raise ItemNotFoundError(
                    'hypervisor_profile', hyp_prof_name, self)
            properties['hypervisor_profile'] = '{}/{}'.format(
                item.system_rel.hypervisor_rel.name, hyp_prof_name)

        # profile set as default: make sure to unset the previous default one
        # to avoid duplication
        if properties.get('default') is True:
            current_default = SystemProfile.query.filter_by(
                system_id=item.system_id,
                default=True
            ).one_or_none()
            if current_default is not None and current_default.id != item.id:
                current_default.default = False
                # do not commit yet, let the manager to it when updating the
                # target profile to make it an atomic operation
                API.db.session.add(current_default)

        updated_item = self.manager.update(item, properties)

        # don't waste resources building the object in the answer,
        # just give the id and let the client decide if it needs more info (in
        # which case it can use the provided id to request the item)
        return updated_item.id
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
