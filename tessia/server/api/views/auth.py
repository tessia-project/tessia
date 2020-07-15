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
Authentication routines
"""

#
# IMPORTS
#
from base64 import b64decode
from flask import g as flask_global
from flask import request as flask_request
from sqlalchemy.sql import func
from tessia.server import auth
from tessia.server.api.db import API_DB
from tessia.server.api.exceptions import UnauthorizedError
from tessia.server.config import CONF
from tessia.server.db.models import User
from tessia.server.db.models import UserKey
# use the exception directly so that potion custom error handler can catch
# it and convert to a valid json response
from werkzeug.exceptions import BadRequest


#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class _LoginManager:

    # holds the login manager object
    _manager = None

    @classmethod
    def get_login_manager(cls):
        """
        Return the login manager object, as defined by the auth module.
        """
        if cls._manager is None:
            cls._manager = auth.get_manager()
        return cls._manager
    # get_login_manager()

    @classmethod
    def authenticate_basic(cls, auth_value):
        """
        Basic authentication with username and password, validate against the
        login manager defined in configured file (usually LDAP)

        Args:
            auth_value (str): the value part of the Authorization header
                              form username:password base64 encoded

        Raises:
            BadRequest: if value is malformed
            UnauthorizedError: if credentials are invalid

        Returns:
            User: instance of User's sqlalchemy model
        """
        try:
            # http headers are always ascii
            user, passwd = b64decode(auth_value).decode(
                'ascii').split(':', 1)
        except Exception:
            raise BadRequest()

        case_sensitive = CONF.get_config().get(
            'auth', {}).get('case_sensitive', False)
        if not case_sensitive:
            # logins should be case-insensitive
            user = user.lower()

        # user authentication with login provider failed: return unauthorized
        result = cls.get_login_manager().authenticate(user, passwd)
        if result is None:
            raise UnauthorizedError()

        # find user entry in database
        user_entry = User.query.filter_by(login=user).first()
        if user_entry is not None:
            # update db in case user information has changed
            changed = False
            if user_entry.name != result['fullname']:
                changed = True
                user_entry.name = result['fullname']
            if user_entry.title != result.get('title', None):
                changed = True
                user_entry.title = result.get('title', None)

            if changed:
                API_DB.db.session.add(user_entry)
                API_DB.db.session.commit()

            return user_entry

        allow_auto_create = CONF.get_config().get(
            'auth', {}).get('allow_user_auto_create', False)
        # auto creation of users not allowed: report unauthorized
        if not allow_auto_create:
            raise UnauthorizedError(
                msg='User authenticated but not registered in database')

        # create user in database
        new_user = User()
        if case_sensitive:
            new_user.login = result['login']
        else:
            # save login as lowercase to avoid duplicates or user having to
            # worry about entering the right case
            new_user.login = result['login'].lower()
        new_user.name = result['fullname']
        # job title is optional
        new_user.title = result.get('title', None)
        new_user.restricted = False
        new_user.admin = False
        API_DB.db.session.add(new_user)
        API_DB.db.session.commit()

        return new_user
    # authenticate_basic()

    @classmethod
    def authenticate_key(cls, auth_value):
        """
        API key-based authentication

        Args:
            auth_value (str): the value part of the Authorization header in the
                              form key_id:key_value

        Raises:
            BadRequest: if value is malformed
            UnauthorizedError: if credentials are invalid

        Returns:
            User: instance of User's sqlalchemy model
        """
        try:
            # http headers are always ascii
            key_id, key_secret = auth_value.split(':', 1)
        except Exception:
            raise BadRequest()

        key_entry = UserKey.query.filter_by(
            key_id=key_id, key_secret=key_secret).first()
        if key_entry is None:
            raise UnauthorizedError()

        key_entry.last_used = func.now()
        API_DB.db.session.add(key_entry)
        API_DB.db.session.commit()
        return key_entry.user_rel
    # authenticate_key()
# _LoginManager


def authorize(decorated_view):
    """
    A decorator view which implements authorization routine.

    Args:
        decorated_view (method): the view function to be decorated

    Returns:
        method: the authenticate wrapper containing the original view

    Raises:
        None
    """
    def authenticate(*args, **kwargs):
        """
        The wrapper that takes the authorization related actions before
        executing the actual view

        Args:
            args: packed args for the decorated view
            kwargs: packed keyargs for the decorated view

        Returns:
            any: the return value of the decorated view

        Raises:
            UnauthorizedError: if auth header is missing or invalid
        """
        # no credentials provided: reply that authorization is needed.
        # The exception takes care of providing the scheme allowed
        # via WWW-Authenticate response header
        auth_header = flask_request.headers.get('Authorization', None)
        if not auth_header:
            raise UnauthorizedError(auth_provided=False)

        try:
            auth_scheme, auth_value = auth_header.split(None, 1)
        except ValueError:
            raise UnauthorizedError()

        auth_scheme = auth_scheme.lower()

        if auth_scheme == 'basic':
            user_entry = _LoginManager.authenticate_basic(auth_value)
        elif auth_scheme == 'x-key':
            user_entry = _LoginManager.authenticate_key(auth_value)
        else:
            # scheme not supported
            raise UnauthorizedError()

        # set model as session variable
        flask_global.auth_user = user_entry

        # this might be relevant depending on the nature of the operation.
        # i.e. api key operations are only allowed after entering password
        # (basic scheme)
        flask_global.auth_method = auth_scheme

        return decorated_view(*args, **kwargs)
    # authenticate()

    return authenticate
# authorize()
