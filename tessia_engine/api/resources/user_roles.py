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
from flask_potion import fields
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import UserRole
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