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
Unit test for the sqlalchemy models module
"""

#
# IMPORTS
#
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.sqlite.base import SQLiteDialect
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import aliased
from tessia_engine.db.exceptions import AssociationError
from tessia_engine.db import connection
from tessia_engine.db import models
from tessia_engine.db import types
from tessia_engine.db.feeder import db_insert

from unittest import TestCase
from unittest.mock import patch

import os
import json

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class DbUnit(object):
    """
    This is a helper class that can be used by other tests whenenver they need
    to create a test database instance from scratch.
    """
    SAMPLE_DATA = '{}/sample.json'.format(
        os.path.dirname(os.path.abspath(__file__)))

    _prepared = False

    @classmethod
    def _adapt_sqlite(cls):
        """
        Do some monkey patching to allow the sa's models to work in a sqlite
        database.
        """
        # pylint: disable=protected-access

        # the postgres dialect class defines this variable but it's always None
        # and falls back to json lib, so we can do the same in sqlite
        SQLiteDialect._json_serializer = None
        SQLiteDialect._json_deserializer = None

        # pylint: disable=unused-variable
        # alternate sql statements for postgres specific types
        @compiles(postgresql.JSONB, 'sqlite')
        def compile_jsonb_sqlite(*args, **kwargs):
            """Type for json objects"""
            return "VARCHAR"
        @compiles(postgresql.CIDR, 'sqlite')
        def compile_cidr_sqlite(*args, **kwargs):
            """Type for cidr addresses"""
            return "VARCHAR"
        @compiles(postgresql.INET, 'sqlite')
        def compile_inet_sqlite(*args, **kwargs):
            """Type for inet addresses"""
            return "VARCHAR"
        @compiles(postgresql.MACADDR, 'sqlite')
        def compile_macaddr_sqlite(*args, **kwargs):
            """Type for mac addresses"""
            return "VARCHAR"

        # sqlite does not like constraint naming with placeholders
        models.NAME_CONVENTION.pop('ck', None)

        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, *args, **kwargs):
            """Enable fk support"""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    # _adapt_sqlite()

    @classmethod
    def _prepare(cls):
        """
        Prepare the environment to work with the test database
        """
        db_url = os.environ.get('TESSIA_TEST_DB', 'sqlite://')
        if db_url.startswith('sqlite:'):
            cls._adapt_sqlite()
        cls._prepared = True
    # _prepare()

    @classmethod
    def _connect(cls):
        """
        Establishes a new connection to the database. If in-memory database is
        in use this means any existing database will be erased a new one will
        be created.
        """
        db_url = os.environ.get('TESSIA_TEST_DB', 'sqlite://')

        # create a mock config to point to our test db url
        patcher = patch.object(connection, 'CONF', autospec=True)
        mock_conf = patcher.start()
        conf = {'db': {'url': db_url}}
        mock_conf.get_config.return_value = conf

        # make sure it's a new connection and not one from a previous test
        connection.MANAGER._conn = None # pylint: disable=protected-access
        # session can be used by consumers
        cls.session = connection.MANAGER.session

        # mock config not needed anymore
        patcher.stop()

        # store the references to be used later
        cls._db_insert = db_insert
    # _connect()

    @classmethod
    def create_db(cls, empty=False):
        """
        Initialize the test database.
        """
        if not cls._prepared:
            cls._prepare()
        cls._connect()

        # create and pre-populate the database
        models.BASE.metadata.create_all(connection.MANAGER.engine)
        types.create_all()

        # empty flag specify: do not populate with sample data
        if empty:
            return

        sample_file = '{}/sample.json'.format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(sample_file, 'r') as sample_fd:
            data = sample_fd.read()
        cls.create_entry(json.loads(data))
    # create_db()

    @classmethod
    def create_entry(cls, data):
        """
        Add one or more entries to the test database
        """
        cls._db_insert(data)
    # create_entry()
# DbUnit

class TestModels(TestCase):
    """
    Unit test for the db.models module
    """

    @classmethod
    def setUpClass(cls):
        """
        Called once before any test in this test class run.
        """
        DbUnit.create_db()
        cls.models = models
    # setUpClass()

    def test_repr(self):
        """
        Make sure all model representations work

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
        for name in dir(self.models):
            model = getattr(self.models, name)
            if hasattr(model, 'query'):
                item = model.query.first()
                self.assertIsInstance(repr(item), str)
    # test_repr()

    def test_relations(self):
        """
        Make sure all model relationships work

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
        # create a map with all relations to be tested
        relation_map = {
            self.models.RoleAction: [
                {
                    # the relationship name in the model
                    'rel_name': 'role_rel',
                    # the field name in the model
                    'attr_name': 'role',
                    # the value of the field
                    'value': 'User',
                },
            ],
            self.models.UserRole: [
                {
                    # the relationship name in the model
                    'rel_name': 'user_rel',
                    # the field name in the model
                    'attr_name': 'user',
                    # the value of the field
                    'value': 'user_x_0@domain.com',
                },
                {
                    # the relationship name in the model
                    'rel_name': 'role_rel',
                    # the field name in the model
                    'attr_name': 'role',
                    # the value of the field
                    'value': 'User',
                },
                {
                    # the relationship name in the model
                    'rel_name': 'project_rel',
                    # the field name in the model
                    'attr_name': 'project',
                    # the value of the field
                    'value': 'Department x',
                },
            ],
            self.models.UserKey: [
                {
                    # the relationship name in the model
                    'rel_name': 'user_rel',
                    # the field name in the model
                    'attr_name': 'user',
                    # the value of the field
                    'value': 'user_x_0@domain.com',
                }
            ],
            self.models.NetZone: [
                {
                    'rel_name': 'modifier_rel',
                    'attr_name': 'modifier',
                    'value': 'user_x_0@domain.com',
                },
                {
                    'rel_name': 'owner_rel',
                    'attr_name': 'owner',
                    'value': 'user_x_0@domain.com',
                },
                {
                    'rel_name': 'project_rel',
                    'attr_name': 'project',
                    'value': 'Department x',
                },
            ],
            self.models.Subnet: [
                {
                    'rel_name': 'zone_rel',
                    'attr_name': 'zone',
                    'value': 'cpc0',
                },
            ],
            self.models.IpAddress: [
                {
                    'rel_name': 'subnet_rel',
                    'attr_name': 'subnet',
                    'value': 'cpc0 shared',
                },
            ],
            self.models.SystemType: [
                {
                    'rel_name': 'arch_rel',
                    'attr_name': 'arch',
                    'value': 's390x',
                },
            ],
            self.models.SystemModel: [
                {
                    'rel_name': 'arch_rel',
                    'attr_name': 'arch',
                    'value': 's390x',
                },
            ],
            self.models.System: [
                {
                    'rel_name': 'model_rel',
                    'attr_name': 'model',
                    'value': 'ZEC12_H20',
                },
                {
                    'rel_name': 'state_rel',
                    'attr_name': 'state',
                    'value': 'AVAILABLE',
                },
                {
                    'self': True,
                    'rel_name': 'hypervisor_rel',
                    'attr_name': 'hypervisor',
                    'value': 'cpc0',
                },
                {
                    'rel_name': 'type_rel',
                    'attr_name': 'type',
                    'value': 'CPC',
                },
            ],
            self.models.SystemProfile: [
                {
                    'self': True,
                    'rel_name': 'hypervisor_profile_rel',
                    'attr_name': 'hypervisor_profile',
                    'value': 'cpc0/default cpc0',
                },
                {
                    'rel_name': 'system_rel',
                    'attr_name': 'system',
                    'value': 'cpc0',
                },
                {
                    'rel_name': 'operating_system_rel',
                    'attr_name': 'operating_system',
                    'value': 'rhel7.0',
                },
            ],
            self.models.SystemIfaceProfileAssociation: [
                {
                    'rel_name': 'iface_rel',
                    'attr_name': 'iface',
                    'value': 'cpc0/external osa',
                },
                {
                    'rel_name': 'profile_rel',
                    'attr_name': 'profile',
                    'value': 'cpc0/default cpc0',
                },
            ],
            self.models.SystemIface: [
                {
                    'rel_name': 'ip_address_rel',
                    'attr_name': 'ip_address',
                    'value': 'cpc0 shared/10.1.0.4',
                },
                {
                    'rel_name': 'type_rel',
                    'attr_name': 'type',
                    'value': 'OSA',
                },
                {
                    'rel_name': 'system_rel',
                    'attr_name': 'system',
                    'value': 'cpc0',
                },
            ],
            self.models.StorageServer: [
                {
                    'rel_name': 'type_rel',
                    'attr_name': 'type',
                    'value': 'ECKD-SCSI',
                },
            ],
            self.models.StoragePool: [
                {
                    'rel_name': 'type_rel',
                    'attr_name': 'type',
                    'value': 'LVM_VG',
                },
                {
                    'rel_name': 'system_rel',
                    'attr_name': 'system',
                    'value': 'lpar0',
                },
            ],
            self.models.StorageVolumeProfileAssociation: [
                {
                    'rel_name': 'volume_rel',
                    'attr_name': 'volume',
                    'value': 'DSK8_x_0/1800',
                },
                {
                    'rel_name': 'profile_rel',
                    'attr_name': 'profile',
                    'value': 'cpc0/default cpc0',
                },
            ],
            self.models.StorageVolume: [
                {
                    'rel_name': 'type_rel',
                    'attr_name': 'type',
                    'value': 'ECKD',
                },
                {
                    'rel_name': 'server_rel',
                    'attr_name': 'server',
                    'value': 'DSK8_x_0',
                },
                {
                    'rel_name': 'system_rel',
                    'attr_name': 'system',
                    'value': 'cpc0',
                },
                {
                    'rel_name': 'pool_rel',
                    'attr_name': 'pool',
                    'value': 'Pool for system lpar0',
                },
            ],
            self.models.LogicalVolumeProfileAssociation: [
                {
                    'rel_name': 'volume_rel',
                    'attr_name': 'volume',
                    'value': 'Pool for system lpar0/spare image',
                },
                {
                    'rel_name': 'profile_rel',
                    'attr_name': 'profile',
                    'value': 'lpar0/default lpar0',
                },
            ],
            self.models.LogicalVolume: [
                {
                    'rel_name': 'type_rel',
                    'attr_name': 'type',
                    'value': 'QCOW2',
                },
                {
                    'rel_name': 'system_rel',
                    'attr_name': 'system',
                    'value': 'lpar0',
                },
                {
                    'rel_name': 'pool_rel',
                    'attr_name': 'pool',
                    'value': 'Pool for system lpar0',
                },
            ],
        }

        for model, relations in relation_map.items():
            for rel_map in relations:

                model_col = getattr(model, rel_map['attr_name'])
                if rel_map['value'].find('/') > -1:
                    value = rel_map['value'].split('/', 1)[1]
                else:
                    value = rel_map['value']

                # child/parent relation: special join handling for same table
                if rel_map.get('self') is True:
                    parent = aliased(model)
                    query = model.query.join(
                        parent, rel_map['rel_name']
                    ).filter(
                        parent.name == value
                    )

                # normal relationship pointing to another table: normal join
                else:
                    query = model.query.join(
                        rel_map['rel_name']
                    ).filter(
                        model_col == value
                    )

                item = query.first()

                # verify that we got a row
                self.assertIsInstance(item, model)

                # although we just specified the value for the query this is
                # necessary to trigger the usage of the hybrid_property
                self.assertEqual(
                    getattr(item, rel_map['attr_name']), rel_map['value']
                )

                # validate that the setter raises error when target for
                # association does not exist
                for wrong in ('some_wrong', 'some/wrong'):
                    with self.assertRaises(AssociationError):
                        setattr(item, rel_map['attr_name'], wrong)
                        DbUnit.session.commit()
                    DbUnit.session.rollback()

                # validate that the setter correctly works when we remove the
                # association for nullable types
                relation_attr = getattr(model, rel_map['rel_name'])
                # this is a way to get an item from a set
                fk_col = next(iter(relation_attr.property.local_columns))
                # column is nullable: confirm that it works to set None
                if fk_col.nullable:
                    setattr(item, rel_map['attr_name'], None)
                    DbUnit.session.commit()
                    # return to original value
                    setattr(item, rel_map['attr_name'], rel_map['value'])
                    DbUnit.session.commit()


    # test_relations()

# TestModels
