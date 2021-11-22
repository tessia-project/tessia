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
REST interface for Task Runner mesh component
"""

#
# IMPORTS
#

import json
import logging
import logging.config
import os

from flask import Flask
from .v1 import api_v1
from ..service_layer import ServiceLayer


#
# CONSTANTS AND DEFINITIONS
#

DEFAULT_CONFIGURATION = {
    'logging': {
        'version': 1,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
            }
        },
        'loggers': {
            'mesh-scheduler': {
                'level': 'DEBUG',
                'handlers': ['console']
            }
        }
    }
}


#
# CODE
#


def create_app(app_config=None) -> Flask:
    """
    Create flask application
    """

    config = DEFAULT_CONFIGURATION.copy()
    if app_config:
        config.update(app_config)

    # path to configuration
    conf_path = os.getenv('TASK_RUNNER_CONF')
    if conf_path:
        config.update(json.load(conf_path))

    app = Flask(__name__, instance_relative_config=True)

    # setting up the logging configuration
    logging.config.dictConfig(config['logging'])

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # create common service layer for this flask application
    app.service_layer = ServiceLayer()

    # register routes
    app.register_blueprint(api_v1['blueprint'])

    @app.route('/')
    def status():
        return {
            'name': 'task_runner',
            'apis': [{
                    key: api[key]
                    for key in ['root', 'version', 'min_version']
            } for api in [api_v1]]
        }

    return app
# create_app()
