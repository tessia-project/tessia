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
Initialization of API objects
"""

#
# IMPORTS
#
from flask import Flask
from flask_potion import Api
from flask_potion import exceptions as potion_exceptions
from tessia.server.config import CONF
from tessia.server.api import exceptions as api_exceptions
from tessia.server.api.db import API_DB
from tessia.server.api.manager import ApiManager
from tessia.server.api.resources import RESOURCES
from tessia.server.api.views import version
from tessia.server.api.views.auth import authorize
from tessia.server.db.connection import MANAGER

import logging

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class _AppManager(object):
    """
    Class to handle app creation and configuration
    """
    _singleton = False

    def __init__(self):
        """
        Constructor, defines the variable that stores the app object instance
        as empty. The app creation is triggered on the first time the variable
        'app' is referenced.
        """
        self._app = None
    # __init__()

    def __new__(cls, *args, **kwargs):
        """
        Modules should not instantiate this class since there should be only
        one app instance at a time for all modules.

        Args:
            None

        Returns:
            _AppManager: object instance

        Raises:
            NotImplementedError: as the class should not be instantiated
        """
        if cls._singleton:
            raise NotImplementedError('Class should not be instantiated')
        cls._singleton = True

        return super().__new__(cls, *args, **kwargs)
    # __new__()

    def _configure(self):
        """
        Perform all necessary configuration steps to prepare the rest api.
        """
        if self._app is not None:
            return

        # create the flask app instance
        app = self._create_app()

        # initialize the flask-sa object
        self._init_db(app)

        # create the api entry points
        self._create_api(app)

        self._app = app
    # _configure()

    def _create_api(self, app):
        """
        Customize the flask app and add the api resources

        Args:
            app (Flask): flask object

        Returns:
            flask_potion.Api: potion api instance

        Raises:
            RuntimeError: in case a resource is missing mandatory attribute
        """
        # version verification routine when defined by the client in headers
        app.before_request(version.check_version)
        # add the api version header on each response
        app.after_request(version.report_version)

        # patch the potion error handler for the following reasons:
        # - to log some exceptions to get traceback data
        # - to catch our custom exceptions so that any exception derived from
        # BaseHttpError raised by our views will have get_response() called
        # to generate the response in json format
        logger = logging.getLogger(__name__)
        _orig_exception_handler = Api._exception_handler
        def _exception_handler(self, original_handler, e):
            """
            Wrapper for the original potion exception handler
            """
            # pylint: disable=invalid-name
            if isinstance(e, api_exceptions.BaseHttpError):
                # conflicts are logged to get useful information
                if isinstance(e, api_exceptions.ConflictError):
                    logger.warning(
                        'A conflict exception occurred, info:', exc_info=True)
                # integrity errors might need to be checked so we log them
                elif isinstance(e, api_exceptions.IntegrityError):
                    logger.warning(
                        'An integrity exception occurred, info:',
                        exc_info=True)

                return e.get_response()

            # all potion exceptions are logged
            if isinstance(e, potion_exceptions.PotionException):
                logger.warning('A potion exception occurred, info:',
                               exc_info=True)

            # potion's original handler
            return _orig_exception_handler(self, original_handler, e)
        # _exception_handler()
        Api._exception_handler = _exception_handler

        # log requests in debug mode
        if app.config['DEBUG'] is True:
            from flask import request
            def log_request_info():
                """Helper to log headers and body from requests"""
                app.logger.debug('Headers: %s', request.headers)
                app.logger.debug('Body: %s', request.get_data())
            # log_request_info()
            app.before_request(log_request_info)

        # create the api instance and:
        # - use a decorator to force authentication on
        # each request and well as the api custom db manager
        app.config['POTION_DECORATE_SCHEMA_ENDPOINTS'] = False
        api = Api(app, decorators=[authorize], default_manager=ApiManager)
        app.config['POTION_DEFAULT_PER_PAGE'] = 50
        app.config['POTION_MAX_PER_PAGE'] = 100

        # add each resource
        for resource in RESOURCES:
            # sanity check: make sure some custom parameters are present as
            # they are used by us and not checked by potion
            for attr in ('title', 'description', 'human_identifiers'):
                if not hasattr(resource.Meta, attr):
                    raise RuntimeError("{} missing attribute '{}'".format(
                        resource.__name__, attr))
            api.add_resource(resource)

        return api
    # _create_api()

    @staticmethod
    def _create_app():
        """
        Create a flask app instance

        Args:
            None

        Returns:
            Flask: flask object
        """
        app = Flask('tessia.server')

        conf = CONF.get_config()
        # any flask configuration can be managed from the config file
        app.config.from_object(conf.get('flask', {}))

        return app
    # _create_app()

    @staticmethod
    def _init_db(app):
        """
        Init the app in the flask-sqlalchemy instance for db communication

        Args:
            app (Flask): flask object
        """
        app.config['SQLALCHEMY_DATABASE_URI'] = MANAGER.engine.url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        API_DB.db.init_app(app)
    # _init_db()

    @property
    def app(self):
        """
        Return the flask's application instance
        """
        self._configure()
        return self._app
    # app

    def reset(self):
        """
        Force recreation of app and db objects. This method is primarily
        targeted for unit tests.
        """
        self._app = None
        API_DB._db = None
        # the potion resource might be tied to a previous instance so we remove
        # the association
        for resource in RESOURCES:
            resource.api = None
    # reset()
# _AppManager

API = _AppManager()
