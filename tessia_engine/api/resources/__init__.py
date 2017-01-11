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
Expose the API resources
"""

#
# IMPORTS
#
from tessia_engine.api.resources.iface_types import IfaceTypeResource
from tessia_engine.api.resources.ip_addresses import IpAddressResource
from tessia_engine.api.resources.job_requests import JobRequestResource
from tessia_engine.api.resources.jobs import JobResource
from tessia_engine.api.resources.net_zones import NetZoneResource
from tessia_engine.api.resources.projects import ProjectResource
from tessia_engine.api.resources.users import UserResource
from tessia_engine.api.resources.user_keys import UserKeyResource
from tessia_engine.api.resources.storage_servers import StorageServerResource
from tessia_engine.api.resources.storage_server_types import \
    StorageServerTypeResource
from tessia_engine.api.resources.storage_volumes import StorageVolumeResource
from tessia_engine.api.resources.subnets import SubnetResource
from tessia_engine.api.resources.system_ifaces import SystemIfaceResource
from tessia_engine.api.resources.system_models import SystemModelResource
from tessia_engine.api.resources.system_types import SystemTypeResource
from tessia_engine.api.resources.system_states import SystemStateResource
from tessia_engine.api.resources.systems import SystemResource
from tessia_engine.api.resources.system_profiles import SystemProfileResource
from tessia_engine.api.resources.volume_types import VolumeTypeResource

#
# CONSTANTS AND DEFINITIONS
#
RESOURCES = [
    IfaceTypeResource,
    IpAddressResource,
    JobRequestResource,
    JobResource,
    NetZoneResource,
    ProjectResource,
    StorageServerTypeResource,
    StorageServerResource,
    StorageVolumeResource,
    SubnetResource,
    SystemIfaceResource,
    SystemModelResource,
    SystemTypeResource,
    SystemStateResource,
    SystemResource,
    SystemProfileResource,
    UserKeyResource,
    UserResource,
    VolumeTypeResource,
]

#
# CODE
#
