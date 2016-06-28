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
from flask_potion.contrib.alchemy.fields import InlineModel
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import SystemIface
from tessia_engine.db.models import SystemProfile

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Interface name',
    'osname': 'Operating system name',
    'ip_address': 'IP address',
    'mac_address': 'MAC address',
    'system': 'System',
    'type': 'Interface type',
    'attributes': 'Attributes',
    'desc': 'Description',
    'system_profiles': 'Associated system profiles',
}

#
# CODE
#
class SystemIfaceResource(SecureResource):
    """
    Resource for system network interfaces
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = SystemIface

        # name of the resource in the url
        name = 'system-ifaces'

        title = 'Network interfaces'
        description = 'System network interfaces'
        # custom attribute to define one or more schema fields that have a
        # human description for an item, used by api exceptions to report
        # db errors.
        human_identifiers = ['system', 'name']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        name = fields.String(
            title=DESC['name'], description=DESC['name'])
        osname = fields.String(
            title=DESC['osname'], description=DESC['osname'], nullable=True)
        attributes = fields.String(
            title=DESC['attributes'], description=DESC['attributes'],
            nullable=True)
        mac_address = fields.String(
            title=DESC['mac_address'], description=DESC['mac_address'],
            nullable=True)
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        # relations
        ip_address = fields.String(
            title=DESC['ip_address'], description=DESC['ip_address'],
            nullable=True)
        system = fields.String(
            title=DESC['system'], description=DESC['system'])
        type = fields.String(
            title=DESC['type'], description=DESC['type'])
        profiles = fields.List(
            # InlineModel is a way to use a different sa model in a field while
            # specifying which fields should be displayed.
            InlineModel(
                {
                    # try to keep ourselves restful as possible by providing
                    # the link to the referenced item
                    '$uri': fields.ItemUri(
                        'tessia_engine.api.resources.system_profiles.'
                        'SystemProfileResource',
                        attribute='id'
                    ),
                    'name': fields.String(),
                    'system': fields.String(),
                },
                model=SystemProfile,
                io='r'
            ),
            # point to the sa's model relationship containing the entries
            attribute='profiles_rel',
            # for json schema
            title=DESC['system_profiles'],
            description=DESC['system_profiles'],
            # read-only field
            io='r'
        )

# SystemIfaceResource
