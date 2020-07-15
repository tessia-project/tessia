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
Module containing the exceptions used by the db module
"""

#
# IMPORTS
#

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class AssociationError(Exception):
    """
    Error caused when a model fails to find an associated object for a given
    attribute
    """

    def __init__(
            self, model, column, associated_model, associated_column, value):
        """
        Constructor, sets internal attributes

        Args:
            model (Model): the sqlalchemy model that caused the error
            column (str): column name where error occurred
            associated_model (Model): the target model where object was not
                                      found
            associated_column (str): target's column name
            value (str): value used to perform the search query
        """
        # model where error was caused
        self.model = model
        # column in model where error was caused
        self.column = column
        # the associated model
        self.associated_model = associated_model
        # column in associated model
        self.associated_column = associated_column
        # value used in the search
        self.value = value

        super().__init__()
    # __init__()

    def __str__(self):
        """
        String representation for this error
        """
        msg = 'No row in model ({}) with ({})=({})'.format(
            self.associated_model.__name__, self.associated_column, self.value)
        return msg
    # __str__()

# AssociationError
