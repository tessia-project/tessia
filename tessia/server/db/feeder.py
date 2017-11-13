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
Provides helper utilities to insert data in the database
"""

#
# IMPORTS
#
from tessia.server.db.connection import MANAGER
from tessia.server.db import models

#
# CONSTANTS AND DEFINITIONS
#
INSERT_ORDER = [
    'OperatingSystem',
    'Repository',
    'IfaceType',
    'Role',
    'RoleAction',
    'StoragePoolType',
    'StorageServerType',
    'SystemArch',
    'SystemModel',
    'SystemType',
    'SystemState',
    'VolumeType',
    'Project',
    'User',
    'UserKey',
    'UserRole',
    'Template',
    'System',
    'NetZone',
    'Subnet',
    'IpAddress',
    'SystemIface',
    'StorageServer',
    'StoragePool',
    'StorageVolume',
    'LogicalVolume',
    'SystemProfile',
    'StorageVolumeProfileAssociation',
    'SystemIfaceProfileAssociation',
    'LogicalVolumeProfileAssociation',
]

#
# CODE
#
def db_insert(data):
    """
    Given a dictionary in the format:
        {'ModelObjectName': [{'field_name': 'value', 'field_name2': 'value'}]}
    Instantiate the model objects and commit the data to the database.

    Args:
        data (dict): dictionary containing db entries

    Raises:
        None
    """
    # Since we can start by trying to feed an object that needs to query the
    # database to fullfill some property, we need to create a session so that
    # the "query" property is created in every object of the model.
    MANAGER.connect()
    for model_name in INSERT_ORDER:
        model_class = getattr(models, model_name)
        for row in data.get(model_name, []):
            new_instance = model_class(**row)
            MANAGER.session.add(new_instance)

    MANAGER.session.commit()
# db_insert()
