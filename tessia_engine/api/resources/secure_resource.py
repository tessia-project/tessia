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
from tessia_engine.api import exceptions as api_exceptions
from tessia_engine.db import exceptions as db_exceptions
from tessia_engine.db.models import Project
from tessia_engine.db.models import RoleAction
from tessia_engine.db.models import UserRole
from werkzeug.exceptions import Forbidden

#
# CONSTANTS AND DEFINITIONS
#

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
        """
        return self.do_read(id)
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
        """
        try:
            ret = self.do_delete(id)
        except potion_exceptions.BackendConflict as exc:
            # here we infer it's a integrity problem due to the lack of a
            # specific exception in potion exception hierarchy
            raise api_exceptions.IntegrityError(exc, self)
        return ret
    # destroy()
    # end of routes section

    def _assert_permission(self, action, target_obj, target_type):
        """
        Helper function, asserts if the logged user has the necessary
        permissions to perform the specified action upon the target.

        Args:
            action (str): one of CREATE, UPDATE, DELETE
            target_obj (ResourceMixin): sa's object
            target_type (str): type of the target to report in case of error

        Returns:
            None

        Raises:
            Forbidden: in case user has no permission
        """
        # user is owner or an administrator: permission is granted
        if self._is_owner_or_admin(target_obj):
            return

        match = self._get_project_for_action(
            action, target_obj.__tablename__, target_obj.project_id)
        # no permission in target's project: report error
        if match is None:
            msg = ('User has no {} permission for the specified '
                   '{}'.format(action, target_type))
            raise Forbidden(description=msg)
    # _assert_permission()

    @staticmethod
    def _get_project_for_action(action_name, resource_type, project_id=None):
        """
        Query the database and return the name of the project which allows
        the user to perform the specified operation, or None if no such
        permission exists.

        Args:
            action_name (str): the action to be performed (i.e. CREATE)
            resource_type (string): tablename of target's resource
            project_id (int): id of the target project, if None means
                              to find a suitable project

        Returns:
            str: project name, or None if not found
        """
        query = Project.query.join(
            UserRole, UserRole.project_id == Project.id
        ).filter(
            UserRole.user_id == flask_global.auth_user.id
        ).filter(
            RoleAction.role_id == UserRole.role_id
        ).filter(
            RoleAction.resource == resource_type.upper()
        ).filter(
            RoleAction.action == action_name
        )
        # no project specified: find one that allows the specified action
        if project_id is None:
            query = query.filter(UserRole.project_id == Project.id)
        # project specified: verify if there is a permission for the user to
        # perform the specified action on that project
        else:
            query = query.filter(UserRole.project_id == project_id)

        project = query.first()
        if project is not None:
            project = project.name

        return project
    # _get_project_for_action()

    def _get_project_for_create(self, resource_type, project):
        """
        If a project was specified, verify if the user has create permission on
        it, otherwise the method tries to find a project where user has create
        permission. In case both fail a forbidden exception is raised.
        """
        # project specified by an admin user: no permission verification needed
        if project is not None and flask_global.auth_user.admin:
            return project

        if project is None:
            project_id = None
        else:
            project_id = Project.query.filter_by(name=project).one().id
        # perform the db query
        project_match = self._get_project_for_action(
            'CREATE', resource_type, project_id)

        # permission was found or validated: return corresponding project
        if project_match is not None:
            return project_match

        # user had not specified project: report no project with permission
        # was found
        if project is None:
            msg = ('No create permission found for the user in any '
                   'project')
        # project was specified: report that user has no permission on it
        else:
            msg = ('User has no create permission for the specified '
                   'project')
        # send the forbidden response with the appropriate explanation
        raise Forbidden(description=msg)
    # _get_project_for_create()

    @staticmethod
    def _get_role_for_project(project_id):
        """
        Query the db for any role associated with the authenticated user on
        the passed project.

        Args:
            project_id (int): id of the target project

        Returns:
            UserRole: a role associated with user or None if not found
        """
        query = UserRole.query.join(
            'project_rel'
        ).join(
            'user_rel'
        ).join(
            'role_rel'
        ).filter(
            UserRole.user_id == flask_global.auth_user.id
        ).filter(
            RoleAction.role_id == UserRole.role_id
        ).filter(
            UserRole.project_id == project_id
        )
        return query.first()
    # _get_role_for_project()

    @staticmethod
    def _is_owner_or_admin(target_obj):
        """
        Return whether the logged user is the owner of the target object or an
        administrator.

        Args:
            target_obj (ResourceMixin): sa's object

        Returns:
            bool: True if logged user is administrator or owner of the target
        """
        return (target_obj.owner_id == flask_global.auth_user.id or
                flask_global.auth_user.admin)
    # _is_owner_or_admin()

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
        # model is a special resource: only admins can handle it
        if not hasattr(self.meta.model, 'project_id'):
            # user is admin: the operation is allowed
            if flask_global.auth_user.admin:
                return self.manager.create(properties).id

            # for non admins, action is prohibited
            raise Forbidden(
                'You need administrator privileges to perform this '
                'operation')

        project = self._get_project_for_create(
            self.meta.model.__tablename__, properties.get('project', None))

        # create the item beloging to the user requesting it
        properties['project'] = project
        properties['owner'] = flask_global.auth_user.login

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
        # model is a special resource: only admins can handle it
        if not hasattr(self.meta.model, 'project_id'):
            # user is admin: the operation is allowed
            if flask_global.auth_user.admin:
                self.manager.delete_by_id(id)
                return True

            # for non admins, action is prohibited
            raise Forbidden(
                'You need administrator privileges to perform this '
                'operation')

        entry = self.manager.read(id)

        # validate user permission on object
        self._assert_permission('DELETE', entry, 'resource')

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
        if not hasattr(self.meta.model, 'project_id'):
            return self.manager.paginated_instances(**kwargs)
        # non restricted user: regular resource listing is allowed
        elif not flask_global.auth_user.restricted:
            return self.manager.paginated_instances(**kwargs)

        # for restricted users, filter the list by the projects they have
        # access or if they own the resource
        allowed_instances = []
        for instance in self.manager.instances(kwargs.get('where'),
                                               kwargs.get('sort')):
            # user is not the resource's owner or an administrator: verify if
            # they have a role in resource's project
            if not self._is_owner_or_admin(instance):
                # no role in resource's project: cannot list
                if self._get_role_for_project(instance.project_id) is None:
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

        # model is a special resource: reading is allowed for all
        if not hasattr(self.meta.model, 'project_id'):
            return item
        # non restricted user: regular resource reading is allowed
        elif not flask_global.auth_user.restricted:
            return item

        # user is not the resource's owner or an administrator: verify if
        # they have a role in resource's project
        if not self._is_owner_or_admin(item):
            # no role in resource's project: access forbidden
            if self._get_role_for_project(item.project_id) is None:
                msg = 'User has no READ permission for the specified resource'
                raise Forbidden(description=msg)

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
        # model is a special resource: only admins can handle it
        if not hasattr(self.meta.model, 'project_id'):
            # not an admin user: action is prohibited
            if not flask_global.auth_user.admin:
                raise Forbidden(
                    'You need administrator privileges to perform this '
                    'operation')

            # user is admin: the operation is allowed
            item = self.manager.read(id)
            updated_item = self.manager.update(item, properties)
            return updated_item.id

        item = self.manager.read(id)

        # validate permission on the object
        self._assert_permission('UPDATE', item, 'resource')

        updated_item = self.manager.update(item, properties)

        # don't waste resources building the object in the answer,
        # just give the id and let the client decide if it needs more info (in
        # which case it can use the provided id to request the item)
        return updated_item.id
    # do_update()

# SecureResource
