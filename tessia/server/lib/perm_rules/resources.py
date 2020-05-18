# Copyright 2020 IBM Corp.
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
Module consolidating permission rules
"""

#
# IMPORTS
#
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import and_
from sqlalchemy.sql.expression import or_
from tessia.server.db.models import LogicalVolume
from tessia.server.db.models import IpAddress
from tessia.server.db.models import NetZone
from tessia.server.db.models import Project
from tessia.server.db.models import Repository
from tessia.server.db.models import Role
from tessia.server.db.models import StoragePool
from tessia.server.db.models import StorageServer
from tessia.server.db.models import StorageVolume
from tessia.server.db.models import Subnet
from tessia.server.db.models import System
from tessia.server.db.models import SystemIface
from tessia.server.db.models import SystemProfile
from tessia.server.db.models import Template
from tessia.server.db.models import User
from tessia.server.db.models import UserRole

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class ResourceBase(object):
    """
    Base class for providing permissions to secured resources
    """

    @classmethod
    def protect_query(cls, query, user):
        """
        Apply role filter to a query

        Base implementation provides default access mode:
        - sandbox cannot read a resource
        - restricted users can only read their project resources
        - everyone else can read everything
        """        
        stmt = query.session.query(UserRole).join(Role).join(User).\
            filter(
                User.id == user.id,
                # deny sandbox
                # deny restricted, unless same project or user is owner
                # allow unrestricted
                Role.name != 'USER_SANDBOX',
                or_(User.restricted == False,
                    cls._Resource.project_id == UserRole.project_id,
                    cls._Resource.owner_id == User.id))

        # additional check for admin user
        is_admin_stmt = query.session.query(User).\
            filter(
                User.id == user.id,
                User.admin == True
            )

        return query.filter(or_(stmt.exists(), is_admin_stmt.exists()))

    # TODO: implement checks for create, update and delete

class UserRolesPermissions(object):
    """
    Permissions class for user-roles requests
    """
    _Resource = UserRole

    @classmethod
    def protect_query(cls, query, user):
        """
        Apply role filter to a query

        User-roles have following access rules:
        - sandbox and restricted can only list their project members
        - everyone else can read everything
        """
        # Original query is also bound for UserRole, so we need to have
        # an alias to the same table to distinguish between them
        ur_alias = aliased(UserRole)
        stmt = query.session.query(ur_alias).join(Role).join(User).\
            filter(
                User.id == user.id,
                # deny sandbox and/or restricted, unless same project
                # allow everyone else
                or_(and_(User.restricted == False,
                         Role.name != 'USER_SANDBOX'),
                    cls._Resource.project_id == ur_alias.project_id))
            
        # additional check for admin user
        is_admin_stmt = query.session.query(User).\
            filter(
                User.id == user.id,
                User.admin == True
            )

        return query.filter(or_(stmt.exists(), is_admin_stmt.exists()))

class SystemAttached(ResourceBase):
    """
    Resources that have System attachment
    """

    @classmethod
    def protect_query(cls, query, user):
        """
        Apply role filter to a query

        System-attached resources extend basic access mode:
        - restricted users may read a resource if it is attached to an
          owned or accessible system
        """

        # We're using outerjoin to Systems, because system_id may be null.
        # If that were the case, inner join would skip the whole entry,
        # whereas outerjoin keeps it and replaces all joined System fields
        # with null. This is very convenient here, because all comparisons
        # to null are false and can safely be used in "or" clause.
        stmt = query.session.query(UserRole).join(Role).join(User).\
            outerjoin(System, cls._Resource.system_id == System.id).\
            filter(
                User.id == user.id,
                # deny sandbox
                # deny restricted, unless same project or user is owner
                #                  or likewise for designated system
                # allow unrestricted
                Role.name != 'USER_SANDBOX',
                or_(User.restricted == False,
                    cls._Resource.project_id == UserRole.project_id,
                    cls._Resource.owner_id == User.id,
                    System.project_id == UserRole.project_id,
                    System.owner_id == User.id
                    ))
        
        # additional check for admin user
        is_admin_stmt = query.session.query(User).\
            filter(
                User.id == user.id,
                User.admin == True
            )

        return query.filter(or_(stmt.exists(), is_admin_stmt.exists()))

class SystemRelated(ResourceBase):
    """
    Resources that have System relation
    """

    @classmethod
    def protect_query(cls, query, user):
        """
        Apply role filter to a query

        System-related resources inherit basic access mode from related object
        """

        # Original query is likely joined with System, so we need to have
        # an alias to the same table to distinguish between them
        sys_alias = aliased(System)
        stmt = query.session.query(UserRole).join(Role).join(User).\
            join(sys_alias, cls._Resource.system_id == sys_alias.id).\
            filter(
                User.id == user.id,
                # deny sandbox
                # deny restricted, unless same project or user is owner
                #                  or likewise for designated system
                # allow unrestricted
                Role.name != 'USER_SANDBOX',
                or_(User.restricted == False,
                    sys_alias.project_id == UserRole.project_id,
                    sys_alias.owner_id == User.id,
                    ))
        
        # additional check for admin user
        is_admin_stmt = query.session.query(User).\
            filter(
                User.id == user.id,
                User.admin == True
            )

        return query.filter(or_(stmt.exists(), is_admin_stmt.exists()))

class LogicalVolumePermissions(SystemAttached):
    """
    Access to LogicalVolume
    """
    _Resource = LogicalVolume

class IpAddressPermissions(SystemAttached):
    """
    Access to IpAddress
    """
    _Resource = IpAddress

class NetZonePermissions(ResourceBase):
    """
    Access to NetZone
    """
    _Resource = NetZone

class RepositoryPermissions(ResourceBase):
    """
    Access to Repository
    """
    _Resource = Repository

class StoragePoolPermissions(ResourceBase):
    """
    Access to StoragePool
    """
    _Resource = StoragePool

class StorageServerPermissions(ResourceBase):
    """
    Access to StorageServer
    """
    _Resource = StorageServer

class StorageVolumePermissions(SystemAttached):
    """
    Access to StorageVolume
    """
    _Resource = StorageVolume
    
class SubnetPermissions(ResourceBase):
    """
    Access to Subnet
    """
    _Resource = Subnet

class SystemPermissions(ResourceBase):
    """
    Access to System
    """
    _Resource = System

class SystemIfacePermissions(SystemRelated):
    """
    Access to SystemIface
    """
    _Resource = SystemIface

class SystemProfilePermissions(SystemRelated):
    """
    Access to SystemProfile
    """
    _Resource = SystemProfile

class TemplatePermissions(ResourceBase):
    """
    Access to Template
    """
    _Resource = Template
