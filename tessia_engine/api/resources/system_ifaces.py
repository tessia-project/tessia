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
from flask_potion.instances import Pagination
from tessia_engine.api.exceptions import BaseHttpError
from tessia_engine.api.exceptions import ItemNotFoundError
from tessia_engine.api.resources.secure_resource import NAME_PATTERN
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import System
from tessia_engine.db.models import SystemIface
from tessia_engine.db.models import SystemProfile

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Interface name',
    'osname': 'Operating system name',
    'ip_address': 'IP address',
    'mac_address': 'MAC address',
    'system': 'System',
    'type': 'Interface type',
    'attributes': 'Attributes',
    'desc': 'Description',
    'system_profiles': 'Associated system profiles',
}

#
# CODE
#
class SystemIfaceResource(SecureResource):
    """
    Resource for system network interfaces
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = SystemIface

        # name of the resource in the url
        name = 'system-ifaces'

        title = 'Network interfaces'
        description = 'System network interfaces'
        # custom attribute to define one or more schema fields that have a
        # human description for an item, used by api exceptions to report
        # db errors.
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
        osname = fields.String(
            title=DESC['osname'], description=DESC['osname'], nullable=True,
            pattern=r'^[a-zA-Z0-9_\s\.\-]+$')
        attributes = fields.Custom(
            schema=SystemIface.get_schema('attributes'),
            title=DESC['attributes'], description=DESC['attributes'])
        mac_address = fields.String(
            title=DESC['mac_address'], description=DESC['mac_address'])
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        # relations
        ip_address = fields.String(
            title=DESC['ip_address'], description=DESC['ip_address'],
            nullable=True)
        system = fields.String(
            title=DESC['system'], description=DESC['system'])
        type = fields.String(
            title=DESC['type'], description=DESC['type'])
        profiles = fields.List(
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

    def do_create(self, properties):
        """
        Use the permissions on the system to allow access to the interfaces.

        Args:
            properties (dict): field=value combination for the item to be
                               created

        Raises:
            Forbidden: in case user has no permission to perform action
            ItemNotFoundError: in case hypervisor profile is specified but not
                               found

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
            if not self._is_owner_or_admin(instance):
                # no role in system's project: cannot list
                if self._get_role_for_project(
                        instance.system_rel.project_id) is None:
                    continue

            allowed_instances.append(instance)

        return Pagination.from_list(
            allowed_instances, kwargs['page'], kwargs['per_page'])
    # do_list()

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

        # an iface cannot change its system so we only allow to set it on
        # creation
        if 'system' in properties and properties['system'] != item.system:
            raise BaseHttpError(
                400, msg='Interfaces cannot change their associated system')

        updated_item = self.manager.update(item, properties)

        # don't waste resources building the object in the answer,
        # just give the id and let the client decide if it needs more info (in
        # which case it can use the provided id to request the item)
        return updated_item.id
    # do_update()

# SystemIfaceResource
