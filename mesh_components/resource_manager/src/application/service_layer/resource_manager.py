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
Resource Manager mesh component
"""

#
# IMPORTS
#
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

#
# CONSTANTS AND DEFINITIONS
#

# Current version of the component
CURRENT_VERSION = "0.0.1"

# Default configuration
DEFAULT_CONFIGURATION = {

}

#
# CODE
#


class ResourceManager:
    """
    Resource Manager

    Provides resource management
    """

    def __init__(self, db_uri: str) -> None:
        self.version = CURRENT_VERSION
        self._db_uri = db_uri
        self._db = None
        self._conn = None
        self._logger = logging.getLogger("logger_common")
    # __init__()

    def _create_db(self):
        """ Not implemented yet """
    # _create_db()

    def connect(self) -> tuple:
        """
       Create a SQLAlchemy engine and a session instances.

        Args:
            None

        Returns:
            tuple: (sqlalchemy.engine.Engine, sqlalchemy.orm.session.Session)

        """
        if self._conn is not None:
            return self._conn

        engine = create_engine(self._db_uri, echo=True)
        self._logger.debug("SQLAlchemy engine was has been created: {}".format(
            engine))

        session = scoped_session(sessionmaker(bind=engine))

        self._conn = (engine, session)
        return self._conn
    # connect()
# ResourceManager
