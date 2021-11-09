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
default Resource Manager configuration
"""

#
# IMPORTS
#

import os

#
# CODE
#

TESSIA_RESOURCE_MANAGER_BD_USER =\
    os.environ.get("TESSIA_RESOURCE_MANAGER_BD_USER", default="tessia")

TESSIA_RESOURCE_MANAGER_BD_PASSWORD = \
    os.environ.get("TESSIA_RESOURCE_MANAGER_BD_PASSWORD")

if not TESSIA_RESOURCE_MANAGER_BD_PASSWORD:
    raise ValueError("No TESSIA_RESOURCE_MANAGER_BD_PASSWORD set")

TESSIA_RESOURCE_MANAGER_BD_PORT = \
    os.environ.get("TESSIA_RESOURCE_MANAGER_BD_PORT", default=5432)

TESSIA_RESOURCE_MANAGER_BD_HOST = \
    os.environ.get("TESSIA_RESOURCE_MANAGER_BD_HOST", default="localhost")

TESSIA_RESOURCE_MANAGER_BD_NAME = \
    os.environ.get("TESSIA_RESOURCE_MANAGER_BD_NAME",
                   default="tessia-resources")

TESSIA_RESOURCE_MANAGER_BD_URI = \
    f"postgresql://{TESSIA_RESOURCE_MANAGER_BD_USER}:" \
    f"{TESSIA_RESOURCE_MANAGER_BD_PASSWORD}" \
    f"@{TESSIA_RESOURCE_MANAGER_BD_HOST}:" \
    f"{TESSIA_RESOURCE_MANAGER_BD_PORT}/" \
    f"{TESSIA_RESOURCE_MANAGER_BD_NAME}"
