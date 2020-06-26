# Copyright 2020 IBM Corp.
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
Module that helps mediating transient data between components
"""

#
# IMPORTS
#
from tessia.server.config import CONF
from redis import exceptions as RedisExceptions

import logging
import redis

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class _Mediator(object):
    """
    Mediator class for key-value data exchange backed by a redis server
    """
    _mediator_uri = None

    def __init__(self):
        """
        Constructor, defines the variable that stores the engine and session
        instances as empty. The connection to the db is triggered on the first
        time one of the variables engine or session is referenced.
        """
        self._conn = None
    # __init__()

    def _verify_connection(self):
        """
        Ping redis server to see if connection is still alive,
        and recreate it if not

        Raises:
            RuntimeError: on missing connection configuration
        """
        if self._conn:
            try:
                self._conn.ping()
            except RedisExceptions.ConnectionError:
                self._conn = None
            except RedisExceptions.TimeoutError:
                self._conn = None

        if not self._conn:
            if not self._mediator_uri:
                config_dict = CONF.get_config()
                try:
                    redis_url = config_dict['mediator']['url']
                except KeyError:
                    raise RuntimeError('No mediator configuration found')
            else:
                redis_url = self._mediator_uri
            logging.debug("Connecting to redis at %s", redis_url)

            self._conn = redis.from_url(redis_url)
    # _verify_connection()

    def _decode(self, binary):
        """
        Decode an object that may have bytes value.

        Bytes are decoded directly to strings, lists and dicts are
        recursively processed

        Args:
            binary (Union[bytes,str,list,dict]): a 'bytes' string,
                list or dict that may contain those

        Returns:
            Union[str,list,dict]: a decoded object
        """
        if isinstance(binary, bytes):
            return binary.decode("utf-8")
        elif isinstance(binary, list):
            return [self._decode(item) for item in binary]
        elif isinstance(binary, dict):
            return dict([(self._decode(key), self._decode(value)) for
                         key, value in binary.items()])

        return binary
    # _decode()

    def _flushdb(self):
        """
        Clear the database
        """
        self._verify_connection()
        self._conn.flushdb()
    # _flushdb()

    def get(self, key):
        """
        Retrieve a value by key

        Args:
            key (str): string identifier

        Returns:
            Union[str,dict,list,None]: retrieved value

        Raises:
            ValueError: when stored value type is none of the above
        """
        self._verify_connection()
        value_type = self._conn.type(key).decode('utf-8')
        if value_type == 'string':
            return self._decode(self._conn.get(key))
        elif value_type == 'hash':
            return self._decode(self._conn.hgetall(key))
        elif value_type == 'list':
            return self._decode(self._conn.lrange(key, 0, -1))
        elif value_type == 'none':
            return None

        raise ValueError("Key " + repr(key) + " has unsupported value type " +
                         value_type)
    # get()

    def set(self, key, value, expire=None):
        """
        Set a value by key with a possible expiration timeout

        Args:
            key (str): identifier
            value (Union[str,list,dict]): value to store
            expire (int): time in seconds for data expiration
        """
        self._verify_connection()

        if isinstance(value, dict):
            self._conn.delete(key)
            self._conn.hset(key, mapping=value)
            if expire:
                self._conn.expire(key, expire)
        elif isinstance(value, list):
            self._conn.delete(key)
            self._conn.rpush(key, *value)
            if expire:
                self._conn.expire(key, expire)
        elif value is None:
            self._conn.delete(key)
        else:
            self._conn.set(key, value, ex=expire)
    # set()

# _Mediator()

MEDIATOR = _Mediator()
