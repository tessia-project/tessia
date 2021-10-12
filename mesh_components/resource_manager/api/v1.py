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
Resource Manager API v1
"""

#
# IMPORTS
#

from flask import Blueprint


#
# CODE
#

api = Blueprint('v1', __name__, url_prefix='/v1')

api_v1 = {
    'blueprint': api,
    'root': '/v1',
    'min_version': '0.0.0',
    'version': '0.0.1'
}


@api.route('/')
def root():
    """
    API root

    Verify that request is authorized and succeeds
    """
    return {
        'success': True
    }


@api.route('/schema')
def schema():
    """API schema"""
    return {
        '/': 'api root'
    }
