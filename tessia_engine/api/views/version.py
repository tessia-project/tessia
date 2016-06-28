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
API version verification routine
"""

#
# IMPORTS
#
from flask import request as flask_request
from tessia_engine.api.exceptions import BaseHttpError
from werkzeug.http import parse_dict_header

#
# CONSTANTS AND DEFINITIONS
#

# the current version of the api
CURRENT_API_VERSION = 20160916
# the oldest version that is backwards compatible
OLDEST_COMPAT_API_VERSION = 20160916

#
# CODE
#

def check_version():
    """
    Helper function to verify if the client expected api version is compatible
    with our current version. It does so by parsing the HTTP standard header
    'Expect' (which allows extensions, see the rfc 2616) and returning a 417 -
    "Expectation failed" when client version is not backwards compatible.

    Args:
        None

    Returns:
        None: if no expect header was provided
        str: json error response in case versions are not compatible
    """
    expect_values = parse_dict_header(flask_request.headers.get('Expect', ''))
    try:
        expect_version = int(expect_values['tessia-api-compat-version'])
    # option was specified in an invalid format: report bad request
    except (TypeError, ValueError):
        msg = ("The value for option tessia-api-compat-version in request's"
               "Expect: header is not a valid integer")
        error = BaseHttpError(400, {'message': msg, 'status': 400})
        return error.get_response()
    # no option in header was specified: nothing to verify
    except KeyError:
        pass
    # option was sucessfully retrieved and parsed
    else:
        # expected client's version is not backwards compatible with our
        # current version: return expectation failed
        if expect_version < OLDEST_COMPAT_API_VERSION:
            msg = ("Server cannot provide an answer in a backwards "
                   "compatible version")
            error = BaseHttpError(417, {'message': msg, 'status': 417})
            return error.get_response()

# check_version()

def report_version(response):
    """
    Simple helper to add the server's api version as a header in the response
    """
    response.headers['X-Tessia-Api-Version'] = CURRENT_API_VERSION
    return response
# report_version()
