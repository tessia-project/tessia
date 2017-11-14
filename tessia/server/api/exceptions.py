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
API exceptions raised by the views
"""

#
# IMPORTS
#
from flask import jsonify
from tessia.server.config import CONF

import logging
import re

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#
class BaseHttpError(Exception):
    """
    Base error which provides functionality to return a flask response object
    """
    def __init__(self, code=500, body=None, msg=None, headers=None):
        """
        Constructor.

        Args:
            code (int): http error code
            body (str): content for response body
            msg (str): error message error in response body
            headers (dict): response headers
        """
        self.code = code

        if headers is not None:
            self.headers = headers
        else:
            self.headers = {}

        if body is None:
            if msg is None:
                msg = 'Internal server error'
            self.body = {
                'message': msg,
                'status': self.code,
            }
        else:
            self.body = body

        super().__init__()
    # __init__()

    def get_response(self):
        """
        Return a flask Response object based on the defined attributes

        Returns:
            flask.Response: a flask response object
        """
        resp = jsonify(self.body)
        resp.status_code = self.code
        for key, value in self.headers.items():
            resp.headers.add(key, value)
        return resp
    # get_response()

# BaseHttpError

class ConflictError(BaseHttpError):
    """
    Error used when duplicated entries are attempted (i.e. two systems with
    same name)
    """
    GENERIC_MSG = 'An item with the provided value(s) already exists'
    PRECISE_MSG = "An item with the value(s) '{}' already exists"

    def __init__(self, potion_exc, resource, headers=None):
        """
        Constructor.

        Args:
            potion_exc (PotionException): the original exception to extract
                                          data from
            resource (Resource): potion resource to extract field description
            headers (dict): optional response headers
        """
        self._logger = logging.getLogger(__name__)
        self.potion_exc = potion_exc
        self.resource = resource

        code = 409
        message = self._build_msg()
        body = {'message': message, 'status': code}

        super().__init__(code=code, body=body, headers=headers)
    # __init__()

    def _build_msg(self):
        """
        Extract information from the original exception to build the error
        message.

        Args:
            None

        Returns:
            str: message to be returned in response body
        """
        # no schema available in resource: not possible to parse error
        # information therefore just report generic message
        if not hasattr(self.resource, 'Schema'):
            self._logger.debug(
                'Returning generic msg: no schema available in resource')
            return self.GENERIC_MSG

        # try to access the underlying sqlalchemy exception
        # explicit chained exception used: retrieve underlying sqlalchemy
        # exception from it
        if self.potion_exc.__cause__ is not None:
            sa_exc = self.potion_exc.__cause__
        # implicit chained exception used: retrieve underlying sqlalchemy
        # exception from it
        elif self.potion_exc.__context__ is not None:
            sa_exc = self.potion_exc.__context__
        # could not determine underlying exception: return generic message
        else:
            self._logger.debug(
                'Returning generic msg: no underlying exception available')
            return self.GENERIC_MSG

        # original exception did not came from postgres: we don't know how
        # to handle it therefore return generic message
        if not hasattr(sa_exc, 'orig') or not hasattr(sa_exc.orig, 'pgcode'):
            self._logger.debug(
                'Returning generic msg: exception is not from postgres')
            return self.GENERIC_MSG

        # this complicated re is to extract the column name and the attempted
        # value which caused the error. The error message looks like:
        # Schlüssel »(name)=(Server_test_4)« existiert bereits
        # or in case of multiple keys:
        # Schlüssel »(volume_id, server_id)=(xxxxxxx, 7)« existiert bereits
        msg_match = re.match(
            r'^.*»\((.*)\)=\((.*)\)«.*$', sa_exc.orig.diag.message_detail)
        try:
            fields = msg_match.group(1).split(',')
            values = msg_match.group(2).split(',')
        except (AttributeError, IndexError):
            self._logger.debug(
                'Returning generic msg: failed to match re')
            return self.GENERIC_MSG

        # retrieve the offended item
        query_filters = {k.strip(): v.strip() for k, v in zip(fields, values)}
        conflict_item = self.resource.Meta.model.query.filter_by(
            **query_filters).one_or_none()
        # offended item not found: should never happen but in an unpredicted
        # case we show the generic message
        if conflict_item is None:
            self._logger.debug(
                'Returning generic msg: failed to find conflicting item')
            return self.GENERIC_MSG

        # build the error message by combining the human description from
        # resource's schema with values from offended item
        item_desc = []
        try:
            for field in self.resource.Meta.human_identifiers:
                schema_field = getattr(self.resource.Schema, field)
                field_desc = schema_field.description
                item_desc.append('{}={}'.format(
                    field_desc, getattr(conflict_item, field)))
        # in case the human identifier do not match a field on the item
        except AttributeError:
            self._logger.debug(
                'Returning generic msg: failed to match human identifier '
                'with item')
            return self.GENERIC_MSG

        conflict_msg = ', '.join(item_desc)

        return self.PRECISE_MSG.format(conflict_msg)
    # _build_msg()

# ConflictError

class IntegrityError(BaseHttpError):
    """
    Error used when an integrity violation occurs (i.e. attempt to delete a row
    which is referenced via foreign key in another table)
    """
    GENERIC_MSG = ('An item of different type depends on this item, remove '
                   'the dependency first.')
    PRECISE_MSG = (
        "An item of type {} with value(s) '{}' depends on this item, remove "
        "the dependency first.")

    def __init__(self, potion_exc, resource, headers=None):
        """
        Constructor

        Args:
            potion_exc (PotionException): the original exception to extract
                                          data from
            resource (Resource): potion resource to extract field description
            headers (dict): optional response headers
        """
        self._logger = logging.getLogger(__name__)
        self.potion_exc = potion_exc
        self.resource = resource

        code = 409
        message = self._build_msg()
        body = {'message': message, 'status': code}

        super().__init__(code=code, body=body, headers=headers)
    # __init__()

    def _build_msg(self):
        """
        Extract information from the sqlalchemy exception to build the error
        message

        Args:
            None

        Returns:
            str: the error message to be used in response body
        """
        # no schema available in resource: not possible to parse error
        # information therefore just report generic message
        if not hasattr(self.resource, 'Schema'):
            self._logger.debug(
                'Returning generic msg: no schema available in resource')
            return self.GENERIC_MSG

        # try to access the underlying sqlalchemy exception
        # explicit chained exception used: retrieve underlying sqlalchemy
        # exception from it
        if self.potion_exc.__cause__ is not None:
            sa_exc = self.potion_exc.__cause__
        # implicit chained exception used: retrieve underlying sqlalchemy
        # exception from it
        elif self.potion_exc.__context__ is not None:
            sa_exc = self.potion_exc.__context__
        # could not determine underlying exception: return generic message
        else:
            self._logger.debug(
                'Returning generic msg: no underlying exception available')
            return self.GENERIC_MSG

        # original exception did not came from postgres: we don't know how
        # to handle it therefore return generic message
        if not hasattr(sa_exc, 'orig') or not hasattr(sa_exc.orig, 'pgcode'):
            self._logger.debug(
                'Returning generic msg: exception is not from postgres')
            return self.GENERIC_MSG

        # this complicated re is to extract the key/value of the item that
        # caused the error and the dependent table, the message looks like:
        # Auf Schlüssel (id)=(558) wird noch aus Tabelle »subnets« verwiesen.
        msg_match = re.match(r'^.*\((.*)\)=\((.*)\).*»(.*)«.*$',
                             sa_exc.orig.diag.message_detail)
        try:
            target_col_name = msg_match.group(1)
            target_value = msg_match.group(2)
            dep_table = msg_match.group(3)
        except (AttributeError, IndexError):
            self._logger.debug(
                'Returning generic msg: failed to match re')
            return self.GENERIC_MSG

        # find the corresponding resource by matching table name with model
        dep_resource = None
        for check_res in self.resource.api.resources.values():
            if check_res.Meta.model.__tablename__ == dep_table:
                dep_resource = check_res
                break
        if dep_resource is None:
            self._logger.debug(
                'Returning generic msg: failed to find dependent resource')
            return self.GENERIC_MSG

        dep_model = dep_resource.Meta.model

        # find out which field in the dependent table carries the foreign key
        dep_column = None
        target_col_obj = getattr(self.resource.Meta.model, target_col_name)
        for check_column in dep_model.__table__.columns:
            if check_column.references(target_col_obj):
                dep_column = check_column
                break
        # no column references the target column: should never happen but in an
        # unpredicted scenario we show a generic message
        if dep_column is None:
            self._logger.debug(
                'Returning generic msg: failed to determine column '
                'holding foreign key')
            return self.GENERIC_MSG

        # now we know the dependent column and can perform a query to get one
        # dependent item
        dep_item = dep_model.query.filter(
            dep_column == target_value).limit(1).one_or_none()
        # dependent item not found: should never happen but in an unpredicted
        # case we show the generic message
        if dep_item is None:
            self._logger.debug(
                'Returning generic msg: failed to find dependent item')
            return self.GENERIC_MSG

        # build the error message by combining the human description from
        # dependent resource's schema with its values
        item_desc = []
        try:
            for field in dep_resource.Meta.human_identifiers:
                schema_field = getattr(dep_resource.Schema, field)
                field_desc = schema_field.description
                item_desc.append('{}={}'.format(
                    field_desc, getattr(dep_item, field)))
        # in case the human identifier do not match a field on the item
        except AttributeError:
            self._logger.debug(
                'Returning generic msg: failed to match human identifier '
                'with item')
            return self.GENERIC_MSG

        error_msg = ', '.join(item_desc)

        return self.PRECISE_MSG.format(dep_resource.Meta.title, error_msg)
    # _build_msg()

# IntegrityError

class ItemNotFoundError(BaseHttpError):
    """
    Error used when some expected row was not found in database
    """
    MSG = "No associated item found with value '{}' for field '{}'"

    def __init__(self, column, value, resource, headers=None):
        """
        Constructor.

        Args:
            column (str): column in dependent table
            value (str): value attempted without corresponding item
            resource (Resource): potion resource to extract field description
            headers (dict): optional response headers
        """
        # unprocessable entity
        code = 422

        # schema provided: extract description for column name
        if hasattr(resource, 'Schema') and hasattr(resource.Schema, column):
            schema_field = getattr(resource.Schema, column)
            desc = schema_field.description
        else:
            desc = column
        message = self.MSG.format(value, desc)

        body = {'message': message, 'status': code}

        super().__init__(code=code, body=body, headers=headers)
    # __init__()

# ItemNotFoundError

class UnauthorizedError(BaseHttpError):
    """
    Implement the message and headers for the 401 Unauthorized response
    """
    # we allow two authentication schemes:
    # 1- the well known basic authentication, which is safe while used under
    # SSL. This is to allow usage in the browser (perhaps more useful for
    # debugging) and makes implementation of UIs easier too (the UI just needs
    # to keep the header on all requests, instead of having to generate a key
    # which would need to be deleted at user logout).
    # 2- our own scheme based on an API key. The user generates an API key and
    # uses it instead of the username/password. This is a common approach to
    # Rest APIs implementation.
    HEADERS = {
        'WWW-Authenticate':
            'Basic realm="{0}", X-Key realm="{0}"'
    }

    def __init__(self, auth_provided=True, msg=None):
        """
        Constructor

        Args:
            auth_provided (bool): whether the request had authorization header
            msg (str): custom error message
        """
        code = 401
        if msg is None:
            # header provided: explain it was invalid
            if auth_provided:
                msg = (
                    'The credentials provided are either invalid or in the '
                    'wrong format. Verify your credentials or refer to the '
                    'API documentation for the accepted authentication '
                    'methods.'
                )
            # no Authorization: demand credentials
            else:
                msg = ('You need to provide credentials to access this '
                       'resource.')

        body = {
            'message': msg,
            'status': code,
        }

        try:
            auth_realm = CONF.get_config()['auth']['realm']
        except KeyError:
            logger = logging.getLogger(__name__)
            logger.warning(
                'authorization realm name (auth/realm) missing from config '
                'file, using default value instead')
            auth_realm = 'auth-realm'
        self.HEADERS['WWW-Authenticate'].format(auth_realm)
        super().__init__(code=code, body=body, headers=self.HEADERS)
    # __init__()

# UnauthorizedError
