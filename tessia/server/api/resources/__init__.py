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
from tessia.server.api.resources.auto_templates import AutoTemplateResource
from tessia.server.api.resources.hmc_canary import HMCCanaryResource
from tessia.server.api.resources.iface_types import IfaceTypeResource
from tessia.server.api.resources.ip_addresses import IpAddressResource
from tessia.server.api.resources.job_requests import JobRequestResource
from tessia.server.api.resources.jobs import JobResource
from tessia.server.api.resources.net_zones import NetZoneResource
from tessia.server.api.resources.projects import ProjectResource
from tessia.server.api.resources.users import UserResource
from tessia.server.api.resources.user_keys import UserKeyResource
from tessia.server.api.resources.roles import RoleResource
from tessia.server.api.resources.user_roles import UserRoleResource
from tessia.server.api.resources.storage_servers import StorageServerResource
from tessia.server.api.resources.storage_server_types import \
    StorageServerTypeResource
from tessia.server.api.resources.storage_volumes import StorageVolumeResource
from tessia.server.api.resources.subnets import SubnetResource
from tessia.server.api.resources.system_ifaces import SystemIfaceResource
from tessia.server.api.resources.system_models import SystemModelResource
from tessia.server.api.resources.system_types import SystemTypeResource
from tessia.server.api.resources.system_states import SystemStateResource
from tessia.server.api.resources.systems import SystemResource
from tessia.server.api.resources.system_profiles import SystemProfileResource
from tessia.server.api.resources.volume_types import VolumeTypeResource
from tessia.server.api.resources.repositories import RepositoryResource
from tessia.server.api.resources.operating_systems import \
    OperatingSystemResource

#
# CONSTANTS AND DEFINITIONS
#
RESOURCES = [
    AutoTemplateResource,
    HMCCanaryResource,
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
    RoleResource,
    UserRoleResource,
    VolumeTypeResource,
    RepositoryResource,
    OperatingSystemResource,
]

#
# CODE
#
