# Copyright 2017 IBM Corp.
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
Resource definition
"""

#
# IMPORTS
#
from flask_potion import fields
from flask_potion.contrib.alchemy.fields import InlineModel
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import Role
from tessia_engine.db.models import RoleAction

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Role',
    'desc': 'Description',
    'actions': 'Allowed actions',
}

#
# CODE
#
class RoleResource(SecureResource):
    """
    Resource for roles
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = Role

        # name of the resource in the url
        name = 'roles'

        title = 'Role'
        description = 'A role contains a set of permissions for users'
        human_identifiers = ['name']
    # Meta

    class Schema:
        """
        Schema defining the resource fields and their properties
        """
        name = fields.String(
            title=DESC['name'], description=DESC['name'], io='r')
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], io='r')
        # relationships section
        actions = fields.List(
            # InlineModel is a way to use a different sa model in a field while
            # specifying which fields should be displayed.
            InlineModel(
                {
                    'resource': fields.String(),
                    'action': fields.String(),
                },
                model=RoleAction,
                io='r'
            ),
            # point to the sa's model relationship containing the entries
            attribute='actions_rel',
            # for json schema
            title=DESC['actions'],
            description=DESC['actions'],
            # read-only field
            io='r'
        )
    # Schema
# RoleResource
