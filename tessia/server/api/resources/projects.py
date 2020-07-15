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
from tessia.server.api.resources.secure_resource import NAME_PATTERN
from tessia.server.api.resources.secure_resource import SecureResource
from tessia.server.db.models import Project

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Name',
    'desc': 'Description',
}

#
# CODE
#


class ProjectResource(SecureResource):
    """
    Resource for projects
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = Project

        # name of the resource in the url
        name = 'projects'

        # not used at the moment
        exclude_fields = ['avatar']

        title = 'Project'
        description = 'A project contains group of users'
        human_identifiers = ['name']

    class Schema:
        """
        Potion's schema section
        """
        name = fields.String(
            title=DESC['name'], description=DESC['name'], pattern=NAME_PATTERN)
        desc = fields.String(title=DESC['desc'], description=DESC['desc'])

# ProjectResource
