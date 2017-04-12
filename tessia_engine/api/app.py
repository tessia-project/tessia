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
Configuration of API objects
"""

#
# IMPORTS
#
from flask import Flask
from flask_potion import Api
from flask_potion import exceptions as potion_exceptions
from tessia_engine.config import CONF
from tessia_engine.db.connection import MANAGER
from tessia_engine.db.models import BASE

# used by potion to connect the Resources with the Models
import flask_sqlalchemy as flask_sa
import logging

#
# CONSTANTS AND DEFINITIONS
#

# the current version of the api
CURRENT_API_VERSION = 20160916
# the oldest version that is backwards compatible
OLDEST_COMPAT_API_VERSION = 20160916

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
        Constructor, defines the variable that stores the app and db objects
        instances as empty. The app creation and db configuration are triggered
        on the first time one of the variables app or db is referenced.
        """
        self._api = None
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
        if self._api is not None:
            return

        # create the flask app instance
        app = self._create_app()

        # create the flask-sa object
        database = self._create_db(app)

        # create the api entry points
        self._create_api(app)

        self._api = (app, database)
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
        # pylint: disable=protected-access
        # these imports are made here to avoid circular import problems
        from tessia_engine.api.manager import ApiManager
        from tessia_engine.api.resources import RESOURCES
        from tessia_engine.api.views.auth import authorize
        from tessia_engine.api.views import version
        from tessia_engine.api import exceptions as api_exceptions

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
        app = Flask('tessia_engine')

        conf = CONF.get_config()
        # any flask configuration can be managed from the config file
        app.config.from_object(conf.get('flask', {}))

        return app
    # _create_app()

    def _create_db(self, app):
        """
        Create the flask-sqlalchemy instance for db communication

        Args:
            app (Flask): flask object

        Returns:
            SQLAlchemy: instance of flask-SQLAlchemy

        Raises:
            RuntimeError: in case db url is not found in cfg file
        """
        def patched_base(self, *args, **kwargs):
            """
            Change the flask_sqlalchemy base creator function to use our custom
            declarative base in place of the default one.
            """
            # pylint: disable=protected-access
            # add our base to the query property of each model we have
            # in case a query property was already added by the db.connection
            # module it will be overriden here, which is ok because the
            # flask_sa implementation just add a few bits more like pagination
            for cls_model in BASE._decl_class_registry.values():
                if isinstance(cls_model, type):
                    cls_model.query_class = flask_sa.BaseQuery
                    cls_model.query = flask_sa._QueryProperty(self)

            # return our base as the base to be used by flask-sa
            return BASE
        # patched_base()

        config_dict = CONF.get_config()
        try:
            db_url = config_dict['db']['url']
        except KeyError:
            raise RuntimeError('No database configuration found')
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        flask_sa.SQLAlchemy.make_declarative_base = patched_base
        flask_sa.SQLAlchemy.create_session = lambda *args, **kwargs: \
            MANAGER.session

        return flask_sa.SQLAlchemy(app, model_class=BASE)
    # _create_db()

    @property
    def app(self):
        """
        Return the flask's application instance
        """
        self._configure()
        return self._api[0]

    @property
    def db(self):
        """
        Return the flask-sa's db object
        """
        self._configure()
        return self._api[1]

# _AppManager

API = _AppManager()
