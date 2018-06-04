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
Extended implementation of potion's ModelResource
"""

#
# IMPORTS
#
from flask import g as flask_global
from flask_potion import ModelResource
from flask_potion import exceptions as potion_exceptions
from flask_potion.fields import Inline
from flask_potion.instances import Instances
from flask_potion.instances import Pagination
from flask_potion.routes import Route
from tessia.server.api import exceptions as api_exceptions
from tessia.server.lib.perm_manager import PermManager
from tessia.server.db import exceptions as db_exceptions
from tessia.server.db.models import ResourceMixin
from werkzeug.exceptions import Forbidden

#
# CONSTANTS AND DEFINITIONS
#
# regex pattern to be used for name fields, defined here to be shared by the
# children resource classes
NAME_PATTERN = r'^\w+[\w\s\.\-]+$'

#
# CODE
#
# pylint: disable=redefined-builtin
class SecureResource(ModelResource):
    """
    A specialized resource with error handling and permission verification
    capabilities. The method are not in alphabetical order because the
    decorators have dependencies between them.
    """
    def __init__(self, *args, **kwargs):
        """
        Constructor, creates permission manager instance.
        """
        super().__init__(*args, **kwargs)
        self._perman = PermManager()
    # __init__()

    # routes section, we reimplement the routes defined in ModelResource
    # to add the error handling and permission verification bits.
    # this is done in such a way that a family of do_{operation} methods are
    # defined which can be overridden by specialized children resource classes.
    @Route.GET('', rel="instances")
    def instances(self, **kwargs):
        """
        Handler for the list items operation via GET method, forwards it to the
        specialized do_list method.

        Args:
            kwargs (dict): contains keys like 'where' (filtering) and
                           'per_page' (pagination), see potion doc for details
        Returns:
            json: json response as defined by response_schema property
        """
        return self.do_list(**kwargs)
    instances.request_schema = instances.response_schema = Instances()

    @Route.GET(lambda r: '/<{}:id>'.format(r.meta.id_converter),
               rel="self", attribute="instance")
    def read(self, id):
        """
        Handler for the get item operation via GET method, forwards it to the
        specialized do_read method.

        Args:
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Returns:
            json: json response as defined by response_schema property

        Raises:
            Forbidden: in case user has no rights
        """
        try:
            item = self.do_read(id)
        except PermissionError as exc:
            raise Forbidden(description=str(exc))
        return item
    # read()
    read.request_schema = None
    read.response_schema = Inline('self')

    @instances.POST(rel="create")
    def create(self, properties):
        """
        Handler for the create item via POST operation, forwards it to the
        specialized do_create method while doing error handling.

        Args:
            properties (dict): field=value combination for the item to be
                               created

        Returns:
            json: json response as defined by response_schema property

        Raises:
            Forbidden: in case user has no rights
        """
        # set the property so that the field always reflects last user to
        # modify the item
        properties['modifier'] = flask_global.auth_user.login

        try:
            item = self.do_create(properties)
        except potion_exceptions.DuplicateKey as exc:
            raise api_exceptions.ConflictError(exc, self)
        except db_exceptions.AssociationError as exc:
            raise api_exceptions.ItemNotFoundError(
                exc.column, exc.value, self)
        except PermissionError as exc:
            raise Forbidden(description=str(exc))

        return item
    # create()
    create.request_schema = Inline('self')
    create.response_schema = None

    @read.PATCH(rel="update")
    def update(self, properties, id):
        """
        Handler for the update item operation via PATCH method, forwards it to
        the specialized do_update method while doing error handling.

        Args:
            properties (dict): field=value combination for the fields to be
                               updated
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Returns:
            json: json response as defined by response_schema property

        Raises:
            Forbidden: in case user has no rights
        """
        # set the property so that the field always reflects last user to
        # modify the item
        properties['modifier'] = flask_global.auth_user.login

        try:
            item = self.do_update(properties, id)
        except potion_exceptions.DuplicateKey as exc:
            raise api_exceptions.ConflictError(exc, self)
        except db_exceptions.AssociationError as exc:
            raise api_exceptions.ItemNotFoundError(
                exc.column, exc.value, self)
        except PermissionError as exc:
            raise Forbidden(description=str(exc))

        return item
    # update()
    update.request_schema = Inline('self', patchable=True)
    update.response_schema = None

    @update.DELETE(rel="destroy")
    def destroy(self, id):
        """
        Handler for the delete item operation via DELETE method, forwards it
        to the specialized do_delete method while doing error handling.

        Args:
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Returns:
            any: the return value of do_delete

        Raises:
            Forbidden: in case user has no rights
        """
        try:
            ret = self.do_delete(id)
        except potion_exceptions.BackendConflict as exc:
            # here we infer it's a integrity problem due to the lack of a
            # specific exception in potion exception hierarchy
            raise api_exceptions.IntegrityError(exc, self)
        except PermissionError as exc:
            raise Forbidden(description=str(exc))
        return ret
    # destroy()
    # end of routes section

    def do_create(self, properties):
        """
        Verify if the user attempting to create a new resource has the
        permission to do so. This function can be overriden in specialized
        classes that need additional verifications.

        Args:
            properties (dict): field=value combination for the item to be
                               created

        Raises:
            Forbidden: in case user has no permission to perform action

        Returns:
            int: id of created item
        """
        new_item = self.meta.model()
        # no project specified: find a role in a project while validating
        # permissions
        if properties.get('project') is None:
            properties['project'] = self._perman.can(
                'CREATE', flask_global.auth_user, new_item)
        else:
            # this can raise AssociationError which gets caught by create()
            new_item.project = properties['project']
            self._perman.can(
                'CREATE', flask_global.auth_user, new_item)

        # if not defined create the item beloging to the user requesting it
        properties['owner'] = properties.get('owner') or \
            flask_global.auth_user.login

        item = self.manager.create(properties)
        # don't waste resources building the object in the answer,
        # just give the id and let the client decide if it needs more info (in
        # which case it can use the provided id to request the item)
        return item.id
    # do_create()

    def do_delete(self, id): # pylint: disable=invalid-name
        """
        Verify if the user attempting to delete the instance has permission
        to do so. This function can be overriden in specialized classes that
        need additional verifications.

        Args:
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Raises:
            Forbidden: in case user has no permission to perform action

        Returns:
            bool: True
        """
        entry = self.manager.read(id)

        self._perman.can('DELETE', flask_global.auth_user, entry)

        self.manager.delete_by_id(id)
        return True
    # do_delete()

    def do_list(self, **kwargs):
        """
        Verify if the user attempting to list the resource instances has
        permissions to do so. This function can be overriden in specialized
        classes that need additional verifications.

        Args:
            kwargs (dict): contains keys like 'where' (filtering) and
                           'per_page' (pagination), see potion doc for details

        Returns:
            list: list of items retrieved, can be an empty in case no items are
                  found or a restricted user has no permission to see them
        """
        # model is a special resource: listing is allowed for all
        if not issubclass(self.meta.model, ResourceMixin):
            return self.manager.paginated_instances(**kwargs)
        # non restricted user: regular resource listing is allowed
        elif not flask_global.auth_user.restricted:
            return self.manager.paginated_instances(**kwargs)

        # for restricted users, filter the list by the projects they have
        # access or the resources they own
        allowed_instances = []
        for instance in self.manager.instances(kwargs.get('where'),
                                               kwargs.get('sort')):
            try:
                self._perman.can(
                    'READ', flask_global.auth_user, instance)
            except PermissionError:
                continue

            allowed_instances.append(instance)

        return Pagination.from_list(
            allowed_instances, kwargs['page'], kwargs['per_page'])
    # do_list()

    def do_read(self, id): # pylint: disable=invalid-name
        """
        Verify if the user attempting to read the given resource has
        permissions to do so. This function can be overriden in specialized
        classes that need additional verifications.

        Args:
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Raises:
            Forbidden: in case user has no permission to perform action

        Returns:
            json: json representation of item as defined by response_schema
                  property in route's decorator
        """
        item = self.manager.read(id)

        self._perman.can('READ', flask_global.auth_user, item)

        return item
    # do_read()

    def do_update(self, properties, id): # pylint: disable=invalid-name
        """
        Verify if the user attempting to update the given resource has
        permissions to do so. This function can be overriden in specialized
        classes that need additional verifications.

        Args:
            properties (dict): field=value combination for the fields to be
                               updated
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Raises:
            Forbidden: in case user has no permission to perform action

        Returns:
            int: id of updated item

        """
        item = self.manager.read(id)

        # validate permission on the object
        self._perman.can('UPDATE', flask_global.auth_user, item)

        updated_item = self.manager.update(item, properties)

        # don't waste resources building the object in the answer,
        # just give the id and let the client decide if it needs more info (in
        # which case it can use the provided id to request the item)
        return updated_item.id
    # do_update()

# SecureResource
