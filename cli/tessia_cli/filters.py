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
Utilites for parsing arguments to REST filters
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
def dict_to_filter(args):
    """
    Convert a dict in the form {"field': 'value'} to a REST-type filter format

    Args:
        args (dict): dict in the form {"field': 'value'}

    Returns:
        dict: in REST-type filter format

    Raises:
        None
    """
    # TODO: add support to wildcards
    where_args = {}
    for key, value in args.items():
        if value is not None:
            where_args[key] = value

    return {'where': where_args}
# dict_to_filter()
