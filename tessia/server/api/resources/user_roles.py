# Copyright 2017 IBM Corp.
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
from flask_potion.instances import Pagination
from tessia.server.api.exceptions import BaseHttpError
from tessia.server.api.resources.secure_resource import SecureResource
from tessia.server.db.models import UserRole
from werkzeug.exceptions import Forbidden

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'user': 'User login',
    'project': 'Project name',
    'role': 'Role',
}

#
# CODE
#
class UserRoleResource(SecureResource):
    """
    Resource for user roles
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = UserRole

        # name of the resource in the url
        name = 'user-roles'

        title = 'User role'
        description = (
            'A user role allows certain actions for a user on a project')
        human_identifiers = ['user', 'project', 'role']

    class Schema:
        """
        Potion's schema section
        """
        # relations
        user = fields.String(
            title=DESC['user'], description=DESC['user'])
        project = fields.String(
            title=DESC['project'], description=DESC['project'])
        role = fields.String(
            title=DESC['role'], description=DESC['role'])
    # Schema

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
        # non restricted user: regular listing is allowed
        if not flask_global.auth_user.restricted:
            return self.manager.paginated_instances(**kwargs)

        # for restricted users, filter the list by the projects they have
        # a role
        allowed_instances = []
        for instance in self.manager.instances(kwargs.get('where'),
                                               kwargs.get('sort')):
            user_role = self._perman.get_role_for_project(
                flask_global.auth_user, instance.project_id)
            if not user_role:
                continue
            allowed_instances.append(instance)

        return Pagination.from_list(
            allowed_instances, kwargs['page'], kwargs['per_page'])
    # do_list()

    def do_read(self, id): # pylint: disable=redefined-builtin
        """
        Custom implementation of item reading.

        Args:
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Raises:
            BaseHttpError: 404 in case user has no rights to read item

        Returns:
            json: json representation of item
        """
        item = self.manager.read(id)
        # non restricted user: regular reading is allowed
        if not flask_global.auth_user.restricted:
            return item

        # for restricted users they must have access to the project (a role)
        user_role = self._perman.get_role_for_project(
            flask_global.auth_user, item.project_id)
        if not user_role:
            raise BaseHttpError(404, msg='Item not found')

        return item
    # do_read()

    def do_update(self, properties, id):
        """
        Custom update action, blocks this operation as it is not allowed.
        All fields of a row make it unique so an update is replaced by a
        delete + create.

        Args:
            properties (dict): field=value combination for the fields to be
                               updated
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Raises:
            Forbidden: always, since operation is not allowed
        """
        # pylint: disable=redefined-builtin

        # not allowed
        raise Forbidden()
    # do_update()
# UserRoleResource
