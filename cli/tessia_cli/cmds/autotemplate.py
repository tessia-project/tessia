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
Module for the os installation template (autotemplate) commands
"""

#
# IMPORTS
#
from tessia_cli.client import Client
from tessia_cli.filters import dict_to_filter
from tessia_cli.output import print_items
from tessia_cli.types import AUTO_TEMPLATE
from tessia_cli.types import NAME
from tessia_cli.utils import fetch_and_delete
from tessia_cli.utils import fetch_and_update
from tessia_cli.utils import fetch_item

import click

#
# CONSTANTS AND DEFINITIONS
#
MODEL_FIELDS = (
    'name', 'operating_system', 'owner', 'project', 'modified', 'modifier',
    'desc'
)

#
# CODE
#

@click.group()
def autotemplate():
    """manage the autoinstallation templates"""
    pass
# autotemplate()

@autotemplate.command('add')
@click.option('--name', required=True, type=NAME,
              help="template's name identifier")
@click.option('--content', required=True, type=AUTO_TEMPLATE,
              help="template content")
@click.option('operating_system', '--os', required=True, help="supported OS")
@click.option('--project', help="project owning template")
@click.option('--desc', help="free form field describing template")
def template_add(**kwargs):
    """
    add a new auto template
    """
    client = Client()

    item = client.AutoTemplates()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()

    click.echo('Item added successfully.')
# template_add()

@autotemplate.command(name='del')
@click.option('--name', required=True, type=NAME, help="template to delete")
def template_del(name):
    """
    remove an existing auto template
    """
    client = Client()

    fetch_and_delete(
        client.AutoTemplates, {'name': name}, 'template not found.')
    click.echo('Item successfully deleted.')
# template_del()

@autotemplate.command(
    'edit',
    short_help='change properties of an existing template')
@click.option('cur_name', '--name', required=True, type=NAME,
              help="template's name identifier")
@click.option('name', '--newname', type=NAME,
              help="new template's name identifier")
@click.option('--content', type=AUTO_TEMPLATE, help="template content")
@click.option('--owner', help="template owner")
@click.option('--project', help="project owning template")
@click.option('operating_system', '--os', help="supported OS")
@click.option('--desc', help="free form field describing model")
def template_edit(cur_name, **kwargs):
    """
    change properties of an existing template
    """
    client = Client()
    fetch_and_update(
        client.AutoTemplates,
        {'name': cur_name},
        'template not found.',
        kwargs)
    click.echo('Item successfully updated.')
# template_edit()

@autotemplate.command(name='list')
@click.option('--name', type=NAME, help="filter by template name")
@click.option('--owner', help="filter by owner")
@click.option('--project', help="filter by project")
@click.option('operating_system', '--os', help="filter by supported OS")
def template_list(**kwargs):
    """
    list the available templates
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    parsed_filter = dict_to_filter(kwargs)
    entries = client.AutoTemplates.instances(**parsed_filter)

    # present results
    print_items(
        MODEL_FIELDS, client.AutoTemplates, None, entries)
# template_list()

@autotemplate.command(name='print')
@click.option('--name', type=NAME,
              required=True, help="template to print content")
def template_print(**kwargs):
    """
    print the content of a template
    """
    # fetch data from server
    client = Client()
    item = fetch_item(
        client.AutoTemplates,
        {'name': kwargs['name']},
        'template not found.')

    click.echo(item.content, nl=False)
# template_print()
