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
Custom potion db manager
"""

#
# IMPORTS
#
from flask_potion import exceptions as potion_exceptions
from flask_potion.contrib.alchemy.manager import SQLAlchemyManager
from sqlalchemy import exc as sa_exceptions
from sqlalchemy.orm import aliased
from werkzeug.exceptions import BadRequest

import logging
import re

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class ApiManager(SQLAlchemyManager):
    """
    Extend potion's manager with some features needed by the api
    """
    class DataError(potion_exceptions.PotionException):
        """
        Define a exception in potion's hierarchy to deal with the data type
        error in database.
        """
        werkzeug_exception = BadRequest

        def __init__(self, sa_exc):
            """
            Constructors, extract message from sa's exception object

            Args:
                sa_exc (DataError): sa's exception
            """
            super().__init__()

            self._logger = logging.getLogger(__name__)
            # original exception did not came from postgres: we don't know how
            # to handle it therefore return generic message
            if (not hasattr(sa_exc, 'orig') or
                    not hasattr(sa_exc.orig, 'pgcode')):
                self.msg = 'A value entered is in wrong format.'
                return

            # this re extracts the value which caused the error, the message
            # looks like:
            # ungültige Eingabesyntax für Typ macaddr: »ff:dd:cc:bb:aa«
            msg_match = re.match(r'^.*»(.*)«.*$',
                                 sa_exc.orig.diag.message_primary)
            try:
                value = msg_match.group(1)
            except (AttributeError, IndexError):
                self._logger.debug(
                    'Returning generic msg: failed to match re')
                self.msg = 'A value entered is in wrong format.'
                return

            self.msg = "The value '{}' is in wrong format.".format(value)
        # __init__()

        def as_dict(self):
            """
            Wraps original as_dict to return customized message
            """
            ret_dict = super().as_dict()
            ret_dict['message'] = self.msg
            return ret_dict
        # as_dict()
    # DataError

    def instances(self, where=None, sort=None):
        """
        Add the functionality to join tables when queries use hybrid
        attributes that point to another table via a foreign key.

        Args:
            where (list): list of SQLAlchemyBaseFilter instances
            sort (list): list containing sorting conditions

        Returns:
            sqlalchemy.orm.query: the sa's query object

        Raises:
            None
        """
        # get the model's query object
        query = self._query()

        # sanity check
        if query is None:
            return []

        # filtering condition was specified: build sqlalchemy query expression
        if where:
            expressions = []
            # each condition is an instance of SQLAlchemyBaseFilter
            for condition in where:
                # retrieve the sa object corresponding to the target column
                col = condition.filter.column
                # column points to another table: add the join condition to the
                # query.
                if (hasattr(col, 'property') and
                        col.property.expression.table.name !=
                        self.model.__tablename__):
                    # name of the attribute in the resource, corresponds to the
                    # name of the column
                    attr_name = condition.filter.attribute
                    # specify the attribute in the model containing the
                    # fk relationship definition. Here we rely on our naming
                    # convention where a hybrid column named 'foo' always has
                    # its fk relationship defined under the attribute name
                    # 'foo_rel'. This is better than trying to extract the
                    # relationship information from the column object as it
                    # would require a lot of digging because one has to provide
                    # both target and dependent columns to the join() method,
                    # i.e. join(DepTable.type_id == Target.id)
                    query = query.join(attr_name + '_rel')

                # special case parent/child for systems
                elif (self.model.__tablename__ == 'systems' and
                      condition.filter.attribute == 'hypervisor'):
                    parent = aliased(self.model)
                    query = query.join(
                        parent, 'hypervisor_rel')
                    query = query.filter(parent.name == condition.value)
                    continue

                # special case parent/child for system profiles
                elif (self.model.__tablename__ == 'system_profiles' and
                      condition.filter.attribute == 'hypervisor_profile'):
                    # TODO: handle the case when user specifies
                    # hypervisor-name/profile-name
                    parent = aliased(self.model)
                    query = query.join(
                        parent, 'hypervisor_profile_rel')
                    query = query.filter(parent.name == condition.value)
                    continue

                # add the comparison expression (the filter itself)
                expressions.append(self._expression_for_condition(condition))

            # more than one expression specified: build the final statement
            if expressions:
                query = self._query_filter(
                    query, self._and_expression(expressions))

        # sort field(s) specified: add join to the fk fields as needed
        if sort:
            for _, attribute, _ in sort:
                column = getattr(self.model, attribute)
                if (hasattr(column, 'property') and
                        column.property.expression.table.name !=
                        self.model.__tablename__):
                    query = query.join(attribute + '_rel')
                # special case parent/child for systems
                elif (self.model.__tablename__ == 'systems' and
                      attribute == 'hypervisor'):
                    parent = aliased(self.model)
                    query = query.join(parent, 'hypervisor_rel')
                    query = query.filter(parent.id == self.model.hypervisor_id)
                # special case parent/child for system profiles
                elif (self.model.__tablename__ == 'system_profiles' and
                      attribute == 'hypervisor_profile'):
                    parent = aliased(self.model)
                    query = query.join(parent, 'hypervisor_profile_rel')
                    query = query.filter(
                        parent.id == self.model.hypervisor_profile_id)

            query = self._query_order_by(query, sort)

        return query
    # instances()

    def create(self, properties, commit=True):
        """
        Fix the create method which is not catching sa's exception for error in
        data format.

        Args:
            properties (dict): properties for the created item
            commit (bool): commit session

        Returns:
            any: whatever parent's create returns

        Raises:
            ApiManager.DataError: in case a data error occurs (i.e. mac address
                                  in wrong format)
            BackendConflict: database could not perform an operation due to
                             data conflicts
        """
        try:
            return super().create(properties, commit=commit)
        except sa_exceptions.DataError as sa_exc:
            session = self._get_session()
            session.rollback()
            raise ApiManager.DataError(sa_exc)
        except sa_exceptions.IntegrityError:
            session = self._get_session()
            session.rollback()
            raise potion_exceptions.BackendConflict()
    # create()

    def delete(self, item, commit=True):
        """
        Fix the delete method which is not cleaning up the session after a
        failed operation

        Args:
            item (dict): item to delete
            commit (bool): commit session

        Returns:
            any: whatever parent's delete returns (as of today, None)

        Raises:
            BackendConflict: in case a integrity error occurs (i.e. FK
                             depending on item to delete)
        """
        try:
            return super().delete(item, commit=commit)
        except sa_exceptions.IntegrityError:
            session = self._get_session()
            session.rollback()
            raise potion_exceptions.BackendConflict()
    # delete()

    def update(self, item, changes, commit=True):
        """
        Fix the update method which is not catching sa's exception for error in
        data format.

        Args:
            item (dict): item to update
            changes (dict): changes to apply
            commit (bool): commit session

        Returns:
            any: whatever parent's update returns

        Raises:
            ApiManager.DataError: in case a data error occurs (i.e. mac address
                                  in wrong format)
            BackendConflict: database could not perform an operation due to
                             data conflicts
        """
        try:
            return super().update(item, changes, commit=commit)
        except sa_exceptions.DataError as sa_exc:
            session = self._get_session()
            session.rollback()
            raise ApiManager.DataError(sa_exc)
        except sa_exceptions.IntegrityError:
            session = self._get_session()
            session.rollback()
            raise potion_exceptions.BackendConflict()
    # update()
# ApiManager
