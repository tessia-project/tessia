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
Provide database connection via sqlalchemy
"""

#
# IMPORTS
#
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from tessia.server.config import CONF
from tessia.server.db.models import BASE


#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class _DbManager:
    """
    Class to handle db connection and session creation for all modules
    """
    _counter = 0

    def __init__(self):
        """
        Constructor, defines the variable that stores the engine and session
        instances as empty. The connection to the db is triggered on the first
        time one of the variables engine or session is referenced.
        """
        self._conn = None
    # __init__()

    def __new__(cls, *args, **kwargs):
        """
        Modules should not instantiate this class since db connection is the
        same for all modules and we want a single access point to db session.

        Args:
            None

        Returns:
            _Dbmanager: object instance

        Raises:
            NotImplementedError: as the class should not be instantiated
        """
        if cls._counter == 1:
            raise NotImplementedError('Class should not be instantiated')
        cls._counter = 1

        return super().__new__(cls, *args, **kwargs)
    # __new__()

    @property
    def engine(self):
        """
        Return the sqlalchemy's engine instance
        """
        self.connect()
        return self._conn[0]

    @property
    def session(self):
        """
        Return the sqlalchemy's session instance
        """
        self.connect()
        return self._conn[1]

    def connect(self):
        """
        Read the db connection parameters from the configuration file and
        create an engine instance and a scoped session factory. Scoped session
        automatically provides the same session object to calls made in the
        same thread.

        Args:
            None

        Returns:
            tuple: (sqlalchemy.engine.Engine, sqlalchemy.orm.session.Session)

        Raises:
            RuntimeError: in case db config is missing
        """
        if self._conn is not None:
            return self._conn

        try:
            db_url = CONF.get_config().get('db')['url']
        except (TypeError, KeyError):
            raise RuntimeError('No database configuration found')

        engine = create_engine(db_url)
        session = scoped_session(sessionmaker(bind=engine))

        # patch the models base to provide a convenient query attribute
        # this is similar to what flask-sqlalchemy does
        for class_entry in BASE._decl_class_registry.values():
            if isinstance(class_entry, type):
                if not hasattr(class_entry, 'query_class'):
                    class_entry.query = session.query_property()

        self._conn = (engine, session)
        return self._conn
    # connect()
# _DbManager


MANAGER = _DbManager()
