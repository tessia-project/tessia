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
REST interface for Permission Manager mesh component
"""

import os
from logging.config import dictConfig as logDictConfig

from flask import Flask
from .v1 import api_v1
from ..permission_manager import PermissionManager

DEFAULT_API_CONFIGURATION = {
    'logging': {
        'version': 1,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
            }
        },
        'loggers': {
            'mesh-permission-manager': {
                'level': 'DEBUG',
                'handlers': ['console']
            }
        }
    },
    'permission_manager': None,
    'request_authorization': None,
}


def set_logging(log_config):
    """
    Setup logging facilities
    """
    logDictConfig(log_config)
# set_logging()


def create_app(config=None) -> Flask:
    """
    Create flask application
    """

    app = Flask(__name__, instance_relative_config=True)

    if config:
        app.config.from_json(config)
    else:
        app.config.from_mapping(DEFAULT_API_CONFIGURATION)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    set_logging(app.config.get(
        'logging', DEFAULT_API_CONFIGURATION['logging']))

    # Create common Permission Manager instance for this flask application
    permission_manager = PermissionManager()
    permission_manager.apply_config(app.config.get('permission_manager'))
    app.permission_manager = permission_manager

    # register routes
    app.register_blueprint(api_v1['blueprint'])

    @app.route('/')
    def status():
        return {'name': 'permission_manager',
                'apis': [
                    {key: api[key]}
                    for key in ['root', 'version', 'min_version']
                    for api in [api_v1]]
                }

    return app
# create_app()
