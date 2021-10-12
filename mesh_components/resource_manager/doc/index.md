<!--
Copyright 2021 IBM Corp.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->
# tessia-resource-manager

This component aims to automate and simplify the work with IBM Z platform resources.

# Please note

The component is at the active stage of design and development and cannot be used at the moment.

# Documentation

## tessia-resource-manager API (DRAFT):
- ###Resources:
    - [auto-templates](api/auto-templates.json): a template used to automatically install an operating system;
    - [iface-types](api/iface-types.json): a type of network interface for use in systems;
    - [ip-addresses](api/ip-addresses.json): an IP address that belongs to a subnet;
    - [net-zones](api/net-zones.json): a network zone is a physical or logical subnetwork where one or more of subnets exist;
    - [operating-systems](api/operating-systems.json): a supported operating system;
    - [projects](api/projects.json): a project contains group of users;
    - [repositories](api/repositories.json): a repository is a collection of packages or files that can be installed on a system;
    - [roles](api/roles.json): a role contains a set of permissions for users;
    - [storage-server-types](api/storage-server-types.json): a type for storage servers;
    - [storage-servers](api/storage-servers.json): a storage server contains many storage volumes;
    - [storage-volumes](api/storage-volumes.json): a storage volume for use by Systems;
    - [subnets](api/subnets.json): a subnet holds a range of IP addresses;
    - [system-ifaces](api/system-ifaces.json): a System network interfaces;
    - [system-models](api/system-models.json): a model of system, containing architecture information;
    - [system-profiles](api/system-profiles.json): a system activation profile has volumes, network interfaces and parameters associated;
    - [system-states](api/system-states.json): the current state of a system;
    - [system-types](api/system-types.json): a type of system, containing architecture information;
    - [systems](api/systems.json): a system contains volumes and network interfaces associated through boot profiles;
    - [user-keys](api/user-keys.json): a authentication key allows an user to connect to the API;
    - [user-roles](api/user-roles.json): a user role allows certain actions for a user on a project;
    - [users](api/users.json): a user belongs to a project and has roles;
    - [volume-types](api/volume-types.json): a supported type for volumes;
    