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
Resource definition
"""

#
# IMPORTS
#
from flask_potion import fields
from tessia_engine.api.resources.secure_resource import NAME_PATTERN
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import User

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'login': 'Login',
    'name': 'Fullname',
    'title': 'Job title',
    'restricted': 'Restricted',
    'admin': 'Administrator',
}

#
# CODE
#
class UserResource(SecureResource):
    """
    Resource for application users
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = User

        # name of the resource in the url
        name = 'users'

        title = 'User'
        description = 'A user belongs to a project and has roles'
        human_identifiers = ['login']
    # Meta

    class Schema:
        """
        Schema defining the resource fields and their properties
        """
        login = fields.String(
            title=DESC['login'], description=DESC['login'],
            pattern=r'^[a-zA-Z0-9_\:\@\.\-]+$')
        name = fields.String(
            title=DESC['name'], description=DESC['name'], pattern=NAME_PATTERN)
        title = fields.String(
            title=DESC['title'], description=DESC['title'], nullable=True)
        restricted = fields.Boolean(
            title=DESC['restricted'], description=DESC['restricted'])
        admin = fields.Boolean(
            title=DESC['admin'], description=DESC['admin'])
    # Schema
# UserResource
