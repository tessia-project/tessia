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
from flask_potion.contrib.alchemy.filters import EqualFilter
from flask_potion.filters import Condition
from tessia.server.db.models import UserKey
from tessia.server.api.exceptions import BaseHttpError
from tessia.server.api.exceptions import ItemNotFoundError
from tessia.server.api.resources.secure_resource import SecureResource
from werkzeug.exceptions import Forbidden

import uuid

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'key_id': 'Key ID',
    'created': 'Date created',
    'last_used': 'Last used',
    'desc': 'Description',
    'user': 'Key Owner',
}

#
# CODE
#


class UserKeyResource(SecureResource):
    """
    Resource for user authentication keys
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = UserKey

        # name of the resource in the url
        name = 'user-keys'

        # fields not imported from sa's model
        exclude_fields = ['key_secret']

        title = 'Authentication key'
        description = (
            'An authentication key allows an user to connect to the API')
        human_identifiers = ['key_id']

    class Schema:
        """
        Potion's schema section
        """
        # io attribute set field permissions
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        key_id = fields.String(
            title=DESC['key_id'], description=DESC['key_id'], io='r',
            nullable=True)
        created = fields.DateTime(
            title=DESC['created'], description=DESC['created'], io='r',
            nullable=True)
        last_used = fields.DateTime(
            title=DESC['last_used'], description=DESC['last_used'], io='r',
            nullable=True)
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], io='rw',
            nullable=True)
        # relations
        user = fields.String(
            title=DESC['user'], description=DESC['user'], io='r',
            nullable=True)
    # Schema

    def do_create(self, properties):
        """
        Custom implementation of key creation. Enforce password based
        authentication to perform key related operations and generate the id
        and secret for a new key.

        Args:
            properties (dict): field=value combination for the item to be
                               created

        Raises:
            BaseHttpError: in case password based auth was not used

        Returns:
            list: [key_id, key_secret] created so that client can store it
                  locally.
        """
        # must be authenticated with password
        if flask_global.auth_method != 'basic':
            raise BaseHttpError(
                code=403,
                body='For this operation login and password must be provided')

        properties['user'] = flask_global.auth_user.login
        properties['key_id'] = str(uuid.uuid4()).replace('-', '')
        properties['key_secret'] = str(uuid.uuid4()).replace('-', '')
        item = self.manager.create(properties)
        return [item.key_id, item.key_secret]
    # do_create()

    def do_delete(self, key_id):
        """
        Custom implementation of key deletion. Enforce password based
        authentication and permission control.

        Args:
            key_id (int): user key id

        Raises:
            BaseHttpError: in case password based auth was not used
            ItemNotFoundError: if id specified does not exist or user is
                               neither key's owner nor admin

        Returns:
            bool: True
        """
        user_key = self.manager.read(key_id)

        # user is not the key owner and is not admin: report item as not found
        # instead of forbidden for security reasons (forbidden would tip the
        # user that such key_id exists)
        if (user_key.user_rel.id != flask_global.auth_user.id and
                not flask_global.auth_user.admin):
            raise ItemNotFoundError('id', key_id, self)

        # must be authenticated with password
        if flask_global.auth_method != 'basic':
            raise BaseHttpError(
                code=403,
                body='For this operation login and password must be provided')

        # perform operation
        self.manager.delete_by_id(key_id)
        return True
    # do_delete()

    def do_list(self, **kwargs):
        """
        Custom implementation of key listing. Make sure only admin users can
        list other users' keys.

        Args:
            kwargs (dict): contains keys like 'where' (filtering) and
                           'per_page' (pagination), see potion doc for details

        Raises:
            None

        Returns:
            list: list of items retrieved, can be an empty list
        """
        # only admin can list keys from other users
        if not flask_global.auth_user.admin:
            new_where = []
            # remove any existing filter on user attribute
            for condition in kwargs['where']:
                if condition.attribute == 'user':
                    continue
                new_where.append(condition)
            user_condition = Condition(
                'user',
                EqualFilter(
                    name=None,
                    field=self.Schema.user,
                    attribute='user',
                    column=self.Meta.model.user
                ),
                flask_global.auth_user.login)
            new_where.append(user_condition)
            kwargs['where'] = new_where

        return self.manager.paginated_instances(**kwargs)
    # do_list()

    def do_read(self, key_id):
        """
        Custom implementation of key reading. Make sure only admin users can
        list other users' keys.

        Args:
            key_id (any): user key id

        Raises:
            ItemNotFoundError: in case user is not admin or key's owner

        Returns:
            json: json representation of item
        """

        user_key = self.manager.read(key_id)
        # user is not the key owner and is not admin: report item as not found
        # instead of forbidden for security reasons (forbidden would tip the
        # user that such key_id exists)
        if (user_key.user_rel.id != flask_global.auth_user.id and
                not flask_global.auth_user.admin):
            raise ItemNotFoundError('id', key_id, self)

        return self.manager.read(key_id)
    # do_read()

    def do_update(self, properties, key_id):
        """
        Custom update action, blocks this operation as it is not allowed. Users
        needing an update should delete and generate a new key instead.

        Args:
            properties (dict): field=value combination for the fields to be
                               updated
            key_id (any): user key id

        Raises:
            Forbidden: always, since operation is not allowed
        """

        # not allowed
        raise Forbidden()
    # do_update()

# UserKeyResource
