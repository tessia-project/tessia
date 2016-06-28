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
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import SystemModel

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Model name identifier',
    'arch': 'Architecture',
    'model': 'Model title',
    'submodel': 'Model sub-classification',
    'desc': 'Description',
}

#
# CODE
#
class SystemModelResource(SecureResource):
    """
    Resource for system models
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = SystemModel

        # name of the resource in the url
        name = 'system-models'

        title = 'System model'
        description = 'A model of system, containing architecture information'
        human_identifiers = ['name']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        name = fields.String(
            title=DESC['name'], description=DESC['name'])
        arch = fields.String(
            title=DESC['arch'], description=DESC['arch'], enum=['s390x'])
        model = fields.String(
            title=DESC['model'], description=DESC['model'])
        submodel = fields.String(
            title=DESC['submodel'], description=DESC['submodel'],
            nullable=True)
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)

# SystemModelResource
