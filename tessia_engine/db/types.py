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
The administratives entries required in the database
"""

#
# IMPORTS
#
from tessia_engine.db.feeder import db_insert

import os

#
# CONSTANTS AND DEFINITIONS
#
TEMPLATES_DIR = os.path.dirname(os.path.abspath(__file__)) + "/templates/"

IFACE_TYPES = [
    'OSA,OSA card',
    'KVM_LIBVIRT,KVM interface configured by libvirt',
    'OVS_BRIDGE,Openvswitch bridge',
    'LINUX_BRIDGE,Linux bridge',
    'HSI,Hipersocket',
    'ROCE,PCI card',
    'OVS_VPORT,Openvswitch virtual port',
]

OPERATING_SYSTEMS = [
    'rhel7.2,rhel,7,2,RHEL 7.2 GA'
]

USERS = [
    'System user,System user for common resources,system,false,true'
]

PROJECTS = [
    'System project,System project for common resources'
]

TEMPLATES = [
    "RHEL7.2,Template for RHEL7.2,system,System project,rhel7.2"
]

ROLES = [
    'Restricted user,Control owned resources only',
    'User,Control owned resources and create new systems',
    'Privileged user,Same as User + use systems from others',
    'Project admin,Control all resources in the project, except for lab '
    'resources (i.e. subnets)',
    'Hardware admin,Control hardware resources (storage volumes, subnets, ip '
    'addresses)',
]

ROLE_ACTIONS = [
    # User
    'User,SYSTEMS,CREATE',
    'User,SUBNETS,CREATE',
    'User,NET_ZONES,CREATE',
    'User,STORAGE_POOLS,CREATE',
    'User,LOGICAL_VOLUMES,CREATE',
    # Privileged user
    # first, create the same privileges as 'User'
    'Privileged user,SYSTEMS,CREATE',
    'Privileged user,SUBNETS,CREATE',
    'Privileged user,NET_ZONES,CREATE',
    'Privileged user,STORAGE_POOLS,CREATE',
    'Privileged user,LOGICAL_VOLUMES,CREATE',
    # now the additional ones to allow managing other users' systems
    'Privileged user,SYSTEMS,UPDATE',
    'Privileged user,STORAGE_POOLS,UPDATE',
    'Privileged user,LOGICAL_VOLUMES,UPDATE',
    # Project admin
    # first, the same privileges as 'Privileged user'
    'Project admin,SYSTEMS,CREATE',
    'Project admin,SUBNETS,CREATE',
    'Project admin,NET_ZONES,CREATE',
    'Project admin,STORAGE_POOLS,CREATE',
    'Project admin,LOGICAL_VOLUMES,CREATE',
    'Project admin,SYSTEMS,UPDATE',
    'Project admin,STORAGE_POOLS,UPDATE',
    'Project admin,LOGICAL_VOLUMES,UPDATE',
    # additional ones to allow managing the resources
    'Project admin,SYSTEMS,DELETE',
    'Project admin,STORAGE_POOLS,DELETE',
    'Project admin,LOGICAL_VOLUMES,DELETE',
    # Hardware admin
    'Hardware admin,IP_ADDRESSES,CREATE',
    'Hardware admin,IP_ADDRESSES,DELETE',
    'Hardware admin,IP_ADDRESSES,UPDATE',
    'Hardware admin,NET_ZONES,CREATE',
    'Hardware admin,NET_ZONES,DELETE',
    'Hardware admin,NET_ZONES,UPDATE',
    'Hardware admin,STORAGE_SERVERS,CREATE',
    'Hardware admin,STORAGE_SERVERS,DELETE',
    'Hardware admin,STORAGE_SERVERS,UPDATE',
    'Hardware admin,STORAGE_VOLUMES,CREATE',
    'Hardware admin,STORAGE_VOLUMES,DELETE',
    'Hardware admin,STORAGE_VOLUMES,UPDATE',
    'Hardware admin,SUBNETS,CREATE',
    'Hardware admin,SUBNETS,DELETE',
    'Hardware admin,SUBNETS,UPDATE',
    'Hardware admin,SYSTEMS,CREATE',
    'Hardware admin,SYSTEMS,DELETE',
    'Hardware admin,SYSTEMS,UPDATE',
]

STORAGE_POOL_TYPES = [
    'LVM_VG,LVM VOlume Group',
    'LVM_LV,LVM Logical Volume',
    'RAID_0,RAID Array Level 0',
]

STORAGE_SERVER_TYPES = [
    'DASD-FCP,Storage serving dasd/fcp disks',
    'ISCSI,iSCSI server',
    'NFS,NFS server',
]

SYSTEM_ARCHS = [
    's390x,IBM System z'
]

SYSTEM_MODELS = [
    'ZEC12_H20,ZEC12,H20,s390x,System z zEC12',
    'ZEC12_H43,ZEC12,H43,s390x,System z zEC12',
    'ZEC12_H66,ZEC12,H66,s390x,System z zEC12',
    'ZEC12_H89,ZEC12,H89,s390x,System z zEC12',
    'Z196_M49,Z196,M49,s390x,System z z196',
    'ZGENERIC,ZGENERIC,,s390x,System z generic',
]

SYSTEM_TYPES = [
    'CPC,s390x,System z CPC',
    'LPAR,s390x,System z LPAR',
    'ZVM,s390x,zVM guest',
    'KVM,s390x,System z KVM guest',
]

SYSTEM_STATES = [
    'AVAILABLE,Available for use',
    'LOCKED,Usage blocked',
    'DEBUG,Temporarily disabled for debugging purposes',
]

VOLUME_TYPES = [
    'DASD,DASD disk type',
    'FCP,FCP-SCSI disk type',
    'ISCSI,ISCSI disk type',
    'RAW,RAW (loopback file)',
    'QCOW2,Compressed file format',
    'LVM,LVM Logical Volume',
]


#
# CODE
#
def get_iface_types():
    """
    Create the network interface types allowed in the application.
    """
    data = []
    for row in IFACE_TYPES:
        row = row.split(',', 2)
        data.append({'name': row[0], 'desc': row[1]})

    return {'IfaceType': data}
# get_iface_types()

def get_oses():
    """
    Create the supported operating systems
    """
    data = []
    for row in OPERATING_SYSTEMS:
        row = row.split(',', 5)
        template_filename = '{}_cmdline.jinja'.format(row[0])
        with open(TEMPLATES_DIR + template_filename, "r") as template_file:
            template_content = template_file.read()
        data.append(
            {
                'name': row[0],
                'type': row[1],
                'major': row[2],
                'minor': row[3],
                'desc': row[4],
                'cmdline': template_content
            }
        )

    return {'OperatingSystem': data}

def get_projects():
    """
    Create the default projects
    """
    data = []
    for row in PROJECTS:
        row = row.split(',', 2)
        data.append(
            {
                'name': row[0],
                'desc': row[1],
            }
        )

    return {"Project": data}
# get_projects()

def get_roles():
    """
    Create the default system roles for users
    """
    data = []
    for row in ROLES:
        row = row.split(',', 2)
        data.append(
            {'name': row[0], 'desc': row[1]})

    return {'Role': data}

def get_role_actions():
    """
    Create the actions allowed for each role
    """
    data = []
    for row in ROLE_ACTIONS:
        row = row.split(',', 3)
        data.append(
            {'role': row[0], 'resource': row[1], 'action': row[2]})

    return {'RoleAction': data}
# get_role_action()

def get_storage_pool_types():
    """
    Create the resource types supported in the application.
    """
    data = []
    for row in STORAGE_POOL_TYPES:
        row = row.split(',', 2)
        data.append({'name': row[0], 'desc': row[1]})

    return {'StoragePoolType': data}
# get_storage_pool_types()

def get_storage_server_types():
    """
    Create the storage server types allowed in the application.
    """
    data = []
    for row in STORAGE_SERVER_TYPES:
        row = row.split(',', 2)
        data.append({'name': row[0], 'desc': row[1]})

    return {'StorageServerType': data}
# get_storage_server_types()

def get_system_archs():
    """
    Create the system architectures supported in the application.
    """
    data = []
    for row in SYSTEM_ARCHS:
        row = row.split(',', 2)
        data.append(
            {'name': row[0], 'desc': row[1]})

    return {'SystemArch': data}
# get_system_archs()

def get_system_models():
    """
    Create the system types supported in the application.
    """
    data = []
    for row in SYSTEM_MODELS:
        row = row.split(',', 5)
        data.append(
            {'name': row[0], 'model': row[1], 'submodel': row[2],
             'arch': row[3], 'desc': row[4]})

    return {'SystemModel': data}
# get_system_models()

def get_system_types():
    """
    Create the system types supported in the application.
    """
    data = []
    for row in SYSTEM_TYPES:
        row = row.split(',', 3)
        data.append({'name': row[0], 'arch': row[1], 'desc': row[2]})

    return {'SystemType': data}
# get_system_types()

def get_system_states():
    """
    Create the system states allowed in the application.
    """
    data = []
    for row in SYSTEM_STATES:
        row = row.split(',', 2)
        data.append({'name': row[0], 'desc': row[1]})

    return {'SystemState': data}
# get_system_states()

def get_templates():
    """
    Create the supported operating systems
    """
    data = []
    for row in TEMPLATES:
        row = row.split(',', 5)
        template_filename = '{}.jinja'.format(row[4])
        with open(TEMPLATES_DIR + template_filename, "r") as template_file:
            template_content = template_file.read()
        data.append(
            {
                'name': row[0],
                'desc': row[1],
                'owner': row[2],
                'modifier': row[2],
                'project': row[3],
                'operating_system': row[4],
                'content': template_content
            }
        )

    return {'Template': data}
# get_templates()

def get_users():
    """
    Create the default users in the application.
    """
    data = []
    for row in USERS:
        row = row.split(',', 5)
        data.append(
            {
                'name': row[0],
                'title': row[1],
                'login': row[2],
                'admin': bool(row[3] == 'true'),
                'restricted': bool(row[4] == 'true'),
            }
        )

    return {"User": data}
# get_users()

def get_volume_types():
    """
    Create the volume types allowed in the application.
    """
    data = []
    for row in VOLUME_TYPES:
        row = row.split(',', 2)
        data.append({'name': row[0], 'desc': row[1]})

    return {'VolumeType': data}
# get_volume_types()

def create_all():
    """
    Create all the database entries for the types allowed or supported by the
    application.
    """
    data = {}
    data.update(get_iface_types())
    data.update(get_roles())
    data.update(get_role_actions())
    data.update(get_storage_pool_types())
    data.update(get_storage_server_types())
    data.update(get_system_archs())
    data.update(get_system_models())
    data.update(get_system_types())
    data.update(get_system_states())
    data.update(get_volume_types())
    data.update(get_users())
    data.update(get_projects())
    data.update(get_oses())
    data.update(get_templates())
    db_insert(data)
# create_all()
