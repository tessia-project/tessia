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
from tessia_engine import auth
from tessia_engine.api.app import API
from tessia_engine.api.exceptions import UnauthorizedError
from tessia_engine.config import CONF
from tessia_engine.db.models import User
from tessia_engine.db.models import UserKey
# use the exception directly so that potion custom error handler can catch
# it and convert to a valid json response
from werkzeug.exceptions import BadRequest


#
# CONSTANTS AND DEFINITIONS
#
LOGIN_MANAGER = auth.get_manager()

#
# CODE
#

def _authenticate_basic(auth_value):
    """
    Basic authentication with username and password, validate against the login
    manager defined in configured file (usually LDAP)

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

    # logins should be case-insensitive
    user = user.lower()

    # user authentication with login provider failed: return unauthorized
    result = LOGIN_MANAGER.authenticate(user, passwd)
    if result is None:
        raise UnauthorizedError()

    # find user entry in database
    user_entry = User.query.filter_by(login=user).first()
    if user_entry is not None:
        return user_entry

    allow_auto_create = CONF.get_config().get(
        'auth', {}).get('allow_user_auto_create', False)
    # auto creation of users not allowed: report unauthorized
    if not allow_auto_create:
        raise UnauthorizedError(
            msg='User authenticated but not registered in database')

    # create user in database
    new_user = User()
    # important: always save login as lowercase to avoid duplicates or user
    # having to worry about entering the right case
    new_user.login = result['login'].lower()
    new_user.name = result['fullname']
    # job title is optional
    new_user.title = result.get('title', None)
    new_user.restricted = False
    new_user.admin = False
    API.db.session.add(new_user)
    API.db.session.commit()

    return new_user
# _authenticate_basic()

def _authenticate_key(auth_value):
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
    API.db.session.add(key_entry)
    API.db.session.commit()
    return key_entry.user_rel
# _authenticate_key()

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
        if auth_header is None or len(auth_header) == 0:
            raise UnauthorizedError(auth_provided=False)

        try:
            auth_scheme, auth_value = auth_header.split(None, 1)
        except ValueError:
            raise UnauthorizedError()

        auth_scheme = auth_scheme.lower()

        if auth_scheme == 'basic':
            user_entry = _authenticate_basic(auth_value)
        elif auth_scheme == 'x-key':
            user_entry = _authenticate_key(auth_value)
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
