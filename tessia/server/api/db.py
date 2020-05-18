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
Configuration of flask-sqlalchemy for use by flask app
"""

#
# IMPORTS
#
from flask import g as flask_global
from sqlalchemy.orm.mapper import Mapper
from sys import stderr
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import BASE
from tessia.server.db.models import LogicalVolume
from tessia.server.db.models import IpAddress
from tessia.server.db.models import NetZone
from tessia.server.db.models import Repository
from tessia.server.db.models import StoragePool
from tessia.server.db.models import StorageServer
from tessia.server.db.models import StorageVolume
from tessia.server.db.models import Subnet
from tessia.server.db.models import System
from tessia.server.db.models import SystemIface
from tessia.server.db.models import SystemProfile
from tessia.server.db.models import Template
from tessia.server.db.models import UserRole
from tessia.server.lib.perm_rules.resources import LogicalVolumePermissions
from tessia.server.lib.perm_rules.resources import IpAddressPermissions
from tessia.server.lib.perm_rules.resources import NetZonePermissions
from tessia.server.lib.perm_rules.resources import RepositoryPermissions
from tessia.server.lib.perm_rules.resources import StoragePoolPermissions
from tessia.server.lib.perm_rules.resources import StorageServerPermissions
from tessia.server.lib.perm_rules.resources import StorageVolumePermissions
from tessia.server.lib.perm_rules.resources import SubnetPermissions
from tessia.server.lib.perm_rules.resources import SystemPermissions
from tessia.server.lib.perm_rules.resources import SystemIfacePermissions
from tessia.server.lib.perm_rules.resources import SystemProfilePermissions
from tessia.server.lib.perm_rules.resources import TemplatePermissions
from tessia.server.lib.perm_rules.resources import UserRolesPermissions

import flask_sqlalchemy as flask_sa

#
# CONSTANTS AND DEFINITIONS
#

CLASS_MAPPER = {
    LogicalVolume: LogicalVolumePermissions,
    IpAddress: IpAddressPermissions,
    NetZone: NetZonePermissions,
    Repository: RepositoryPermissions,
    StoragePool: StoragePoolPermissions,
    StorageServer: StorageServerPermissions,
    StorageVolume: StorageVolumePermissions,
    Subnet: SubnetPermissions,
    System: SystemPermissions,
    SystemIface: SystemIfacePermissions,
    SystemProfile: SystemProfilePermissions,
    Template: TemplatePermissions,
    UserRole: UserRolesPermissions
}

#
# CODE
#

class RoleBasedQuery(flask_sa.BaseQuery):
    """
    Implement role-based access queries for protected resources

    This class overrides several methods of Flask/SqlAlchemy query class
    and adds additional filter clause to a constructed query. This way
    only items that are allowed to be seen by the current Flask user
    are selected.
    """
    def __init__(self, entities, session=None):
        """
        Initialize query object

        Not all resources are protected, we only apply filtering to a
        chosen subset.
        """
        self.permissions_class = None
        self.permissions_applied = False

        super().__init__(entities, session)

        # Query is created against a certain model; check the model class here
        # and choose the role-bsaed implementation
        if isinstance(entities, Mapper):
            if entities.class_ in CLASS_MAPPER:
                self.permissions_class = CLASS_MAPPER[entities.class_]

    def __iter__(self):
        """
        Override query iterator

        Query iterator is called by all methods that retrieve results from
        the database, so we can apply the clause here.

        However, under certain conditions we are unable to alter the query,
        e.g. when offset or limit clauses were applied. That's why we override
        all other calls too.
        """
        return self._apply_role_clause().__iter__()

    def _apply_role_clause(self):
        """
        Apply role-based restrictions on the query before it is finalized
        with limit or offset.

        We cannot modify the query after limit/offset, so we override these too
        to insert our role-based subquery.

        Returns:
            Query: SqlAlchemy query object instance
        """
        if self.permissions_class is not None and not self.permissions_applied:
            self.permissions_applied = True
            query = self.permissions_class.protect_query(
                self, flask_global.auth_user)
            return super(flask_sa.BaseQuery, query)
        return super()

    def all(self):
        return self._apply_role_clause().all()

    def count(self):
        return self._apply_role_clause().count()

    def first(self):
        return self._apply_role_clause().first()

    def one(self):
        return self._apply_role_clause().one()

    def one_or_none(self):
        return self._apply_role_clause().one_or_none()

    def scalar(self):
        return self._apply_role_clause().scalar()

    def value(self, column):
        return self._apply_role_clause().value(column)

    def values(self, *columns):
        return self._apply_role_clause().values(*columns)

    def limit(self, limit):
        return self._apply_role_clause().limit(limit)

    def offset(self, offset):
        return self._apply_role_clause().offset(offset)

    def order_by(self, *criterion):
        return self._apply_role_clause().order_by(*criterion)

class RoleBasedQueryDebug(RoleBasedQuery):
    """
    Debug class that prints out executed statements
    """

    def __iter__(self):
        """
        Override iterator to print final SQL statement
        """
        if self.permissions_class is not None:
            print("[q] --> ", self.permissions_class, ":__iter__", file=stderr)
            print("[q] --> ",
                  self._apply_role_clause().statement.compile(
                      compile_kwargs={"literal_binds": True}), file=stderr)
        return super().__iter__()

class _AppDbManager(object):
    """
    Class to handle db object creation and configuration
    """
    _singleton = False

    def __init__(self):
        """
        Constructor, defines the variable that stores the db object instance
        as empty. The db initialization is triggered on the first time the
        variable 'db' is referenced.
        """
        self._db = None
    # __init__()

    def __new__(cls, *args, **kwargs):
        """
        Modules should not instantiate this class since there should be only
        one db entry point at a time for all modules.

        Args:
            None

        Returns:
            _AppDbManager: object instance

        Raises:
            NotImplementedError: as the class should not be instantiated
        """
        if cls._singleton:
            raise NotImplementedError('Class should not be instantiated')
        cls._singleton = True

        return super().__new__(cls, *args, **kwargs)
    # __new__()

    def _create_db(self):
        """
        Create the flask-sqlalchemy instance for db communication

        Returns:
            SQLAlchemy: instance of flask-SQLAlchemy
        """
        def patched_base(self, *args, **kwargs):
            """
            Change the flask_sqlalchemy base creator function to use our custom
            declarative base in place of the default one.
            """
            # add our base to the query property of each model we have
            # in case a query property was already added by the db.connection
            # module it will be overriden here, which is ok because the
            # flask_sa implementation just add a few bits more like pagination
            for cls_model in BASE._decl_class_registry.values():
                if isinstance(cls_model, type):
                    cls_model.query_class = RoleBasedQuery
                    cls_model.query = flask_sa._QueryProperty(self)

            # return our base as the base to be used by flask-sa
            return BASE
        # patched_base()

        flask_sa.SQLAlchemy.make_declarative_base = patched_base
        flask_sa.SQLAlchemy.create_session = lambda *args, **kwargs: \
            MANAGER.session

        return flask_sa.SQLAlchemy(model_class=BASE)
    # _create_db()

    @property
    def db(self):
        """
        Return the flask-sa's db object
        """
        if self._db is not None:
            return self._db

        self._db = self._create_db()
        return self._db
    # db
# _AppDbManager

API_DB = _AppDbManager()
