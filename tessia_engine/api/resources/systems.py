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
from tessia_engine.api.exceptions import BaseHttpError
from tessia_engine.api.exceptions import ItemNotFoundError
from tessia_engine.api.resources.secure_resource import SecureResource
from tessia_engine.db.models import System

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Name',
    'hostname': 'Hostname',
    'model': 'Model',
    'type': 'Type',
    'hypervisor': 'Hypervisor name',
    'state': 'Current state',
    'modified': 'Last modified',
    'desc': 'Description',
    'modifier': 'Modified by',
    'project': 'Project',
    'owner': 'Owner',
}

GUEST_HYP_MATCHES = {
    'KVM': ['LPAR', 'KVM', 'ZVM'],
    'ZVM': ['LPAR'],
    'LPAR': ['CPC'],
    'CPC': [],
}

#
# CODE
#
class SystemResource(SecureResource):
    """
    Resource for systems
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = System

        # name of the resource in the url
        name = 'systems'

        title = 'System'
        description = (
            'A system contains volumes and network interfaces associated '
            'through boot profiles')

        # custom attribute to define one or more schema fields that have a
        # human description for an item, used by integrity exceptions to
        # parse db errors.
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
        hostname = fields.String(
            title=DESC['hostname'], description=DESC['hostname'],
            nullable=True)
        modified = fields.DateTime(
            title=DESC['modified'], description=DESC['modified'], io='r')
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        # relations
        hypervisor = fields.String(
            title=DESC['hypervisor'], description=DESC['hypervisor'],
            nullable=True)
        model = fields.String(
            title=DESC['model'], description=DESC['model'], nullable=True)
        type = fields.String(
            title=DESC['type'], description=DESC['type'])
        state = fields.String(
            title=DESC['state'], description=DESC['state'],
            nullable=True)
        modifier = fields.String(
            title=DESC['modifier'], description=DESC['modifier'], io='r')
        project = fields.String(
            title=DESC['project'], nullable=True, description=DESC['project'])
        owner = fields.String(
            title=DESC['owner'], nullable=True, description=DESC['owner'])

    def do_create(self, properties):
        """
        Custom implementation of system creation. Perform some sanity checks
        and add sensitive defaults to values not provided.

        Args:
            properties (dict): field=value combination for the item to be
                               created

        Raises:
            BaseHttpError: if combination guest/hypervisor is invalid
            ItemNotFoundError: if system type is invalid or hypervisor is
                               invalid

        Returns:
            int: new item's row id
        """
        guest_match_list = GUEST_HYP_MATCHES.get(properties['type'])
        # specified type is invalid: report error
        if guest_match_list is None:
            raise ItemNotFoundError(
                'type', properties['type'], self)

        # hypervisor specified: make sure it has correct type (i.e. a lpar
        # cannot belong to a kvm guest)
        if properties['hypervisor'] is not None:
            hyp = System.query.filter_by(
                name=properties['hypervisor']).one_or_none()
            # hypervisor provided not found: report error
            if hyp is None:
                raise ItemNotFoundError(
                    'hypervisor', properties['hypervisor'], self)

            if hyp.type not in guest_match_list:
                raise BaseHttpError(
                    code=422, msg='Invalid guest/hypervisor combination')

            if properties['model'] is None:
                properties['model'] = hyp.model

        elif properties['model'] is None:
            raise BaseHttpError(code=400, msg='System model must be specified')

        if properties['state'] is None:
            properties['state'] = 'AVAILABLE'

        return super().do_create(properties)
    # do_create()

    def do_update(self, properties, id):
        """
        Custom implementation of system update. Perform some sanity checks.

        Args:
            properties (dict): field=value combination for the fields to be
                               updated
            id (any): id of the item, usually an integer corresponding to the
                      id field in the table's database

        Raises:
            BaseHttpError: if combination guest/hypervisor is invalid
            ItemNotFoundError: if system type is invalid or hypervisor is
                               invalid

        Returns:
            int: id of updated item
        """
        # pylint: disable=redefined-builtin

        system_type = properties.get('type')
        hyp_name = properties.get('hypervisor')
        # no type or hypervisor change: nothing to verify
        if system_type is None and hyp_name is None:
            return super().do_update(properties, id)

        item = self.manager.read(id)
        # type not changed: fetch value from existing item
        if system_type is None:
            system_type = item.type

        guest_match_list = GUEST_HYP_MATCHES.get(system_type)
        # specified type is invalid: report error
        if guest_match_list is None:
            raise ItemNotFoundError('type', system_type, self)

        # hypervisor not changed: fetch value from existing item
        if hyp_name is None:
            hyp_obj = item.hypervisor_rel
        # hypervisor changed: fetch provided value from database
        else:
            hyp_obj = System.query.filter_by(name=hyp_name).one_or_none()
            # hypervisor provided not found: report error
            if hyp_obj is None:
                raise ItemNotFoundError('hypervisor', hyp_name, self)

        # guest/hypervisor combination does not match: report error
        if hyp_obj.type not in guest_match_list:
            raise BaseHttpError(
                code=422, msg='Invalid guest/hypervisor combination')

        return super().do_update(properties, id)
    # do_update()

# SystemResource
