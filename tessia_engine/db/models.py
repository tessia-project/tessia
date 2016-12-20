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
Module containing the sqlalchemy models for the database
"""

#
# IMPORTS
#
from sqlalchemy import Column
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm import validates
from sqlalchemy.schema import ForeignKey
from sqlalchemy.schema import MetaData
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.types import BigInteger
from sqlalchemy.types import Boolean
from sqlalchemy.types import DateTime
from sqlalchemy.types import Integer
from sqlalchemy.types import LargeBinary
from sqlalchemy.types import SmallInteger
from sqlalchemy.types import String
from tessia_engine.db.exceptions import AssociationError

import ipaddress
import json
import os

#
# CONSTANTS AND DEFINITIONS
#
# patterns below are used to name indexes, constraints, primary keys
NAME_CONVENTION = {
    "columns": (
        lambda const, table: '_'.join([col.name for col in const.columns])),
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(columns)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(columns)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
BASE = declarative_base(metadata=MetaData(naming_convention=NAME_CONVENTION))

# some meta definitions are not recognized by pylint so disable some checks
# pylint: disable=no-self-argument,no-self-use,no-member,method-hidden

#
# CODE
#

# some comments regarding postgres:
# - we use the String type without fixed length because it performs better and
# imposes us no restriction on size. From postgres documentation
# (https://www.postgresql.org/docs/current/static/datatype-character.html):
# "in fact character(n) is usually the slowest of the three because of its
# additional storage costs and slower sorting. In most situations text or
# character varying should be used instead."
# - jsonb over json: for jsonb the content is parsed before being stored in the
# database, which allows indexing and thus querying significantly faster.

class CommonMixin(object):
    """
    Helper mixin to set attributes common to most classes
    """

    # pylint: disable=invalid-name
    id = Column(Integer, primary_key=True)

    def __init__(self, *args, **kwargs):
        """
        Simple constructor which only calls parent's constructor to allow
        cooperative multiple inheritance.
        """
        super().__init__(*args, **kwargs)
    # __init__()
# CommonMixin

class SchemaMixin(object):
    """
    Helper mixin to provide json-schema validation capability
    """
    _SCHEMA_FOLDER = '{}/schemas'.format(
        os.path.dirname(os.path.abspath(__file__)))
    _cache = {}

    @classmethod
    def get_schema(cls, field_name):
        """
        Return the json-schema for the field specified, or None if no schema is
        defined.
        """
        if not hasattr(cls, field_name):
            raise ValueError("Field '{}' not part of model".format(field_name))

        if field_name not in cls._cache:
            file_path = '{}/{}/{}.json'.format(
                cls._SCHEMA_FOLDER, cls.__tablename__, field_name)
            try:
                with open(file_path) as file_fd:
                    cls._cache[field_name] = json.loads(file_fd.read())
            except FileNotFoundError:
                cls._cache[field_name] = None

        return cls._cache[field_name]
    # get_schema()
# SchemaMixin

class User(CommonMixin, BASE):
    """Represents a user on the application"""

    __tablename__ = 'users'

    login = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    title = Column(String)
    restricted = Column(Boolean, nullable=False)
    admin = Column(Boolean, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<User(login='{}')>".format(self.login)
    # __repr__()
# User

class UserKey(CommonMixin, BASE):
    """User key used to access the API"""

    __tablename__ = 'user_keys'

    user_id = Column(
        Integer, ForeignKey('users.id'), index=True, nullable=False)
    key_id = Column(String, index=True, nullable=False)
    key_secret = Column(String, nullable=False)
    created = Column(
        DateTime(timezone=False), server_default=func.now(), nullable=False)
    last_used = Column(DateTime(timezone=False), server_default=func.now(),
                       onupdate=func.now(), nullable=False)
    desc = Column(String)

    # relationships
    user_rel = relationship(
        'User', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def user(self):
        """Defines the user attribute pointing to user's login"""
        return self.user_rel.login

    @user.setter
    def user(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = User.query.filter_by(login=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'user', User, 'login', value)
        self.user_id = match.id

    @user.expression
    def user(cls):
        """Expression used for performing queries"""
        return User.login

    # constraints
    __table_args__ = (UniqueConstraint(user_id, key_id),)

    def __repr__(self):
        """Object representation"""
        return "<UserKey(id='{}')>".format(self.key_id)
    # __repr__()

# UserKey

class Project(CommonMixin, BASE):
    """Projects which users belong to"""

    __tablename__ = 'projects'

    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)
    avatar = Column(LargeBinary)

    def __repr__(self):
        """Object representation"""
        return "<Project(name='{}')>".format(self.name)
    # __repr__()
# Project

class Role(CommonMixin, BASE):
    """A user role"""

    __tablename__ = 'roles'

    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<Role(name='{}')>".format(self.name)
    # __repr__()
# Role

