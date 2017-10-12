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
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import Template

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Template name',
    'content': 'Template content',
    'operating_system': 'Supported OS',
    'modified': 'Last modified',
    'desc': 'Description',
    'modifier': 'Modified by',
    'project': 'Project',
    'owner': 'Owner',
}

#
# CODE
#
class AutoTemplateResource(SecureResource):
    """
    Resource for auto templates
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = Template

        # name of the resource in the url
        name = 'auto-templates'

        title = 'Auto template'
        description = ('A template used to automatically install an operating '
                       'system')
        human_identifiers = ['name']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        name = fields.String(
            title=DESC['name'], description=DESC['name'],
            pattern=r'^[a-zA-Z0-9_\s\.\-]+$')
        content = fields.String(
            title=DESC['content'], description=DESC['content'])
        modified = fields.DateTime(
            title=DESC['modified'], description=DESC['modified'], io='r')
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        # relations
        operating_system = fields.String(
            title=DESC['operating_system'],
            description=DESC['operating_system'])
        modifier = fields.String(
            title=DESC['modifier'], description=DESC['modifier'], io='r')
        project = fields.String(
            title=DESC['project'], nullable=True, description=DESC['project'])
        owner = fields.String(
            title=DESC['owner'], nullable=True, description=DESC['owner'])

# AutoTemplateResource
