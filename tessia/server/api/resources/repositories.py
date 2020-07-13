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
from tessia.server.api.exceptions import BaseHttpError
from tessia.server.api.resources.secure_resource import NAME_PATTERN
from tessia.server.api.resources.secure_resource import SecureResource
from tessia.server.db.models import Repository

#
# CONSTANTS AND DEFINITIONS
#
DESC = {
    'name': 'Repository name',
    'url': 'Network URL',
    'kernel': 'Kernel path',
    'initrd': 'Initrd path',
    'install_image': 'Install image URL',
    'operating_system': 'Installable OS',
    'modified': 'Last modified',
    'desc': 'Description',
    'modifier': 'Modified by',
    'project': 'Project',
    'owner': 'Owner',
}

#
# CODE
#


class RepositoryResource(SecureResource):
    """
    Resource for package repositories
    """
    class Meta:
        """
        Potion's meta section
        """
        # the sqlalchemy model
        model = Repository

        # name of the resource in the url
        name = 'repositories'

        title = 'Package pepository'
        description = (
            'A repository is a collection of packages or files that can be '
            'installed on a system')
        human_identifiers = ['name', 'url']

    class Schema:
        """
        Potion's schema section
        """
        # it seems that 'title' attribute would be better than 'description'
        # (according to json spec) but our client does not support it therefore
        # we set both
        name = fields.String(
            title=DESC['name'], description=DESC['name'], pattern=NAME_PATTERN)
        url = fields.String(
            title=DESC['url'], description=DESC['url'],
            pattern=r'^[a-zA-Z0-9_\:\@\.\/\-]+$')
        kernel = fields.String(
            title=DESC['kernel'], description=DESC['kernel'], nullable=True)
        initrd = fields.String(
            title=DESC['initrd'], description=DESC['initrd'], nullable=True)
        install_image = fields.String(
            title=DESC['install_image'], description=DESC['install_image'],
            nullable=True)
        modified = fields.DateTime(
            title=DESC['modified'], description=DESC['modified'], io='r')
        desc = fields.String(
            title=DESC['desc'], description=DESC['desc'], nullable=True)
        # relations
        operating_system = fields.String(
            title=DESC['operating_system'],
            description=DESC['operating_system'], nullable=True)
        modifier = fields.String(
            title=DESC['modifier'], description=DESC['modifier'], io='r')
        owner = fields.String(
            title=DESC['owner'], description=DESC['owner'], nullable=True)
        project = fields.String(
            title=DESC['project'], description=DESC['project'], nullable=True)
    # Schema

    @staticmethod
    def _assert_os(properties, repo_obj):
        """
        Assert that kernel and initrd paths are not null when an operating
        system is specified.
        """
        operating_system = None
        if 'operating_system' in properties:
            operating_system = properties['operating_system']
        elif repo_obj:
            operating_system = repo_obj.operating_system_rel
        if operating_system is None:
            return

        for prop in ('kernel', 'initrd'):
            prop_value = None
            if prop in properties:
                prop_value = properties[prop]
            elif repo_obj:
                prop_value = getattr(repo_obj, prop)
            if not prop_value:
                msg = ("Property '{}' cannot be null when operating "
                       "system is specified.".format(prop))
                raise BaseHttpError(code=400, msg=msg)

    # _assert_os()

    def do_create(self, properties):
        """
        Overriden method to perform sanity check on os/kernel/initrd
        combination.
        See parent class for complete docstring.
        """
        self._assert_os(properties, None)

        return super().do_create(properties)
    # do_create()

    def do_update(self, properties, repo_id):
        """
        Overriden method to perform sanity check on the address provided.
        See parent class for complete docstring.
        """
        item = self.manager.read(repo_id)
        self._assert_os(properties, item)

        return super().do_update(properties, repo_id)
    # do_update()

# RepositoryResource
