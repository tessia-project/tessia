# Copyright 2018 IBM Corp.
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
from tessia.server.api.resources.secure_resource import SecureResource
from tessia.server.db.models import OperatingSystem

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'OS identifier',
    'type': 'OS type',
    'major': 'Major version',
    'minor': 'Minor version',
    'pretty_name': 'Pretty name',
    'template': 'Default install template'
}
OS_TYPES = ('cms', 'debian', 'redhat', 'suse')

#
# CODE
#
class OperatingSystemResource(SecureResource):
    """
    Resource for system types
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = OperatingSystem

        # name of the resource in the url
        name = 'operating-systems'

        title = 'Operating system'
        description = 'A supported operating system'
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
        type = fields.String(
            title=DESC['type'], description=DESC['type'],
            enum=OS_TYPES)
        major = fields.Integer(
            title=DESC['major'], description=DESC['major'])
        minor = fields.Integer(
            title=DESC['minor'], description=DESC['minor'])
        pretty_name = fields.String(
            title=DESC['pretty_name'], description=DESC['pretty_name'])
        # relations
        template = fields.String(
            title=DESC['template'], description=DESC['template'],
            nullable=True)

# OperatingSystemResource
