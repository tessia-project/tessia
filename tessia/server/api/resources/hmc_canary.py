# Copyright 2021 IBM Corp.
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
from tessia.server.db.models import HmcCanary

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'HMC hostname',
    'status': 'Availability of HMC',
    'cpc_status': 'Status of CPC',
    'last_update': 'Last update',
}

NAME_PATTERN = r'^\w+[\w\s\.\-\@]+$'

#
# CODE
#


class HMCCanaryResource(SecureResource):
    """
    Resource for HMC Canary.
    """
    class Meta:
        """
        Potion's meta section.
        """
        # the sqlalchemy model
        model = HmcCanary

        # name of the resource in the url
        name = 'hmc-canary'

        title = 'Hmc Canary'
        description = (
            'hmc resources status monitoring')
        human_identifiers = ['name']

    class Schema:
        """
        Potion's schema section.
        """
        name = fields.String(title=DESC['name'],
                             description=DESC['name'],
                             pattern=NAME_PATTERN)
        status = fields.String(title=DESC['status'],
                               description=DESC['status'],
                               nullable=True)
        cpc_status = fields.Any(title=DESC['cpc_status'],
                                description=DESC['cpc_status'],
                                nullable=True)
        last_update = fields.DateTime(title=DESC['last_update'],
                                      description=DESC['last_update'],
                                      nullable=False)

# HMCCanaryResource
