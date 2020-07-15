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
Unit test for resource access module
"""

#
# IMPORTS
#
from tessia.server.db import models
from tessia.server.lib.perm_rules.resources import SystemPermissions
from tessia.server.lib.perm_rules.resources import StorageVolumePermissions
from tests.unit.db.models import DbUnit

from unittest import TestCase

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class TestResourcePermissions(TestCase):
    """
    Unit test for the lib.perm.resources module
    """

    @classmethod
    def setUpClass(cls):
        """
        Called once before any test in this test class run.
        """
        DbUnit.create_db()
        cls.db = DbUnit
        project_1 = 'one thing'
        project_2 = 'other thing'
        cls._projects = [project_1, project_2]
        cls._db_entries = {
            "User": [
                {
                    "name": "user_sandboxed",
                    "admin": False,
                    "title": "Sandboxed user",
                    "restricted": False,
                    "login": "user_sandbox@domain.com"
                },
                {
                    "name": "user_restricted",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": True,
                    "login": "user_restricted@domain.com"
                },
                {
                    "name": "user_user",
                    "admin": False,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_user@domain.com"
                },
                {
                    "name": "admin",
                    "admin": True,
                    "title": "Title of user",
                    "restricted": False,
                    "login": "user_admin@domain.com"
                },
            ],
            "Project": [
                {
                    "name": project_1,
                    "desc": "{} test".format(project_1),
                },
                {
                    "name": project_2,
                    "desc": "{} test".format(project_2),
                }
            ],
            "UserRole": [
                {
                    "project": project_1,
                    "user": "user_sandbox@domain.com",
                    "role": "USER_SANDBOX"
                },
                {
                    "project": "Quarantine",
                    "user": "user_restricted@domain.com",
                    "role": "USER_RESTRICTED"
                },
                {
                    "project": project_1,
                    "user": "user_user@domain.com",
                    "role": "USER"
                },
            ],
            "System": [
                {
                    "name": "lpar1",
                    "owner": "user_admin@domain.com",
                    "desc": "- LPAR 1",
                    "state": "AVAILABLE",
                    "modifier": "user_admin@domain.com",
                    "type": "lpar",
                    "hypervisor": "cpc0",
                    "hostname": "lpar1.domain.com",
                    "project": project_1,
                    "model": "ZEC12_H20"
                },
                {
                    "name": "lpar2",
                    "owner": "user_restricted@domain.com",
                    "desc": "- LPAR 2",
                    "model": "ZEC12_H20",
                    "modifier": "user_admin@domain.com",
                    "hypervisor": "cpc0",
                    "hostname": "lpar2.domain.com",
                    "state": "AVAILABLE",
                    "type": "lpar",
                    "project": project_2
                },
                {
                    "name": "lpar-other",
                    "owner": "user_user@domain.com",
                    "desc": "- LPAR other",
                    "model": "ZEC12_H20",
                    "modifier": "user_admin@domain.com",
                    "hypervisor": "cpc0",
                    "hostname": "lpar-other.domain.com",
                    "state": "AVAILABLE",
                    "type": "lpar",
                    "project": project_1
                },
            ],
            "StorageVolume": [
                {
                    "specs": {},
                    "server": "DSK8_x_0",
                    "type": "DASD",
                    "system": "lpar1",
                    "owner": "user_user@domain.com",
                    "desc": "- DASD disk for regression tests",
                    "volume_id": "2800",
                    "part_table": {
                        "type": "msdos",
                        "table": [
                            {
                                "type": "primary",
                                "fs": "ext4",
                                "size": 8000,
                                "mo": None,
                                "mp": "/"
                            },
                            {
                                "type": "primary",
                                "fs": "swap",
                                "size": 2000,
                                "mo": None,
                                "mp": None
                            }
                        ]
                    },
                    "modifier": "user_admin@domain.com",
                    "system_attributes": "{}",
                    "project": project_1,
                    "size": 10000
                },
                {
                    "specs": {},
                    "server": "DSK8_x_0",
                    "type": "DASD",
                    "system": "lpar2",
                    "owner": "user_admin@domain.com",
                    "desc": "- DASD disk for regression tests",
                    "volume_id": "2801",
                    "part_table": {
                        "type": "msdos",
                        "table": [
                            {
                                "type": "primary",
                                "fs": "ext4",
                                "size": 8000,
                                "mo": None,
                                "mp": "/"
                            },
                            {
                                "type": "primary",
                                "fs": "swap",
                                "size": 2000,
                                "mo": None,
                                "mp": None
                            }
                        ]
                    },
                    "modifier": "user_admin@domain.com",
                    "system_attributes": "{}",
                    "project": project_2,
                    "size": 10000,
                    "pool": "Pool for system lpar0"
                }
            ]
        }
        cls.db.create_entry(cls._db_entries)
    # setUpClass()

    def test_read_owned(self):
        """
        Read owned
        """
        user = models.User.query.filter(
            models.User.login == 'user_restricted@domain.com').one()
        # pylint: disable=comparison-with-callable
        system = SystemPermissions.protect_query(
            models.System.query.filter(
                models.System.owner_id == user.id
            ), user).one()
        volume = StorageVolumePermissions.protect_query(
            models.StorageVolume.query.filter(
                models.StorageVolume.system_id == system.id
            ), user).one()
        self.assertIsNotNone(volume)
    # test_read_owned()

    def test_read_available(self):
        """
        Read from other projects, including system-owned dependencies
        """
        user = models.User.query.filter(
            models.User.login == 'user_user@domain.com').first()
        self.assertIsNotNone(user)
        system = SystemPermissions.protect_query(
            models.System.query.join(models.Project).filter(
                models.System.project == self._projects[1]
            ), user).first()
        self.assertIsNotNone(system)
        volume = StorageVolumePermissions.protect_query(
            models.StorageVolume.query.join(models.Project).filter(
                models.StorageVolume.project == self._projects[1]
            ), user).first()
        self.assertEqual(volume.volume_id, '2801')
    # test_read_available()

    def test_no_read_restricted(self):
        """
        Nothing returned for restricted users in other projects
        """
        user = models.User.query.filter(
            models.User.login == 'user_restricted@domain.com').first()
        self.assertIsNotNone(user)
        system = SystemPermissions.protect_query(
            models.System.query.join(models.Project).filter(
                models.System.project == self._projects[0]
            ), user).first()
        self.assertIsNone(system)
    # test_no_read_restricted()

    def test_no_read_sandbox(self):
        """
        Nothing returned for sandboxed users even in their project
        """
        user = models.User.query.filter(
            models.User.login == 'user_sandbox@domain.com').first()
        self.assertIsNotNone(user)
        system = SystemPermissions.protect_query(
            models.System.query.join(models.Project).filter(
                models.System.project == self._projects[0]
            ), user).first()
        self.assertIsNone(system)
        system = SystemPermissions.protect_query(
            models.System.query.join(models.Project).filter(
                models.System.project == self._projects[1]
            ), user).first()
        self.assertIsNone(system)
    # test_no_read_sandbox()
# TestModels
