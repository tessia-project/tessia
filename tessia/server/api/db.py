# Copyright 2018 IBM Corp.
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
Configuration of flask-sqlalchemy for use by flask app
"""

#
# IMPORTS
#
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import BASE

import flask_sqlalchemy as flask_sa

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class _AppDbManager(object):
    """
    Class to handle db object creation and configuration
    """
    _singleton = False

    def __init__(self):
        """
        Constructor, defines the variable that stores the db object instance
        as empty. The db initialization is triggered on the first time the
        variable 'db' is referenced.
        """
        self._db = None
    # __init__()

    def __new__(cls, *args, **kwargs):
        """
        Modules should not instantiate this class since there should be only
        one db entry point at a time for all modules.

        Args:
            None

        Returns:
            _AppDbManager: object instance

        Raises:
            NotImplementedError: as the class should not be instantiated
        """
        if cls._singleton:
            raise NotImplementedError('Class should not be instantiated')
        cls._singleton = True

        return super().__new__(cls, *args, **kwargs)
    # __new__()

    def _create_db(self):
        """
        Create the flask-sqlalchemy instance for db communication

        Returns:
            SQLAlchemy: instance of flask-SQLAlchemy
        """
        def patched_base(self, *args, **kwargs):
            """
            Change the flask_sqlalchemy base creator function to use our custom
            declarative base in place of the default one.
            """
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

        flask_sa.SQLAlchemy.make_declarative_base = patched_base
        flask_sa.SQLAlchemy.create_session = lambda *args, **kwargs: \
            MANAGER.session

        return flask_sa.SQLAlchemy(model_class=BASE)
    # _create_db()

    @property
    def db(self):
        """
        Return the flask-sa's db object
        """
        if self._db is not None:
            return self._db

        self._db = self._create_db()
        return self._db
    # db
# _AppDbManager

API_DB = _AppDbManager()
