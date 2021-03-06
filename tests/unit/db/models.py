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
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import aliased
from tessia.server.db.exceptions import AssociationError
from tessia.server.db import connection
from tessia.server.db import models
from tessia.server.db import types
from tessia.server.db.feeder import db_insert

from unittest import TestCase
from unittest.mock import patch

import os
import json

#
# CONSTANTS AND DEFINITIONS
#
DEFAULT_TEST_DB = 'tessia_test'

#
# CODE
#


class DbUnit:
    """
    This is a helper class that can be used by other tests whenenver they need
    to create a test database instance from scratch.
    """
    SAMPLE_DATA = '{}/sample.json'.format(
        os.path.dirname(os.path.abspath(__file__)))

    @classmethod
    def _prepare(cls):
        """
        Create the database in postgres
        """
        db_url = os.environ.get('TESSIA_DB_TEST_URI')
        if not db_url:
            raise RuntimeError('env variable TESSIA_DB_TEST_URI not available')
        db_url_obj = make_url(db_url)
        if not db_url_obj.drivername.startswith('postgresql'):
            raise RuntimeError('Only postgresql is supported as test database '
                               '({} was set)'.format(db_url_obj.drivername))
        if db_url_obj.database:
            test_db = db_url_obj.database
        else:
            test_db = DEFAULT_TEST_DB

        db_url_obj.database = 'postgres'
        engine = create_engine(db_url_obj, isolation_level='AUTOCOMMIT')

        # check whether db already exists
        result = engine.execute("SELECT 1 FROM pg_database WHERE datname='{}'"
                                .format(test_db))
        db_exist = result.scalar()
        result.close()
        # db does not exist: try to create it
        if not db_exist:
            result = engine.execute(
                "CREATE DATABASE {} ENCODING 'UTF8' LC_COLLATE 'en_US.utf8' "
                "LC_CTYPE 'en_US.utf8' TEMPLATE template0".format(test_db))
            result.close()

        engine.dispose()
        db_url_obj.database = test_db

        # prepare the url for use by sqlalchemy
        return str(db_url_obj)
    # _prepare()

    @classmethod
    def create_db(cls, empty=False):
        """
        Initialize the test database.
        """
        # connection already opened: close it
        if connection.MANAGER._conn:
            connection.MANAGER.session.remove()
            connection.MANAGER.engine.dispose()
        db_url = cls._prepare()

        # create a mock config to point to our test db url
        patcher = patch.object(connection, 'CONF', autospec=True)
        mock_conf = patcher.start()
        conf = {'db': {'url': db_url}}
        mock_conf.get_config.return_value = conf

        # make sure it's a new connection and not one from a previous test
        connection.MANAGER._conn = None
        for class_entry in models.BASE._decl_class_registry.values():
            if isinstance(class_entry, type):
                if hasattr(class_entry, 'query_class'):
                    del class_entry.query_class
                if hasattr(class_entry, 'query'):
                    del class_entry.query
        # session can be used by consumers
        cls.session = connection.MANAGER.session

        # mock config not needed anymore
        patcher.stop()

        # store the references to be used later
        cls._db_insert = db_insert

        # reset, create and pre-populate the database
        models.BASE.metadata.drop_all(connection.MANAGER.engine)
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

    @classmethod
    def drop_db(cls):
        """
        Drop the test database.
        """
        models.BASE.metadata.drop_all(connection.MANAGER.engine)
    # drop_db()
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

        # add the scheduler entries as they are not part of the sample file
        request = cls.models.SchedulerRequest(
            requester="user_x_0@domain.com",
            action_type=cls.models.SchedulerRequest.ACTION_SUBMIT,
            job_type="echo",
            parameters="",
            submit_date=datetime.utcnow()
        )
        DbUnit.session.add(request)
        job = cls.models.SchedulerJob(
            requester="user_x_0@domain.com",
            job_type="echo",
            state=cls.models.SchedulerJob.STATE_COMPLETED,
            resources={"exclusive": "A", "shared": "B"},
            parameters="",
            description="test",
            submit_date=datetime.utcnow()
        )
        DbUnit.session.add(job)
        DbUnit.session.commit()

    # setUpClass()

    def test_repr(self):
        """
        Make sure all model representations work

        Args:
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

        Raises:
            None
        """
        # create a map with all relations to be tested
        relation_map = [
            (self.models.RoleAction, [
                {
                    # the relationship name in the model
                    'rel_name': 'role_rel',
                    # the field name in the model
                    'attr_name': 'role',
                    # the value of the field
                    'value': 'USER',
                },
            ]),
            (self.models.UserRole, [
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
                    'value': 'USER',
                },
                {
                    # the relationship name in the model
                    'rel_name': 'project_rel',
                    # the field name in the model
                    'attr_name': 'project',
                    # the value of the field
                    'value': 'Department x',
                },
            ]),
            (self.models.UserKey, [
                {
                    # the relationship name in the model
                    'rel_name': 'user_rel',
                    # the field name in the model
                    'attr_name': 'user',
                    # the value of the field
                    'value': 'user_x_0@domain.com',
                }
            ]),
            (self.models.NetZone, [
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
            ]),
            (self.models.Subnet, [
                {
                    'rel_name': 'zone_rel',
                    'attr_name': 'zone',
                    'value': 'cpc0',
                },
            ]),
            (self.models.IpAddress, [
                {
                    'rel_name': 'subnet_rel',
                    'attr_name': 'subnet',
                    'value': 'cpc0 shared',
                },
                {
                    'rel_name': 'system_rel',
                    'attr_name': 'system',
                    'value': 'cpc0',
                },
            ]),
            (self.models.SystemType, [
                {
                    'rel_name': 'arch_rel',
                    'attr_name': 'arch',
                    'value': 's390x',
                },
            ]),
            (self.models.SystemModel, [
                {
                    'rel_name': 'arch_rel',
                    'attr_name': 'arch',
                    'value': 's390x',
                },
            ]),
            (self.models.System, [
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
            ]),
            (self.models.SystemProfile, [
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
                    'value': 'RHEL7.0',
                },
            ]),
            (self.models.SystemIfaceProfileAssociation, [
                {
                    'rel_name': 'iface_rel',
                    'attr_name': 'iface',
                    'value': 'lpar0/external osa',
                },
                {
                    'rel_name': 'profile_rel',
                    'attr_name': 'profile',
                    'value': 'lpar0/default lpar0',
                },
            ]),
            (self.models.SystemIface, [
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
                    'value': 'lpar0',
                },
            ]),
            (self.models.StorageServer, [
                {
                    'rel_name': 'type_rel',
                    'attr_name': 'type',
                    'value': 'DASD-FCP',
                },
            ]),
            (self.models.StoragePool, [
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
            ]),
            (self.models.StorageVolumeProfileAssociation, [
                {
                    'rel_name': 'volume_rel',
                    'attr_name': 'volume',
                    'value': 'DSK8_x_0/1800',
                },
                {
                    'rel_name': 'profile_rel',
                    'attr_name': 'profile',
                    'value': 'lpar0/default lpar0',
                },
            ]),
            (self.models.StorageVolume, [
                {
                    'rel_name': 'type_rel',
                    'attr_name': 'type',
                    'value': 'DASD',
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
            ]),
            (self.models.LogicalVolumeProfileAssociation, [
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
            ]),
            (self.models.LogicalVolume, [
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
            ]),
            (self.models.SchedulerRequest, [
                {
                    'rel_name': 'requester_rel',
                    'attr_name': 'requester',
                    'value': 'user_x_0@domain.com',
                },
            ]),
            (self.models.SchedulerJob, [
                {
                    'rel_name': 'requester_rel',
                    'attr_name': 'requester',
                    'value': 'user_x_0@domain.com',
                },
            ]),
            (self.models.OperatingSystem, [
                {
                    # the relationship name in the model
                    'rel_name': 'template_rel',
                    # the field name in the model
                    'attr_name': 'template',
                    # the value of the field
                    'value': 'rhel7-custom',
                },
            ]),
        ]

        for model, relations in relation_map:
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

    def test_validators(self):
        """
        Exercise the models' validators
        """
        # enum validation for jobs
        for invalid_field in ('time_slot', 'state'):
            regex = r'Invalid <\({field}\)=\(invalid_{field}\)>'.format(
                field=invalid_field)
            with self.assertRaisesRegex(ValueError, regex):
                kwargs = {
                    'requester': 'user_x_0@domain.com',
                    'job_type': 'echo',
                    'resources': {"exclusive": "A", "shared": "B"},
                    'parameters': '',
                    'description': 'test',
                    'submit_date': datetime.utcnow()
                }
                kwargs[invalid_field] = 'invalid_{}'.format(invalid_field)
                job = self.models.SchedulerJob(**kwargs)
                DbUnit.session.add(job)
                DbUnit.session.commit()
            # return db session to clean state
            DbUnit.session.rollback()

        # get a valid job to allow requests to be created in next step
        job = self.models.SchedulerJob.query.first()

        # enum validation for requests
        for invalid_field in ('action_type', 'time_slot', 'state'):
            regex = r'Invalid <\({field}\)=\(invalid_{field}\)>'.format(
                field=invalid_field)
            with self.assertRaisesRegex(ValueError, regex):
                kwargs = {
                    'requester': 'user_x_0@domain.com',
                    'job_id': job.id,
                    'submit_date': datetime.utcnow()
                }
                kwargs[invalid_field] = 'invalid_{}'.format(invalid_field)
                # not testing action_type field: set cancel as the default
                # since action_type must be always specified
                if invalid_field != 'action_type':
                    kwargs['action_type'] = (
                        self.models.SchedulerRequest.ACTION_CANCEL)

                request = self.models.SchedulerRequest(**kwargs)
                DbUnit.session.add(request)
                DbUnit.session.commit()
            # return db session to clean state
            DbUnit.session.rollback()

        # confirm that cancel requests must only specify action and job types
        request = self.models.SchedulerRequest(
            requester="user_x_0@domain.com",
            action_type=self.models.SchedulerRequest.ACTION_CANCEL,
            job_type='',
            submit_date=datetime.utcnow(),
            job_id=job.id,
        )
        DbUnit.session.add(request)
        DbUnit.session.commit()
    # test_validators()

    def test_storage_volume_human_name(self):
        """
        Test the hybrid attribute definition human_name for StorageVolume
        """
        item = self.models.StorageVolume.query.first()

        # verify that we got a row
        self.assertIsInstance(item, self.models.StorageVolume)

        # test the getter
        server, volume_id = item.human_name.split('/', 1)
        self.assertEqual(item.server, server)
        self.assertEqual(item.volume_id, volume_id)

        # test the setter with invalid value
        with self.assertRaises(ValueError):
            item.human_name = 'some_invalid_id'

        # test the setter with invalid association
        with self.assertRaises(AssociationError):
            item.human_name = 'some_server/some_volume_id'

        # test the setter with valid value
        item.human_name = '{}/{}'.format(item.server, item.volume_id)
        DbUnit.session.add(item)
        DbUnit.session.commit()
        self.assertEqual(item.server, server)
        self.assertEqual(item.volume_id, volume_id)

    # test_storage_volume_human_name()
# TestModels
