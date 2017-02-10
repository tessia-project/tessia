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
Module for the model (system models) commands
"""

#
# IMPORTS
#
from tessia_cli.client import Client
from tessia_cli.output import print_items
from tessia_cli.utils import fetch_and_delete
from tessia_cli.utils import fetch_and_update

import click

#
# CONSTANTS AND DEFINITIONS
#
MODEL_FIELDS = (
    'name', 'arch', 'model', 'submodel', 'desc'
)

#
# CODE
#

@click.command('model-add')
@click.option('--name', required=True, help="model's name identifier")
@click.option('model', '--title', required=True, help="model's title")
@click.option('--arch', required=True, help="architecture (i.e. s390x)")
@click.option('--submodel', help="model's sub-classification")
@click.option('--desc', help="free form field describing model")
def model_add(**kwargs):
    """
    add a new system model (admin only)
    """
    client = Client()

    item = client.SystemModels()
    for key, value in kwargs.items():
        setattr(item, key, value)
    item.save()

    click.echo('Item added successfully.')
# model_add()

@click.command(name='model-del')
@click.option('--name', required=True, help="model to delete")
def model_del(name):
    """
    remove an existing system model (admin only)
    """
    client = Client()

    fetch_and_delete(
        client.SystemModels, {'name': name}, 'model not found.')
    click.echo('Item successfully deleted.')
# model_del()

@click.command(
    'model-edit',
    short_help='change properties of an existing system model (admin only)')
@click.option('cur_name', '--name', required=True,
              help="model's name identifier")
@click.option('name', '--newname', help="new model's name identifier")
@click.option('model', '--title', help="model's title")
@click.option('--arch', help="architecture (i.e. s390x)")
@click.option('--submodel', help="model's sub-classification")
@click.option('--desc', help="free form field describing model")
def model_edit(cur_name, **kwargs):
    """
    change properties of an existing system model (admin only)
    """
    client = Client()
    fetch_and_update(
        client.SystemModels,
        {'name': cur_name},
        'model not found.',
        kwargs)
    click.echo('Item successfully updated.')

# model_edit()

@click.command(name='model-list')
def model_list():
    """
    list the supported system models
    """
    # fetch data from server
    client = Client()

    # parse parameters to filters
    entries = client.SystemModels.instances()

    # present results
    print_items(
        MODEL_FIELDS, client.SystemModels, None, entries)
# model_list()

CMDS = [model_add, model_del, model_edit, model_list]
