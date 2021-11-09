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
REST interface for Resource Manager mesh component
"""

import logging
import logging.config
import os

from .v1 import api_v1
from .. import configuration
from ..service_layer.resource_manager import ResourceManager
from flask import Flask


def create_app(config=None) -> Flask:
    """
    Create flask application
    """

    # specifying the path to the logging configuration:
    # TODO: implement a custom path
    log_conf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 '../log.conf')

    app = Flask(__name__, instance_relative_config=True)

    # setting up the logging configuration
    logging.config.fileConfig(log_conf_path)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # create common Resource Manager instance for this flask application
    resource_manager = ResourceManager(
        db_uri=configuration.TESSIA_RESOURCE_MANAGER_BD_URI
    )
    app.resource_manager = resource_manager

    # create connection to DB
    app.resource_manager.connect()

    # register routes
    app.register_blueprint(api_v1['blueprint'])

    @app.route('/')
    def status():
        return {'name': 'resource_manager',
                'apis': [
                    {key: api[key]}
                    for key in ['root', 'version', 'min_version']
                    for api in [api_v1]]
                }

    return app
# create_app()
