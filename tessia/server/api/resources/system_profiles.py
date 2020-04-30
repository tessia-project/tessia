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
from copy import deepcopy
from flask import g as flask_global
from flask_potion import fields
from flask_potion.routes import Route
from flask_potion.contrib.alchemy.fields import InlineModel
from flask_potion.instances import Pagination
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from sqlalchemy.exc import IntegrityError
from tessia.server.api.db import API_DB
from tessia.server.api.exceptions import BaseHttpError
from tessia.server.api.exceptions import ItemNotFoundError
from tessia.server.api.resources.secure_resource import NAME_PATTERN
from tessia.server.api.resources.secure_resource import SecureResource
from tessia.server.db.models import System
from tessia.server.db.models import SystemIface
from tessia.server.db.models import SystemIfaceProfileAssociation
from tessia.server.db.models import SystemProfile
from tessia.server.db.models import StorageVolume
from tessia.server.db.models import StorageVolumeProfileAssociation
from werkzeug.exceptions import Forbidden

import logging

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

MARKER_STRIPPED_SECRET = '****'

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
            title=DESC['name'], description=DESC['name'], pattern=NAME_PATTERN)
        default = fields.Boolean(
            title=DESC['default'], description=DESC['default'])
        cpu = fields.Integer(
            title=DESC['cpu'], description=DESC['cpu'], minimum=0)
        memory = fields.Integer(
            title=DESC['memory'], description=DESC['memory'], minimum=0)
        parameters = fields.Custom(
            schema=SystemProfile.get_schema('parameters'),
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
        operating_system = fields.String(
            title=DESC['os'], description=DESC['os'], nullable=True)
        storage_volumes = fields.List(
            # InlineModel is a way to use a different sa model in a field while
            # specifying which fields should be displayed.
            InlineModel(
                {
                    # try to keep ourselves restful as possible by providing
                    # the link to the referenced item
                    '$uri': fields.ItemUri(
                        'tessia.server.api.resources.storage_volumes.'
                        'StorageVolumeResource',
                        attribute='id'
                    ),
                    'id': fields.Integer(),
                    'volume_id': fields.String(),
                    'server': fields.String(),
                    'part_table': fields.Custom(
                        schema=StorageVolume.get_schema('part_table')),
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
                        'tessia.server.api.resources.system_ifaces.'
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

    def __init__(self, *args, **kwargs):
        """
        Constructor, loads the necessary json schemas to validate the
        'parameter' field.
        """
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(__name__)

        self._param_schemas = (
            SystemProfile.get_schema('parameters')['definitions'])
    # __init__()

    def _fetch_and_assert_item(self, model, item_id, item_id_key,
                               item_desc, prof_id):
        """
        Retrieve the item and system rows and validate user permissions on
        them.
        """
        # retrieve the system row for permission verification
        system_obj = System.query.join(
            SystemProfile, System.id == SystemProfile.system_id
        ).filter(
            SystemProfile.id == prof_id
        ).one_or_none()
        # row does not exist: report error
        if system_obj is None:
            raise ItemNotFoundError('profile_id', prof_id, None)
        # make sure user has update permission on the system
        try:
            self._perman.can('UPDATE', flask_global.auth_user, system_obj,
                             'system')
        except PermissionError as exc:
            raise Forbidden(description=str(exc))

        # retrieve the target item for permission verification
        item = model.query.filter_by(id=item_id).one_or_none()
        # row does not exist: report error
        if item is None:
            raise ItemNotFoundError(item_id_key, item_id, None)
        # item has no ownership info: nothing more to check
        if not hasattr(item, 'project'):
            return item, system_obj

        # volume assigned to the system: already confirmed user has update
        # permission to the system therefore they are allowed to
        # attach to/detach from profiles
        if (isinstance(item, StorageVolume) and
                item.system_id == system_obj.id):
            return item, system_obj

        # for non volume items or a volume not assigned to the system we need
        # to verify if the user has update permission to the item
        try:
            self._perman.can('UPDATE', flask_global.auth_user, item,
                             item_desc)
        except PermissionError as exc:
            raise Forbidden(description=str(exc))

        return item, system_obj
    # _fetch_and_assert_item()

    @staticmethod
    def _strip_secrets(credentials):
        """
        Strip all secrets from a credentials field

        Args:
            credentials (dict): key from credentials dict
        """
        if not credentials:
            return

        for key in credentials:
            if key in ('admin-user', 'zvm-logonby'):
                continue
            credentials[key] = MARKER_STRIPPED_SECRET
    # _strip_secrets()

    @staticmethod
    def _verify_cred(target_system, cred_dict):
        """
        Verifies the correctness of the credentials dictionary.

        Args:
            target_system (System): db object
            cred_dict (dict): credentials dict in format defined by schema

        Raises:
            BaseHttpError: if dict content is invalid
        """
        if not cred_dict.get('admin-user'):
            raise BaseHttpError(
                422, msg='Credentials must contain OS admin username')
        if not cred_dict.get('admin-password'):
            raise BaseHttpError(
                422, msg='Credentials must contain OS admin password')

        if target_system.type == 'ZVM':
            # zvm guest missing hypervisor password: report as required
            if 'zvm-password' not in cred_dict:
                msg = 'For zVM guests the zVM password must be specified'
                raise BaseHttpError(422, msg=msg)
            # None means unset the value, so we remove the key
            if 'zvm-logonby' in cred_dict and cred_dict['zvm-logonby'] is None:
                cred_dict.pop('zvm-logonby')
        # not a zvm guest but zvm information entered: report as invalid
        elif (target_system.type != 'ZVM' and (
                'zvm-password' in cred_dict or 'zvm-logonby' in cred_dict)):
            msg = 'zVM credentials should be provided for zVM guests only'
            raise BaseHttpError(422, msg=msg)
    # _verify_cred()

    def _verify_params(self, target_system, params_dict):
        """
        Verifies the validity of the parameters dictionary.

        Args:
            target_system (System): db object
            params_dict (dict): dict in format defined by schema

        Raises:
            BaseHttpError: if dict is not in valid format
        """
        if not params_dict:
            return
        if target_system.type == 'CPC':
            schema = self._param_schemas['cpc']
        else:
            schema = self._param_schemas['other']
        try:
            validate(params_dict, schema)
        except ValidationError:
            self._logger.debug(
                "Schema validation for 'parameters' failed, info: ",
                exc_info=True)
            raise BaseHttpError(
                400, msg='Field "parameters" is not in valid format')
    # _verify_params()

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
            System.name == properties['system']).one_or_none()
        if target_system is None:
            raise ItemNotFoundError(
                'system', properties['system'], self)

        # in case of no permissions an exception will be raised
        self._perman.can('UPDATE', flask_global.auth_user, target_system)

        def_profile = SystemProfile.query.filter_by(
            system_id=target_system.id, default=True).first()
        # system has no default profile: make the new profile the default
        if not def_profile:
            properties['default'] = True
        # new profile being set as default: unset the current one
        elif properties.get('default'):
            def_profile.default = False
            # do not commit yet, let the manager do it when updating the
            # target profile to make it an atomic operation
            API_DB.db.session.add(def_profile)

        self._verify_cred(target_system, properties['credentials'])
        self._verify_params(target_system, properties['parameters'])

        hyp_prof_name = properties.get('hypervisor_profile')
        if hyp_prof_name is not None:
            if target_system.hypervisor_id is None:
                raise BaseHttpError(
                    400, msg='System has no hypervisor, you need to define '
                             'one first')
            match = SystemProfile.query.filter(
                SystemProfile.system_id == target_system.hypervisor_id
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

        # there are no pre-defined configurations for KVM guests.
        if target_system.type == 'KVM' and \
                (properties['cpu'] == 0 or properties['memory'] == 0):
            raise BaseHttpError(422, msg='For zVM guests number cpu and '
                                         'memory must be greater than 0')

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
            BaseHttpError: if a deletion of a default profile while others
                           exist is attempted.

        Returns:
            bool: True
        """
        entry = self.manager.read(id)

        # validate user permission on object - in this case we look for the
        # permission to update the system
        self._perman.can(
            'UPDATE', flask_global.auth_user, entry.system_rel, 'system')

        # profile is default: can only be deleted if it's the last one
        if entry.default:
            existing_profiles = SystemProfile.query.filter(
                SystemProfile.system_id == entry.system_id,
                SystemProfile.id != entry.id).all()
            # use list() to force the query to execute
            if list(existing_profiles):
                msg = ('A default profile cannot be removed while other '
                       'profiles for the same system exist. Set another as '
                       'the default first and then retry the operation.')
                raise BaseHttpError(422, msg=msg)

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
        ret_instances = []
        for instance in self.manager.instances(kwargs.get('where'),
                                               kwargs.get('sort')):
            self._strip_secrets(instance.credentials)

            # restricted user can list if they have a role in the project
            try:
                self._perman.can('READ', flask_global.auth_user,
                                 instance.system_rel, 'system')
            except PermissionError:
                continue
            ret_instances.append(instance)

        return Pagination.from_list(
            ret_instances, kwargs['page'], kwargs['per_page'])
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
        self._strip_secrets(item.credentials)

        # restricted user can list if they have a role in the project
        self._perman.can('READ', flask_global.auth_user,
                         item.system_rel, 'system')
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
        self._perman.can(
            'UPDATE', flask_global.auth_user, item.system_rel, 'system')

        # a profile cannot change its system, it's only allowed to set it on
        # creation
        if 'system' in properties and properties['system'] != item.system:
            raise BaseHttpError(
                422, msg='Profiles cannot change their associated system')

        if 'credentials' in properties:
            update_creds = deepcopy(item.credentials)
            update_creds.update(properties['credentials'])
            self._verify_cred(item.system_rel, update_creds)
            properties['credentials'] = update_creds

        if 'parameters' in properties:
            self._verify_params(item.system_rel, properties['parameters'])

        # profile set as default: unset the current one
        if properties.get('default'):
            def_profile = SystemProfile.query.filter_by(
                system_id=item.system_id, default=True).first()
            if def_profile and def_profile.id != item.id:
                def_profile.default = False
                # do not commit yet, let the manager do it when updating the
                # target profile to make it an atomic operation
                API_DB.db.session.add(def_profile)
        # a profile cannot unset its default flag otherwise we would have a
        # state where a system has no default profile, instead it has to be
        # replaced by another
        elif item.default and properties.get('default') is False:
            raise BaseHttpError(
                422, msg='A profile cannot unset its default flag, instead '
                         'another must be set as default in its place')

        hyp_prof_name = properties.get('hypervisor_profile')
        if hyp_prof_name is not None:
            if item.system_rel.hypervisor_id is None:
                raise BaseHttpError(
                    400, msg='System has no hypervisor, '
                             'you need to define one first')
            match = SystemProfile.query.filter(
                SystemProfile.system_id == item.system_rel.hypervisor_id
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

        # there are no pre-defined configurations for KVM guests.
        if item.system_rel.type == 'KVM' and \
                (properties.get('cpu') == 0 or properties.get('memory') == 0):
            raise BaseHttpError(422, msg='For zVM guests number cpu '
                                         'and memory must be greater than 0')

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
            StorageVolume, properties['unique_id'], 'volume_id', 'volume', id)
        # for a cpc system only one disk can be associated *per profile*
        # which is regarded as the disk containing the live image used
        # to netboot lpars.
        if system.type == 'CPC':
            prof_vols = StorageVolumeProfileAssociation.query.filter_by(
                profile_id=id).all()
            if prof_vols:
                msg = 'A CPC profile can have only one volume associated'
                raise BaseHttpError(422, msg=msg)

        # volume not associated to the system yet: do it
        if svol.system_id is None:
            svol.system_id = system.id
        # volume attached to different system: cannot attach to two systems at
        # the same time
        elif svol.system_id != system.id:
            msg = 'The volume is already assigned to system {}'.format(
                svol.system)
            raise BaseHttpError(409, msg=msg)

        # create association
        new_attach = StorageVolumeProfileAssociation(
            profile_id=id, volume_id=properties['unique_id'])
        API_DB.db.session.add(new_attach)
        try:
            API_DB.db.session.commit()
        # duplicate entry
        except IntegrityError:
            API_DB.db.session.rollback()
            msg = 'The volume specified is already attached to the profile'
            raise BaseHttpError(409, msg=msg)

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
            StorageVolume, vol_unique_id, 'volume_id', 'volume', id)

        # remove association
        match = StorageVolumeProfileAssociation.query.filter_by(
            profile_id=id, volume_id=vol_unique_id,
        ).one_or_none()
        if match is None:
            msg = 'The volume specified is not attached to the profile'
            raise BaseHttpError(404, msg=msg)
        API_DB.db.session.delete(match)
        API_DB.db.session.commit()

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
        API_DB.db.session.add(new_attach)
        try:
            API_DB.db.session.commit()
        # duplicate entry
        except IntegrityError:
            API_DB.db.session.rollback()
            msg = ('The network interface specified is already attached to '
                   'the profile')
            raise BaseHttpError(409, msg=msg)

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
            msg = ('The network interface specified is not attached to '
                   'the profile')
            raise BaseHttpError(404, msg=msg)
        API_DB.db.session.delete(match)

        API_DB.db.session.commit()
        return True
    # detach_iface
    detach_iface.request_schema = None
    detach_iface.response_schema = fields.Boolean()

# SystemProfileResource
