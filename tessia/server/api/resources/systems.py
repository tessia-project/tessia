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
from flask import g as flask_global
from flask_potion import fields
from flask_potion.instances import Instances
from flask_potion.routes import Route
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from tessia.server.api.exceptions import BaseHttpError
from tessia.server.api.exceptions import ItemNotFoundError
from tessia.server.api.resources.secure_resource import NAME_PATTERN
from tessia.server.api.resources.secure_resource import SecureResource
from tessia.server.db.models import System, SystemProfile, SystemIface

import csv
import io

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
    'KVM': ['LPAR', 'KVM'],
    'ZVM': ['LPAR', 'ZVM'],
    'LPAR': ['CPC'],
    'CPC': [],
}

MSG_BAD_COMBO = 'Invalid guest/hypervisor combination'

FIELDS_CSV = (
    'HYPERVISOR', 'NAME', 'TYPE', 'HOSTNAME', 'IP', 'IFACE', 'LAYER2',
    'PORTNO', 'OWNER', 'PROJECT', 'STATE', 'DESC'
)

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
            title=DESC['name'], description=DESC['name'], pattern=NAME_PATTERN)
        hostname = fields.String(
            title=DESC['hostname'], description=DESC['hostname'],
            pattern=r'^[a-zA-Z0-9_\:\@\.\/\-]+$')
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
            title=DESC['state'], description=DESC['state'], nullable=True)
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
                raise BaseHttpError(code=422, msg=MSG_BAD_COMBO)

            if properties['model'] is None:
                properties['model'] = hyp.model
        elif properties['model'] is None:
            properties['model'] = 'ZGENERIC'

        if properties['state'] is None:
            properties['state'] = 'AVAILABLE'

        return super().do_create(properties)
    # do_create()

    @Route.GET('/schema', rel="describedBy", attribute="schema")
    def described_by(self, *args, **kwargs):
        schema, http_code, content_type = super().described_by(*args, **kwargs)
        # we don't want to advertise pagination for the bulk endpoint
        link_found = False
        for link in schema['links']:
            if link['rel'] == 'bulk':
                link_found = True
                link['schema']['properties'].pop('page')
                link['schema']['properties'].pop('per_page')
                break
        if not link_found:
            raise SystemError(
                'JSON schema for endpoint /{}/bulk not found'
                .format(self.Meta.name))
        return schema, http_code, content_type
    # described_by()

    @Route.GET('/bulk', rel='bulk')
    def bulk(self, **kwargs):
        """
        Bulk export operation
        """
        result = io.StringIO()
        csv_writer = csv.writer(result, quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(FIELDS_CSV)

        # we need to include information about network interfaces
        for entry in self.manager.instances(kwargs.get('where'),
                                            kwargs.get('sort')):
            try:
                self._perman.can(
                    'READ', flask_global.auth_user, entry)
            except PermissionError:
                continue

            entry.ip = None
            entry.iface = None
            entry.layer2 = None
            entry.portno = None

            # retrieve main network interface and ip
            try:
                # use the default profile as hint for the gateway iface
                gw_iface_hint = SystemProfile.query.filter_by(
                    system_id=entry.id, default=True
                ).one().gateway
                if gw_iface_hint:
                    gw_iface = SystemIface.query.filter_by(
                        system_id=entry.id, name=gw_iface_hint
                    ).one()
                else:
                    gw_iface = None
            except (MultipleResultsFound, NoResultFound):
                gw_iface = None

            # no gateway interface defined: use first one with ip assigned
            if not gw_iface:
                ifaces = SystemIface.query.filter_by(system_id=entry.id).all()
                # no interfaces available: nothing else to do
                if not ifaces:
                    continue
                for iface in ifaces:
                    if iface.ip_address:
                        gw_iface = iface
                        break
                # no iface with ip found: use first available
                if not gw_iface:
                    gw_iface = ifaces[0]

            if gw_iface.type.lower() == 'osa':
                entry.iface = gw_iface.attributes.get(
                    'ccwgroup', '').replace('0.0.', '')
                entry.layer2 = {False: '0', True: '1'}[
                    gw_iface.attributes.get('layer2', False)]
                entry.portno = gw_iface.attributes.get('portno', 0)
            else:
                entry.iface = gw_iface.mac_address

            if gw_iface.ip_address:
                entry.ip = gw_iface.ip_address.split('/', 1)[-1]

            csv_writer.writerow(
                [getattr(entry, attr.lower()) for attr in FIELDS_CSV])

        result.seek(0)
        return result.read()
    # bulk()
    bulk.request_schema = Instances()
    bulk.response_schema = fields.String(
        title="result output", description="content in CSV format")

    def do_update(self, properties, system_id):
        """
        Custom implementation of system update. Perform some sanity checks.

        Args:
            properties (dict): field=value combination for the fields to be
                               updated
            system_id (any): system id

        Raises:
            BaseHttpError: if combination guest/hypervisor is invalid
            ItemNotFoundError: if system type is invalid or hypervisor is
                               invalid

        Returns:
            int: id of updated item
        """

        system_type = properties.get('type')
        hyp_name = properties.get('hypervisor')
        # no type or hypervisor change: nothing to verify
        if system_type is None and hyp_name is None:
            return super().do_update(properties, system_id)

        item = self.manager.read(system_id)
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
            raise BaseHttpError(code=422, msg=MSG_BAD_COMBO)

        return super().do_update(properties, system_id)
    # do_update()

# SystemResource