class UserRole(CommonMixin, BASE):
    """A role for a user on a project"""

    __tablename__ = 'user_roles'

    user_id = Column(
        Integer, ForeignKey('users.id'), index=True, nullable=False)
    role_id = Column(
        Integer, ForeignKey('roles.id'), index=True, nullable=False)
    project_id = Column(
        Integer, ForeignKey('projects.id'), index=True, nullable=False)

    __table_args__ = (UniqueConstraint(user_id, role_id, project_id),)

    # user relationship
    user_rel = relationship(
        'User', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def user(self):
        """Defines the user attribute pointing to user's login"""
        return self.user_rel.login

    @user.setter
    def user(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = User.query.filter_by(login=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'user', User, 'login', value)
        self.user_id = match.id

    @user.expression
    def user(cls):
        """Expression used for performing queries"""
        return User.login

    # role relationship
    role_rel = relationship(
        'Role', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def role(self):
        """Defines the role attribute pointing to role's name"""
        return self.role_rel.name

    @role.setter
    def role(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = Role.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'role', Role, 'name', value)
        self.role_id = match.id

    @role.expression
    def role(cls):
        """Expression used for performing queries"""
        return Role.name

    # project relationship
    project_rel = relationship(
        'Project', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def project(self):
        """Defines the project attribute pointing to project's name"""
        return self.project_rel.name

    @project.setter
    def project(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = Project.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'project', Project, 'name', value)
        self.project_id = match.id

    @project.expression
    def project(cls):
        """Expression used for performing queries"""
        return Project.name

    def __repr__(self):
        """Object representation"""
        return "<UserRole(user='{}', role='{}', project='{}')>".format(
            self.user, self.role, self.project)
    # __repr__()
# UserRole

class RoleAction(CommonMixin, BASE):
    """An action on a resource type associated to a role"""

    __tablename__ = 'role_actions'

    role_id = Column(
        Integer, ForeignKey('roles.id'), index=True, nullable=False)
    resource = Column(String, nullable=False)
    action = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint(role_id, resource, action),
    )

    # role relationship
    role_rel = relationship(
        'Role', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def role(self):
        """Defines the role attribute pointing to role's name"""
        return self.role_rel.name

    @role.setter
    def role(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = Role.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'role', Role, 'name', value)
        self.role_id = match.id

    @role.expression
    def role(cls):
        """Expression used for performing queries"""
        return Role.name

    def __repr__(self):
        """Object representation"""
        return "<RoleAction(id='{}')>".format(self.id)
    # __repr__()
# RoleAction

class ResourceMixin(object):
    """
    Mixin to provide common attributes to resource entities
    """
    @declared_attr
    def owner_id(self):
        """Adds the owner_id column to table"""
        return Column(Integer, ForeignKey('users.id'), index=True,
                      nullable=False)

    @declared_attr
    def project_id(self):
        """Adds the project_id column to table"""
        return Column(Integer, ForeignKey('projects.id'), index=True,
                      nullable=False)

    @declared_attr
    def modifier_id(self):
        """Adds the modifier_id column to table"""
        return Column(Integer, ForeignKey('users.id'), index=True,
                      nullable=False)

    @declared_attr
    def modified(self):
        """Adds the modifier column to table"""
        return Column(DateTime(timezone=False),
                      server_default=func.now(),
                      onupdate=func.now(),
                      nullable=False)

    @declared_attr
    def desc(self):
        """Adds the desc column to table"""
        return Column(String)

    # modifier relationship section
    @declared_attr
    def modifier_rel(self):
        """Defines a relationship with the user object"""
        # primaryjoin is used to avoid ambiguity
        return relationship(
            'User', uselist=False, lazy='joined', innerjoin=True,
            primaryjoin=lambda: self.modifier_id == User.id)

    @hybrid_property
    def modifier(self):
        """Defines the modifier attribute pointing to modifier's login"""
        return self.modifier_rel.login

    @modifier.setter
    def modifier(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = User.query.filter_by(login=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'modifier', User, 'login', value)
        self.modifier_id = match.id

    @modifier.expression
    def modifier(cls):
        """Expression used for performing queries"""
        return User.login

    # owner relationship section
    @declared_attr
    def owner_rel(self):
        """Defines a relationship to attach the user object"""
        return relationship(
            'User', uselist=False, lazy='joined', innerjoin=True,
            primaryjoin=lambda: self.owner_id == User.id)
    @hybrid_property
    def owner(self):
        """Defines the owner attribute pointing to owner's login"""
        return self.owner_rel.login

    @owner.setter
    def owner(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = User.query.filter_by(login=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'owner', User, 'login', value)
        self.owner_id = match.id

    @owner.expression
    def owner(cls):
        """Expression used for performing queries"""
        return User.login

    # project relationship section
    @declared_attr
    def project_rel(self):
        """Defines a relationship to attach the project object"""
        return relationship(
            'Project', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def project(self):
        """Defines the project attribute pointing to project's name"""
        return self.project_rel.name

    @project.setter
    def project(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = Project.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'project', Project, 'name', value)
        self.project_id = match.id

    @project.expression
    def project(cls):
        """Expression used for performing queries"""
        return Project.name
# ResourceMixin

class NetZone(CommonMixin, ResourceMixin, BASE):
    """A network zone containing subnets"""

    __tablename__ = 'net_zones'

    name = Column(String, unique=True, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<NetZone(name='{}')>".format(self.name)
    # __repr__()
# NetZone

class Subnet(CommonMixin, ResourceMixin, BASE):
    """A subnet part of a network zone"""

    __tablename__ = 'subnets'

    name = Column(String, unique=True, nullable=False)
    zone_id = Column(
        Integer, ForeignKey('net_zones.id'), index=True, nullable=False)
    address = Column(postgresql.CIDR, nullable=False)
    gateway = Column(postgresql.INET)
    dns_1 = Column(postgresql.INET)
    dns_2 = Column(postgresql.INET)
    vlan = Column(Integer)

    # relationships
    zone_rel = relationship(
        'NetZone', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def zone(self):
        """Defines the zone attribute pointing to network zone's name"""
        return self.zone_rel.name

    @zone.setter
    def zone(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = NetZone.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'zone', NetZone, 'name', value)
        self.zone_id = match.id

    @zone.expression
    def zone(cls):
        """Expression used for performing queries"""
        return NetZone.name

    def __repr__(self):
        """Object representation"""
        return "<Subnet(name='{}', zone='{}')>".format(self.name, self.zone)
    # __repr__()

    @validates('address', 'gateway', 'dns_1', 'dns_2')
    def validate_ip(self, key, value):
        """
        Verify if ip addresses/networks are in correct format.

        Args:
            key (str): field name
            value (any): field's value

        Raises:
            ValueError: in case field's value is invalid

        Returns:
            str: field's value to populate row
        """
        if value is None:
            return
        try:
            if key == 'address':
                address_obj = ipaddress.ip_network(value, strict=True)
            else:
                address_obj = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("<({})=({})> ({})".format(key, value, str(exc)))

        # conversion to str normalizes different mask formats used
        return str(address_obj)
    # validate_ip()

# Subnet

class IpAddress(CommonMixin, ResourceMixin, BASE):
    """An ip address for use by a system"""

    __tablename__ = 'ip_addresses'

    subnet_id = Column(
        Integer, ForeignKey('subnets.id'), index=True, nullable=False)
    address = Column(postgresql.INET, nullable=False)

    __table_args__ = (UniqueConstraint(subnet_id, address),)

    # relationships
    subnet_rel = relationship(
        'Subnet', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def subnet(self):
        """Defines the subnet attribute pointing to subnet's name"""
        return self.subnet_rel.name

    @subnet.setter
    def subnet(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = Subnet.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'subnet', Subnet, 'name', value)
        self.subnet_id = match.id

    @subnet.expression
    def subnet(cls):
        """Expression used for performing queries"""
        return Subnet.name

    def __repr__(self):
        """Object representation"""
        return "<IpAddress(name='{}')>".format(self.address)
    # __repr__()
# IpAddress

class IfaceType(CommonMixin, BASE):
    """A type of system network interface supported by the application"""

    __tablename__ = 'iface_types'

    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<IfaceType(name='{}')>".format(self.name)
    # __repr__()
# IfaceType

class SystemArch(CommonMixin, BASE):
    """A type of system architecture supported by the application"""

    __tablename__ = 'system_archs'

    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<SystemArch(name='{}')>".format(self.name)
    # __repr__()
# SystemArch

class SystemType(CommonMixin, BASE):
    """A type of system supported by the application"""

    __tablename__ = 'system_types'

    name = Column(String, unique=True, nullable=False)
    arch_id = Column(
        Integer, ForeignKey('system_archs.id'), index=True, nullable=False)
    desc = Column(String, nullable=False)

    # relationships
    arch_rel = relationship(
        'SystemArch', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def arch(self):
        """Defines the arch attribute pointing to arch's name"""
        return self.arch_rel.name

    @arch.setter
    def arch(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = SystemArch.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'arch', SystemArch, 'name', value)
        self.arch_id = match.id

    @arch.expression
    def arch(cls):
        """Expression used for performing queries"""
        return SystemArch.name

    def __repr__(self):
        """Object representation"""
        return "<SystemType(name='{}')>".format(self.name)
    # __repr__()
# SystemType

class SystemModel(CommonMixin, BASE):
    """A description of a system model"""

    __tablename__ = 'system_models'

    name = Column(String, unique=True, nullable=False)
    arch_id = Column(
        Integer, ForeignKey('system_archs.id'), index=True, nullable=False)
    model = Column(String, nullable=False)
    submodel = Column(String)
    desc = Column(String)

    # relationships
    arch_rel = relationship(
        'SystemArch', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def arch(self):
        """Defines the arch attribute pointing to arch's name"""
        return self.arch_rel.name

    @arch.setter
    def arch(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = SystemArch.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'arch', SystemArch, 'name', value)
        self.arch_id = match.id

    @arch.expression
    def arch(cls):
        """Expression used for performing queries"""
        return SystemArch.name

    def __repr__(self):
        """Object representation"""
        return "<SystemModel(name='{}')>".format(self.name)
    # __repr__()
# SystemModel

class SystemState(CommonMixin, BASE):
    """An allowed system state"""

    __tablename__ = 'system_states'

    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<SystemState(name='{}')>".format(self.name)
    # __repr__()
# SystemState

class System(CommonMixin, ResourceMixin, BASE):
    """Represents a system which can provisioned, rebooted, etc."""

    __tablename__ = 'systems'

    name = Column(String, unique=True, nullable=False)
    hostname = Column(String, nullable=False)
    type_id = Column(
        Integer, ForeignKey('system_types.id'), index=True, nullable=False)
    model_id = Column(
        Integer, ForeignKey('system_models.id'), index=True, nullable=False)
    hypervisor_id = Column(Integer, ForeignKey('systems.id'), index=True)
    state_id = Column(Integer, ForeignKey('system_states.id'), nullable=False)

    # model relationship section
    model_rel = relationship(
        'SystemModel', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def model(self):
        """Defines the model attribute pointing to model's name"""
        return self.model_rel.name

    @model.setter
    def model(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = SystemModel.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'model', SystemModel, 'name', value)
        self.model_id = match.id

    @model.expression
    def model(cls):
        """Expression used for performing queries"""
        return SystemModel.name

    # hypervisor relationship section
    hypervisor_rel = relationship(
        'System', uselist=False, remote_side='System.id')

    @hybrid_property
    def hypervisor(self):
        """Defines the hypervisor attribute pointing to system's name"""
        if self.hypervisor_rel is None:
            return None
        return self.hypervisor_rel.name

    @hypervisor.setter
    def hypervisor(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        if value == '' or value is None:
            self.hypervisor_id = None
            return
        match = System.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'hypervisor', System, 'name', value)
        self.hypervisor_id = match.id

    @hypervisor.expression
    def hypervisor(cls):
        """
        It's not possible to express the appropriate joined query here so we
        just return None in order to force an error and make the devel aware
        that the manual join is needed. See the corresponding unit test for an
        example of how to construct the join.
        """
        return None

    # system state relationship section
    state_rel = relationship(
        'SystemState', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def state(self):
        """Defines the state attribute pointing to system state's name"""
        return self.state_rel.name

    @state.setter
    def state(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = SystemState.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'state', SystemState, 'name', value)
        self.state_id = match.id

    @state.expression
    def state(cls):
        """Expression used for performing queries"""
        return SystemState.name

    # system type relationship section
    type_rel = relationship(
        'SystemType', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def type(self):
        """Defines the type attribute pointing to system type's name"""
        return self.type_rel.name

    @type.setter
    def type(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = SystemType.query.filter_by(name=value.upper()).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'type', SystemType, 'name', value)
        self.type_id = match.id

    @type.expression
    def type(cls):
        """Expression used for performing queries"""
        return SystemType.name

    def __repr__(self):
        """Object representation"""
        return "<System(name='{}')>".format(self.name)
    # __repr__()
# System

class OperatingSystem(CommonMixin, BASE):
    """A supported operating system"""

    __tablename__ = 'operating_systems'

    name = Column(String, unique=True, nullable=False)
    major = Column(String, nullable=False)
    minor = Column(String)
    desc = Column(String)

    def __repr__(self):
        """Object representation"""
        return "<OperatingSystem(name='{}', major='{}', minor='{}')>".format(
            self.name, self.major, self.minor)
    # __repr__()

# OperatingSystem

class SystemProfile(CommonMixin, BASE):
    """A system activation profile"""

    __tablename__ = 'system_profiles'

    name = Column(String, index=True, nullable=False)
    hypervisor_profile_id = Column(
        Integer, ForeignKey('system_profiles.id'), index=True)
    system_id = Column(
        Integer, ForeignKey('systems.id'), index=True, nullable=False)
    operating_system_id = Column(Integer, ForeignKey('operating_systems.id'))
    default = Column(Boolean, nullable=False)
    cpu = Column(Integer)
    memory = Column(BigInteger)
    parameters = Column(postgresql.JSONB)
    credentials = Column(postgresql.JSONB)

    __table_args__ = (UniqueConstraint(name, system_id),)

    # hypervisor profile relationship section
    hypervisor_profile_rel = relationship(
        'SystemProfile', uselist=False, remote_side='SystemProfile.id')

    @hybrid_property
    def hypervisor_profile(self):
        """Defines the profile attribute as system_name/profile_name"""
        if self.hypervisor_profile_rel is None:
            return None
        return '{}/{}'.format(
            self.hypervisor_profile_rel.system,
            self.hypervisor_profile_rel.name)

    @hypervisor_profile.setter
    def hypervisor_profile(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        if value == '' or value is None:
            self.hypervisor_profile_id = None
            return
        try:
            system_name, profile_name = value.split('/', 1)
        except ValueError:
            raise AssociationError(
                self.__class__, 'hypervisor_profile',
                SystemProfile, 'name', value)

        match = SystemProfile.query.join(
            System, SystemProfile.system_id == System.id
        ).filter(
            System.name == system_name
        ).filter(
            SystemProfile.name == profile_name
        ).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'hypervisor_profile', SystemProfile,
                'name', value)
        self.hypervisor_profile_id = match.id

    @hypervisor_profile.expression
    def hypervisor_profile(cls):
        """
        It's not possible to express the appropriate joined query here so we
        just return None in order to force an error and make the devel aware
        that the manual join is needed. See the corresponding unit test for an
        example of how to construct the join.
        """
        return None

    # storage volume relationship section
    storage_volumes_rel = relationship(
        'StorageVolume', uselist=True, secondary='profiles_storage_volumes')

    # system iface relationship section
    system_ifaces_rel = relationship(
        'SystemIface', uselist=True, secondary='profiles_system_ifaces')

    # system relationship section
    system_rel = relationship(
        'System', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def system(self):
        """Defines the system attribute pointing to system's name"""
        return self.system_rel.name

    @system.setter
    def system(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = System.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'system', System, 'name', value)
        self.system_id = match.id

    @system.expression
    def system(cls):
        """Expression used for performing query joins"""
        return System.name

    # os relationship section
    operating_system_rel = relationship('OperatingSystem', uselist=False)

    @hybrid_property
    def operating_system(self):
        """Defines the operating system attribute pointing to os name"""
        if self.operating_system_rel is None:
            return None
        return self.operating_system_rel.name

    @operating_system.setter
    def operating_system(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        if value == '' or value is None:
            self.operating_system_id = None
            return
        match = OperatingSystem.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'operating_system',
                OperatingSystem, 'name', value)
        self.operating_system_id = match.id

    @operating_system.expression
    def operating_system(cls):
        """Expression used for performing query joins"""
        return OperatingSystem.name

    def __repr__(self):
        """Object representation"""
        return "<SystemProfile(name='{}'>".format(self.name)
    # __repr__()
# SystemProfile

class SystemIfaceProfileAssociation(BASE):
    """Represents a system iface associated with a system activation profile"""

    __tablename__ = 'profiles_system_ifaces'

    profile_id = Column(
        Integer, ForeignKey('system_profiles.id'), primary_key=True)
    iface_id = Column(
        Integer, ForeignKey('system_ifaces.id'), primary_key=True)

    __table_args__ = (UniqueConstraint(profile_id, iface_id),)

    # profile relationship section
    profile_rel = relationship(
        'SystemProfile', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def profile(self):
        """Defines the profile attribute as system_name/profile_name"""
        return '{}/{}'.format(
            self.profile_rel.system, self.profile_rel.name)

    @profile.setter
    def profile(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        try:
            system_name, profile_name = value.split('/', 1)
        except ValueError:
            raise AssociationError(
                self.__class__, 'profile', SystemProfile, 'name', value)

        match = SystemProfile.query.join(
            System, SystemProfile.system_id == System.id
        ).filter(
            System.name == system_name
        ).filter(
            SystemProfile.name == profile_name
        ).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'profile', SystemProfile, 'name', value)
        self.profile_id = match.id

    @profile.expression
    def profile(cls):
        """Expression used for performing queries"""
        return SystemProfile.name

    # iface relationship section
    iface_rel = relationship(
        'SystemIface', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def iface(self):
        """Defines the iface attribute as system/name"""
        return '{}/{}'.format(
            self.iface_rel.system, self.iface_rel.name)

    @iface.setter
    def iface(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        try:
            system_name, iface_name = value.split('/', 1)
        except ValueError:
            raise AssociationError(
                self.__class__, 'iface', SystemIface, 'name', value)

        match = SystemIface.query.join(
            System, SystemIface.system_id == System.id
        ).filter(
            System.name == system_name
        ).filter(
            SystemIface.name == iface_name
        ).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'iface', SystemIface, 'name', value)
        self.iface_id = match.id

    @iface.expression
    def iface(cls):
        """Expression used for performing queries"""
        return SystemIface.name

    def __repr__(self):
        """Object representation"""
        return ("<SystemIfaceProfileAssociation(profile_id='{}', "
                "iface_id='{}')>".format(self.profile_id, self.iface_id))
    # __repr__()
# SystemIfaceProfileAssociation

class SystemIface(CommonMixin, BASE):
    """Represents a network interface associated to a system"""

    __tablename__ = 'system_ifaces'

    name = Column(String, nullable=False)
    osname = Column(String)
    ip_address_id = Column(Integer, ForeignKey('ip_addresses.id'))
    system_id = Column(
        Integer, ForeignKey('systems.id'), index=True, nullable=False)

    type_id = Column(Integer, ForeignKey('iface_types.id'), nullable=False)
    attributes = Column(postgresql.JSONB)
    mac_address = Column(postgresql.MACADDR)
    desc = Column(String)

    @declared_attr
    def __table_args__(self):
        return (UniqueConstraint(self.name, self.system_id),)

    # profiles relationship section
    profiles_rel = relationship(
        'SystemProfile',
        uselist=True,
        # This is important: prevents sqlalchemy from issuing a delete to
        # the associated entry in the other table
        passive_deletes='all',
        secondary='profiles_system_ifaces')

    # ip_address relationship section
    ip_address_rel = relationship('IpAddress', uselist=False)

    @hybrid_property
    def ip_address(self):
        """Defines the ip_address attribute as subnet_name/ip_address"""
        if self.ip_address_rel is None:
            return None
        return '{}/{}'.format(
            self.ip_address_rel.subnet, self.ip_address_rel.address)

    @ip_address.setter
    def ip_address(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        if value == '' or value is None:
            self.ip_address_id = None
            return
        try:
            subnet_name, ip_address = value.split('/', 1)
        except ValueError:
            raise AssociationError(
                self.__class__, 'ip_address', IpAddress, 'address', value)

        match = IpAddress.query.join(
            Subnet, IpAddress.subnet_id == Subnet.id
        ).filter(
            Subnet.name == subnet_name
        ).filter(
            IpAddress.address == ip_address
        ).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'ip_address', IpAddress, 'address', value)
        self.ip_address_id = match.id

    @ip_address.expression
    def ip_address(cls):
        """Expression used for performing queries"""
        return IpAddress.address

    # iface type relationship section
    type_rel = relationship(
        'IfaceType', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def type(self):
        """Defines the type attribute pointing to iface type's name"""
        return self.type_rel.name

    @type.setter
    def type(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = IfaceType.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'type', IfaceType, 'name', value)
        self.type_id = match.id

    @type.expression
    def type(cls):
        """Expression used for performing queries"""
        return IfaceType.name

    # system relationship section
    system_rel = relationship(
        'System', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def system(self):
        """Defines the system attribute pointing to system's name"""
        return self.system_rel.name

    @system.setter
    def system(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = System.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'system', System, 'name', value)
        self.system_id = match.id

    @system.expression
    def system(cls):
        """Expression used for performing query joins"""
        return System.name

    def __repr__(self):
        """Object representation"""
        return "<SystemIface(name='{}', system='{}')>".format(
            self.name, self.system)
    # __repr__()

# SystemIface

class StorageServerType(CommonMixin, BASE):
    """A type of storage server supported by the application"""

    __tablename__ = 'storage_server_types'

    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<StorageServerType(name='{}')>".format(self.name)
    # __repr__()
# StorageServerType

class StorageServer(CommonMixin, ResourceMixin, BASE):
    """Represents a storage server to which volumes are associated"""

    __tablename__ = 'storage_servers'

    name = Column(String, unique=True, nullable=False)
    hostname = Column(String)
    type_id = Column(
        Integer, ForeignKey('storage_server_types.id'), nullable=False)
    model = Column(String, nullable=False)
    fw_level = Column(String)
    username = Column(String)
    password = Column(String)
    attributes = Column(postgresql.JSONB)

    # relationships
    type_rel = relationship(
        'StorageServerType', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def type(self):
        """Defines the type attribute pointing to server type's name"""
        return self.type_rel.name

    @type.setter
    def type(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = StorageServerType.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'type', StorageServerType, 'name', value)
        self.type_id = match.id

    @type.expression
    def type(cls):
        """Expression used for performing queries"""
        return StorageServerType.name

    def __repr__(self):
        """Object representation"""
        return "<StorageServer(id='{}')>".format(self.name)
    # __repr__()

# StorageServer

class StoragePoolType(CommonMixin, BASE):
    """A type of storage pool"""

    __tablename__ = 'storage_pool_types'

    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<StoragePoolType(name='{}')>".format(self.name)
    # __repr__()

# StoragePoolType

class StoragePool(CommonMixin, ResourceMixin, BASE):
    """
    A storage pool containing storage volumes and providing logical volumes
    """

    __tablename__ = 'storage_pools'

    name = Column(String, unique=True, nullable=False)
    system_id = Column(Integer, ForeignKey('systems.id'), index=True)
    type_id = Column(
        Integer, ForeignKey('storage_pool_types.id'), nullable=False)
    total_size = Column(BigInteger)
    used_size = Column(BigInteger)
    attributes = Column(postgresql.JSONB)

    # pool type relationship section
    type_rel = relationship(
        'StoragePoolType', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def type(self):
        """Defines the type attribute pointing to pool type's name"""
        return self.type_rel.name

    @type.setter
    def type(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = StoragePoolType.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'type', StoragePoolType, 'name', value)
        self.type_id = match.id

    @type.expression
    def type(cls):
        """Expression used for performing queries"""
        return StoragePoolType.name

    # system relationship section
    system_rel = relationship('System', uselist=False)

    @hybrid_property
    def system(self):
        """Defines the system attribute pointing to system's name"""
        if self.system_rel is None:
            return None
        return self.system_rel.name

    @system.setter
    def system(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        if value == '' or value is None:
            self.system_id = None
            return
        match = System.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'system', System, 'name', value)
        self.system_id = match.id

    @system.expression
    def system(cls):
        """Expression used for performing query joins"""
        return System.name

    def __repr__(self):
        """Object representation"""
        return "<StoragePool(name='{}')>".format(self.name)
    # __repr__()
# StoragePool

class VolumeType(CommonMixin, BASE):
    """A type of volume supported by the application"""

    __tablename__ = 'volume_types'

    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<VolumeType(name='{}')>".format(self.name)
    # __repr__()

# VolumeType

class StorageVolumeProfileAssociation(BASE):
    """
    Represents a storage volume associated with a system activation profile
    """

    __tablename__ = 'profiles_storage_volumes'

    profile_id = Column(
        Integer, ForeignKey('system_profiles.id'), primary_key=True)
    volume_id = Column(
        Integer, ForeignKey('storage_volumes.id'), primary_key=True)

    __table_args__ = (UniqueConstraint(profile_id, volume_id),)

    # profile relationship section
    profile_rel = relationship(
        'SystemProfile', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def profile(self):
        """Defines the profile attribute as system_name/profile_name"""
        return '{}/{}'.format(
            self.profile_rel.system, self.profile_rel.name)

    @profile.setter
    def profile(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        try:
            system_name, profile_name = value.split('/', 1)
        except ValueError:
            raise AssociationError(
                self.__class__, 'profile', SystemProfile, 'name', value)

        match = SystemProfile.query.join(
            System, SystemProfile.system_id == System.id
        ).filter(
            System.name == system_name
        ).filter(
            SystemProfile.name == profile_name
        ).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'profile', SystemProfile, 'name', value)
        self.profile_id = match.id

    @profile.expression
    def profile(cls):
        """Expression used for performing queries"""
        return SystemProfile.name

    # volume relationship section
    volume_rel = relationship(
        'StorageVolume', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def volume(self):
        """Defines the volume attribute as storage_server/volume_id"""
        return '{}/{}'.format(
            self.volume_rel.server, self.volume_rel.volume_id)

    @volume.setter
    def volume(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        try:
            server_name, volume_id = value.split('/', 1)
        except ValueError:
            raise AssociationError(
                self.__class__, 'volume', StorageVolume, 'volume_id', value)

        match = StorageVolume.query.join(
            StorageServer, StorageVolume.server_id == StorageServer.id
        ).filter(
            StorageServer.name == server_name
        ).filter(
            StorageVolume.volume_id == volume_id
        ).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'volume', StorageVolume, 'volume_id', value)
        self.volume_id = match.id

    @volume.expression
    def volume(cls):
        """Expression used for performing queries"""
        return StorageVolume.volume_id

    def __repr__(self):
        """Object representation"""
        return (
            "<StorageVolumeProfileAssociation(volume_id='{}', "
            "profile_id='{}')>".format(self.volume_id, self.profile_id)
        )
    # __repr__()

# StorageVolumeProfileAssociation

class StorageVolume(CommonMixin, ResourceMixin, SchemaMixin, BASE):
    """A volume from a storage server"""

    __tablename__ = 'storage_volumes'

    volume_id = Column(String, nullable=False)
    server_id = Column(
        Integer, ForeignKey('storage_servers.id'), index=True, nullable=False)
    system_id = Column(Integer, ForeignKey('systems.id'), index=True)
    type_id = Column(Integer, ForeignKey('volume_types.id'), nullable=False)
    pool_id = Column(Integer, ForeignKey('storage_pools.id'), index=True)
    size = Column(BigInteger, nullable=False)
    part_table = Column(postgresql.JSONB)
    specs = Column(postgresql.JSONB)
    system_attributes = Column(postgresql.JSONB)

    __table_args__ = (UniqueConstraint(volume_id, server_id),)

    # profiles relationship section
    profiles_rel = relationship(
        'SystemProfile',
        uselist=True,
        # This is important: prevents sqlalchemy from issuing a delete to
        # the associated entry in the other table
        passive_deletes='all',
        secondary='profiles_storage_volumes')

    # type relationship section
    type_rel = relationship(
        'VolumeType', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def type(self):
        """Defines the type attribute pointing to volume type's name"""
        return self.type_rel.name

    @type.setter
    def type(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = VolumeType.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'type', VolumeType, 'name', value)
        self.type_id = match.id

    @type.expression
    def type(cls):
        """Expression used for performing queries"""
        return VolumeType.name

    # server relationship section
    server_rel = relationship(
        'StorageServer', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def server(self):
        """Defines the server attribute pointing to server's name"""
        return self.server_rel.name

    @server.setter
    def server(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = StorageServer.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'server', StorageServer, 'name', value)
        self.server_id = match.id

    @server.expression
    def server(cls):
        """Expression used for performing queries"""
        return StorageServer.name

    # system relationship section
    system_rel = relationship('System', uselist=False)

    @hybrid_property
    def system(self):
        """Defines the system attribute pointing to system's name"""
        if self.system_rel is None:
            return None
        return self.system_rel.name

    @system.setter
    def system(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        if value == '' or value is None:
            self.system_id = None
            return
        match = System.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'system', System, 'name', value)
        self.system_id = match.id

    @system.expression
    def system(cls):
        """Expression used for performing query joins"""
        return System.name

    # pool relationship section
    pool_rel = relationship('StoragePool', uselist=False)

    @hybrid_property
    def pool(self):
        """Defines the pool attribute pointing to pool's name"""
        if self.pool_rel is None:
            return None
        return self.pool_rel.name

    @pool.setter
    def pool(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        if value == '' or value is None:
            self.pool_id = None
            return
        match = StoragePool.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'pool', StoragePool, 'name', value)
        self.pool_id = match.id

    @pool.expression
    def pool(cls):
        """Expression used for performing queries"""
        return StoragePool.name

    def __repr__(self):
        """Object representation"""
        return "<StorageVolume(volume_id='{}', server='{}')>".format(
            self.volume_id, self.server)
    # __repr__()

# StorageVolume

class LogicalVolumeProfileAssociation(BASE):
    """
    Represents a logical volume associated with a system activation profile
    """

    __tablename__ = 'profiles_logical_volumes'

    profile_id = Column(
        Integer, ForeignKey('system_profiles.id'), primary_key=True)
    volume_id = Column(
        Integer, ForeignKey('logical_volumes.id'), primary_key=True)

    __table_args__ = (UniqueConstraint(profile_id, volume_id),)

    # profile relationship section
    profile_rel = relationship(
        'SystemProfile', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def profile(self):
        """Defines the profile attribute as system_name/profile_name"""
        return '{}/{}'.format(
            self.profile_rel.system, self.profile_rel.name)

    @profile.setter
    def profile(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        try:
            system_name, profile_name = value.split('/', 1)
        except ValueError:
            raise AssociationError(
                self.__class__, 'profile', SystemProfile, 'name', value)

        match = SystemProfile.query.join(
            System, SystemProfile.system_id == System.id
        ).filter(
            System.name == system_name
        ).filter(
            SystemProfile.name == profile_name
        ).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'profile', SystemProfile, 'name', value)
        self.profile_id = match.id

    @profile.expression
    def profile(cls):
        """Expression used for performing queries"""
        return SystemProfile.name

    # volume relationship section
    volume_rel = relationship(
        'LogicalVolume', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def volume(self):
        """Defines the volume attribute as pool_name/volume_id"""
        return '{}/{}'.format(
            self.volume_rel.pool, self.volume_rel.name)

    @volume.setter
    def volume(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        try:
            pool_name, volume_name = value.split('/', 1)
        except ValueError:
            raise AssociationError(
                self.__class__, 'volume', LogicalVolume, 'name', value)

        match = LogicalVolume.query.join(
            StoragePool, LogicalVolume.pool_id == StoragePool.id
        ).filter(
            StoragePool.name == pool_name
        ).filter(
            LogicalVolume.name == volume_name
        ).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'volume', LogicalVolume, 'name', value)
        self.volume_id = match.id

    @volume.expression
    def volume(cls):
        """Expression used for performing queries"""
        return LogicalVolume.name

    def __repr__(self):
        """Object representation"""
        return (
            "<LogicalVolumeProfileAssociation(volume_id='{}', "
            "profile_id='{}')>".format(self.volume_id, self.profile_id)
        )
    # __repr__()
# LogicalVolumeProfileAssociation

class LogicalVolume(CommonMixin, ResourceMixin, BASE):
    """A volume from a storage pool"""

    __tablename__ = 'logical_volumes'

    name = Column(String, nullable=False)
    system_id = Column(Integer, ForeignKey('systems.id'), index=True)
    type_id = Column(Integer, ForeignKey('volume_types.id'), nullable=False)
    pool_id = Column(
        Integer, ForeignKey('storage_pools.id'), index=True, nullable=False)
    size = Column(BigInteger, nullable=False)
    part_table = Column(postgresql.JSONB)
    specs = Column(postgresql.JSONB)
    system_attributes = Column(postgresql.JSONB)

    __table_args__ = (
        UniqueConstraint(name, pool_id),
        UniqueConstraint(name, system_id)
    )

    # profiles relationship section
    profiles_rel = relationship(
        'SystemProfile',
        uselist=True,
        # This is important: prevents sqlalchemy from issuing a delete to
        # the associated entry in the other table
        passive_deletes='all',
        secondary='profiles_logical_volumes')

    # type relationship section
    type_rel = relationship(
        'VolumeType', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def type(self):
        """Defines the type attribute pointing to volume type's name"""
        return self.type_rel.name

    @type.setter
    def type(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = VolumeType.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'type', VolumeType, 'name', value)
        self.type_id = match.id

    @type.expression
    def type(cls):
        """Expression used for performing queries"""
        return VolumeType.name

    # system relationship section
    system_rel = relationship('System', uselist=False)

    @hybrid_property
    def system(self):
        """Defines the system attribute pointing to system's name"""
        if self.system_rel is None:
            return None
        return self.system_rel.name

    @system.setter
    def system(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        if value == '' or value is None:
            self.system_id = None
            return
        match = System.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'system', System, 'name', value)
        self.system_id = match.id

    @system.expression
    def system(cls):
        """Expression used for performing query joins"""
        return System.name

    # pool relationship section
    pool_rel = relationship(
        'StoragePool', uselist=False, lazy='joined', innerjoin=True)

    @hybrid_property
    def pool(self):
        """Defines the pool attribute pointing to pool's name"""
        return self.pool_rel.name

    @pool.setter
    def pool(self, value):
        """Defines what to do when assigment occurs for the attribute"""
        match = StoragePool.query.filter_by(name=value).one_or_none()
        # related entry does not exist: report error
        if match is None:
            raise AssociationError(
                self.__class__, 'pool', StoragePool, 'name', value)
        self.pool_id = match.id

    @pool.expression
    def pool(cls):
        """Expression used for performing queries"""
        return StoragePool.name

    def __repr__(self):
        """Object representation"""
        return "<LogicalVolume(name='{}', pool='{}')>".format(
            self.name, self.pool_rel.name)
    # __repr__()

# LogicalVolume

class SchedulerRequest(CommonMixin, BASE):
    """A request submitted to the job scheduler"""

    __tablename__ = 'scheduler_requests'

    # define constants to be globally used
    ACTION_CANCEL = 'CANCEL'
    ACTION_SUBMIT = 'SUBMIT'
    # action types
    ACTIONS = (ACTION_CANCEL, ACTION_SUBMIT)
    SLOT_DEFAULT = 'DEFAULT'
    SLOT_NIGHT = 'NIGHT'
    # time slots
    SLOTS = (SLOT_DEFAULT, SLOT_NIGHT)
    STATE_COMPLETED = 'COMPLETED'
    STATE_FAILED = 'FAILED'
    STATE_PENDING = 'PENDING'
    # request states
    STATES = (STATE_COMPLETED, STATE_FAILED, STATE_PENDING)

    requester_id = Column(
        Integer, ForeignKey('users.id'), index=True, nullable=False)

    # user can create a new job, change existing one, cancel an enqueued job
    # state machine wrapper also submits a request to finish the job
    action_type = Column(String, nullable=False)

    # job is filled by scheduler when the requests is processed and job is
    # created
    job_id = Column(Integer, ForeignKey('scheduler_jobs.id'), index=True)

    # job type refers to the type of state machine to use
    job_type = Column(String, nullable=False)

    time_slot = Column(String, nullable=False, default='DEFAULT')

    # period in minutes after job is considered to have timed out
    timeout = Column(Integer, default=0, nullable=False)

    # the date when request was submitted
    submit_date = Column(DateTime(timezone=False), nullable=False)

    # the date when the requester wants the job to be started
    start_date = Column(DateTime(timezone=False))

    # parameters are passed to the state machine parser which returns to the
    # scheduler which resources are to be used
    parameters = Column(String, nullable=False)

    # priority defines order
    priority = Column(SmallInteger, nullable=False, default=0)

    # request state
    state = Column(String, nullable=False, default=STATE_PENDING)

    # messages about the request result
    result = Column(String, nullable=True)

    @validates(('action_type', 'time_slot', 'state'))
    def validate(self, key, value):
        """
        Simple validator
        """
        if key == 'action_type' and value not in self.ACTIONS:
            raise ValueError("Invalid action type '{}'".format(value))

        elif key == 'time_slot' and value not in self.SLOTS:
            raise ValueError("Invalid time slot type '{}'".format(value))

        elif key == 'state' and value not in self.STATES:
            raise ValueError("Invalid state '{}'".format(value))

        return value
    # validate_action_type()

# SchedulerRequest

class SchedulerJob(CommonMixin, BASE):
    """A scheduler request accepted for execution"""

    __tablename__ = 'scheduler_jobs'

    requester_id = Column(
        Integer, ForeignKey('users.id'), index=True, nullable=False)

    # priority defines order
    priority = Column(SmallInteger, nullable=False, default=0)

    # job type refers to the type of state machine to use
    job_type = Column(String, nullable=False)

    # default or nightslot
    time_slot = Column(String, nullable=False)

    state = Column(String, nullable=False)
    pid = Column(Integer)

    # opted for a json field instead of a denormalized table 'job_resources'
    # because of the following reasons:
    # - faster access to information in the same row instead of having to
    # query another table (which has a lot of rows) and build the dictionary
    # - avoid the need to delete old entries from the table (not really a big
    # issue since this have to be done for the requests and jobs table anyway)
    # the field has the format:
    # {'exclusive': [{'name': 'resource1', 'type': 'system'}],
    # 'shared': [{'name': 'resource2', 'type': 'system'}]}
    resources = Column(postgresql.JSONB)

    parameters = Column(String, nullable=False)

    # description is returned by the state machine parser
    description = Column(String, nullable=False)

    # submit date comes from the request
    submit_date = Column(DateTime(timezone=False), nullable=False)

    # filled by scheduler when state machine starts
    start_date = Column(DateTime(timezone=False))

    # filled by scheduler when state machine informs it has finished
    end_date = Column(DateTime(timezone=False))

    # messages about the job result
    result = Column(String)

    timeout = Column(Integer, default=0, nullable=False)

    # define constants to be globally used
    # time slots
    SLOT_DEFAULT = 'DEFAULT'
    SLOT_NIGHT = 'NIGHT'
    # time slots
    SLOTS = (SLOT_DEFAULT, SLOT_NIGHT)
    STATE_CANCELED = 'CANCELED'
    STATE_CLEANINGUP = 'CLEANINGUP'
    STATE_COMPLETED = 'COMPLETED'
    STATE_FAILED = 'FAILED'
    STATE_RUNNING = 'RUNNING'
    STATE_WAITING = 'WAITING'
    # jobs states
    STATES = (STATE_CANCELED, STATE_CLEANINGUP, STATE_COMPLETED, STATE_FAILED,
              STATE_RUNNING, STATE_WAITING)

    def __repr__(self):
        """Object representation"""
        return "<Job (id='{}')>".format(self.id)
    # __repr__()

    @validates(('time_slot', 'state'))
    def validate(self, key, value):
        """
        Simple validator
        """
        if key == 'time_slot' and value not in self.SLOTS:
            raise ValueError("Invalid time slot type '{}'".format(value))

        elif key == 'state' and value not in self.STATES:
            raise ValueError("Invalid state '{}'".format(value))

        return value
    # validate_action_type()

# SchedulerJob
