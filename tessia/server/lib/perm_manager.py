# Copyright 2018 IBM Corp.
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
Module consolidating permission handling routines
"""

#
# IMPORTS
#
from tessia.server.db.exceptions import AssociationError
from tessia.server.db.models import Project
from tessia.server.db.models import ResourceMixin
from tessia.server.db.models import Role
from tessia.server.db.models import RoleAction
from tessia.server.db.models import UserRole

import logging

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class PermManager(object):
    """
    Manage user permission verifications
    """
    def __init__(self):
        """
        Constructor, creates logger instance.
        """
        self._logger = logging.getLogger(__name__)
    # __init__()

    def _assert_create(self, user, item):
        """
        Verify if the user can create the target item.

        Args:
            user (User): user db object
            item (db.models.BASE): target's db object (not committed yet)

        Returns:
            str: project where user can create item

        Raises:
            AssociationError: if an invalid project was specified
            PermissionError: if user has no rights
        """
        # WARNING: it's very important to refer to the field itself
        # 'project_id' and not to the relation 'project' because the db object
        # is not committed yet which means the relation does not work

        # model is a special resource: only admins can handle it
        if not issubclass(item.__class__, ResourceMixin):
            # user is admin: the operation is allowed
            if user.admin:
                return None

            # for non admins, action is prohibited
            raise PermissionError(
                'You need administrator privileges to perform this operation')

        # project specified by an admin user: no permission verification needed
        if item.project_id is not None and user.admin:
            try:
                project_name = Project.query.filter_by(
                    id=item.project_id).first().id
            except AttributeError:
                raise AssociationError(
                    model=item, column='project_id',
                    value=item.project_id, associated_model=Project,
                    associated_column='id')

            return project_name

        # If a project was specified, verify if the user has create permission
        # on it, otherwise try to find a project where user has create
        # permission. In case both fail a forbidden exception is raised.
        project_match = self._get_project_for_action(
            user, 'CREATE', item.__tablename__, item.project_id)

        # permission was found or validated: return corresponding project
        if project_match is not None:
            return project_match

        # user did not specified project: report no project with permission
        # was found
        if item.project_id is None:
            if user.admin:
                msg = ('Could not detect which project to use, specify one')
            else:
                msg = ('No CREATE permission found for the user in any '
                       'project')
        # project was specified: report that user has no permission on it
        else:
            msg = ('User has no CREATE permission for the specified '
                   'project')
        raise PermissionError(msg)
    # _assert_create()

    def _assert_permission(self, user, action, target_obj, target_type):
        """
        Helper function, asserts if the given user has the necessary
        permissions to perform the specified action upon the target.

        Args:
            user (User): user db object
            action (str): one of CREATE, UPDATE, DELETE
            target_obj (db.models.BASE): db object
            target_type (str): type of the target to report in case of error

        Raises:
            PermissionError: in case user has no permission
        """
        # model is a special resource: only admins can handle it
        if not issubclass(target_obj.__class__, ResourceMixin):
            # user is admin: the operation is allowed
            if user.admin:
                return

            # for non admins, action is prohibited
            raise PermissionError(
                'You need administrator privileges to perform this operation')

        # user is owner or an administrator: permission is granted
        if self.is_owner_or_admin(user, target_obj):
            return

        match = self._get_project_for_action(
            user, action, target_obj.__tablename__, target_obj.project_id)
        # no permission in target's project: report error
        if match is None:
            msg = ('User has no {} permission for the specified '
                   '{}'.format(action, target_type))
            raise PermissionError(msg)
    # _assert_permission()

    def _assert_read(self, user, item):
        """
        Verify if the given user has access to read the target item.

        Args:
            user (User): user db object
            item (db.models.BASE): target's db object

        Raises:
            PermissionError: if user has no permission
        """
        # model is a special resource: reading is allowed for all
        if not issubclass(item.__class__, ResourceMixin):
            return
        # non restricted user: regular resource reading is allowed
        elif not user.restricted:
            return

        # user is not the resource's owner or an administrator: verify
        # if they have a role in resource's project
        if not self.is_owner_or_admin(user, item):
            # no role in system's project
            if self._get_role_for_project(user, item.project_id) is None:
                raise PermissionError(
                    "User has no role assigned in resource's project")
    # _assert_read()

    @staticmethod
    def _get_project_for_action(user, action_name, resource_type,
                                project_id=None):
        """
        Query the database and return the name of the project which allows
        the user to perform the specified operation, or None if no such
        permission exists.

        Args:
            user (User): user db object
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
            UserRole.user_id == user.id
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

    @staticmethod
    def _get_role_for_project(user, project_id):
        """
        Query the db for any role associated with the given user on the
        provided project.

        Args:
            user (User): user db object
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
            UserRole.user_id == user.id
        ).filter(
            Role.id == UserRole.role_id
        ).filter(
            UserRole.project_id == project_id
        )
        return query.first()
    # _get_role_for_project()

    def can(self, action, user, item, item_desc='resource'):
        """
        Verify if a given action can be performed by a given user on a given
        object.

        Args:
            action (str): one of CREATE, DELETE, READ, UPDATE
            user (User): user db object
            item (db.models.BASE): target's db object
            item_desc (str): an optional item description to be used in error
                             messages

        Returns:
            str: for create action, project on which user has permission

        Raises:
            PermissionError: if user has no permission
            ValueError: if action is update/delete and item is None
        """
        action = action.upper()
        if action in ('UPDATE', 'DELETE'):
            self._assert_permission(user, action, item, item_desc)
            return None
        elif action == 'CREATE':
            return self._assert_create(user, item)
        elif action == 'READ':
            self._assert_read(user, item)
            return None

        raise ValueError('Cannot validate unknown action <{}>'.format(action))
    # can()

    @staticmethod
    def is_owner_or_admin(user, target_obj):
        """
        Return whether the given user is the owner of the target object or an
        administrator.

        Args:
            user (User): user db object
            target_obj (ResourceMixin): db object

        Returns:
            bool: True if user is administrator or owner of the target
        """
        return target_obj.owner_id == user.id or user.admin
    # is_owner_or_admin()
# PermManager()
