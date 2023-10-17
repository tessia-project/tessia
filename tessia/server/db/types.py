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
from tessia.server.db.feeder import db_insert

import os
import uuid

#
# CONSTANTS AND DEFINITIONS
#
TEMPLATES_DIR = os.path.dirname(os.path.abspath(__file__)) + "/templates/"

IFACE_TYPES = [
    'OSA,OSA card',
    'MACVTAP,KVM macvtap configured by libvirt',
    'ROCE,PCI card',
    'HSI,Hipersockets',

    # TODO:
    #'OVS_BRIDGE,Openvswitch bridge',
    #'LINUX_BRIDGE,Linux bridge',
    #'OVS_VPORT,Openvswitch virtual port',
]

OPERATING_SYSTEMS = [
    'cms,cms,0,0,z/VM Conversational Monitor System (CMS),,',
    'fedora29,redhat,29,0,Fedora 29 (Twenty Nine),fedora-default',
    'fedora30,redhat,30,0,Fedora 30 (Thirty),fedora-default',
    'fedora31,redhat,31,0,Fedora 31 (Thirty One),fedora-default',
    'fedora32,redhat,32,0,Fedora 32 (Thirty Two),fedora-default',
    'rhel7.2,redhat,7,2,Red Hat Enterprise Linux Server 7.2 (Maipo),'
    'rhel7-default',
    'rhel7.3,redhat,7,3,Red Hat Enterprise Linux Server 7.3 (Maipo),'
    'rhel7-default',
    'rhel7.4,redhat,7,4,Red Hat Enterprise Linux Server 7.4 (Maipo),'
    'rhel7-default',
    'rhel7.5,redhat,7,5,Red Hat Enterprise Linux Server 7.5 (Maipo),'
    'rhel7-default',
    'rhel7.6,redhat,7,6,Red Hat Enterprise Linux Server 7.6 (Maipo),'
    'rhel7-default',
    'rhel7.7,redhat,7,7,Red Hat Enterprise Linux Server 7.7 (Maipo),'
    'rhel7-default',
    'rhel7.8,redhat,7,8,Red Hat Enterprise Linux Server 7.8 (Maipo),'
    'rhel7-default',
    'rhel8.0,redhat,8,0,Red Hat Enterprise Linux 8.0 (Ootpa),rhel8-default',
    'rhel8.1,redhat,8,1,Red Hat Enterprise Linux 8.1 (Ootpa),rhel8-default',
    'rhel8.2,redhat,8,2,Red Hat Enterprise Linux 8.2 (Ootpa),rhel8-default',
    'sles12.1,suse,12,1,SUSE Linux Enterprise Server 12 SP1,'
    'sles12-default',
    'sles12.2,suse,12,2,SUSE Linux Enterprise Server 12 SP2,'
    'sles12-default',
    'sles12.3,suse,12,3,SUSE Linux Enterprise Server 12 SP3,'
    'sles12-default',
    'sles12.4,suse,12,4,SUSE Linux Enterprise Server 12 SP4,'
    'sles12-default',
    'sles12.5,suse,12,5,SUSE Linux Enterprise Server 12 SP5,'
    'sles12-default',
    'sles15.0,suse,15,0,SUSE Linux Enterprise Server 15,'
    'sles15-default',
    'sles15.1,suse,15,1,SUSE Linux Enterprise Server 15 SP1,'
    'sles15-default',
    'sles15.2,suse,15,2,SUSE Linux Enterprise Server 15 SP2,'
    'sles15-default',
    'ubuntu16.04.1,debian,1604,1,Ubuntu 16.04.1 LTS,ubuntu16-default',
    'ubuntu16.04.2,debian,1604,2,Ubuntu 16.04.2 LTS,ubuntu16-default',
    'ubuntu16.04.3,debian,1604,3,Ubuntu 16.04.3 LTS,ubuntu16-default',
    'ubuntu16.04.4,debian,1604,4,Ubuntu 16.04.4 LTS,ubuntu16-default',
    'ubuntu16.04.5,debian,1604,5,Ubuntu 16.04.5 LTS,ubuntu16-default',
    'ubuntu18.04,debian,1804,0,Ubuntu 18.04 LTS,ubuntu18-default',
    'ubuntu18.04.1,debian,1804,1,Ubuntu 18.04.1 LTS,ubuntu18-default',
    'ubuntu18.04.2,debian,1804,2,Ubuntu 18.04.2 LTS,ubuntu18-default',
    'ubuntu18.04.3,debian,1804,3,Ubuntu 18.04.3 LTS,ubuntu18-default',
    'ubuntu18.04.4,debian,1804,4,Ubuntu 18.04.4 LTS,ubuntu18-default',
    'ubuntu18.10,debian,1810,0,Ubuntu 18.10,ubuntu18-default',
    'ubuntu19.04,debian,1904,0,Ubuntu 19.04,ubuntu18-default',
    'ubuntu20.04,debian,2004,0,Ubuntu 20.04,ubuntu20-subiquity',
    'ubuntu21.04,debian,2104,0,Ubuntu 21.04,ubuntu21-default',
    'ubuntu22.04,debian,2204,0,Ubuntu 22.04 LTS,ubuntu22-default',
    'ubuntu23.04,debian,2304,0,Ubuntu 23.04,ubuntu23-default',
]

USERS = [
    'Admin user,User for built-in resources and administrative tasks,admin,'
    'true,false'
]

PROJECTS = [
    'Admins,Group for built-in resources and admin users'
]

TEMPLATES = [
    "fedora-default,Default template for Fedora installations,admin,Admins",
    "fedora-kvmhost,Fedora KVM hypervisor profile,admin,Admins",
    "rhel7-default,Default template for RHEL7 installations,admin,Admins",
    "rhel8-default,Default template for RHEL8 installations,admin,Admins",
    "rhel8-kvmhost,RHEL8 KVM hypervisor profile,admin,Admins",
    "sles12-default,Default template for SLES12 installations,admin,Admins",
    "sles12-kvmhost,SLES12 KVM hypervisor profile,admin,Admins",
    "sles15-default,Default template for SLES15 installations,admin,Admins",
    "sles15-kvmhost,SLES15 KVM hypervisor profile,admin,Admins",
    "ubuntu16-default,Default template for Ubuntu16 installations"
    ",admin,Admins",
    "ubuntu16-kvmhost,Ubuntu16 KVM hypervisor profile,admin,Admins",
    "ubuntu18-default,Default template for Ubuntu18 installations"
    ",admin,Admins",
    "ubuntu18-kvmhost,Ubuntu18 KVM hypervisor profile,admin,Admins",
    "ubuntu20-subiquity,Default template for Ubuntu20 installations"
    ",admin,Admins",
    "ubuntu21-default,Default template for Ubuntu21 installations"
    ",admin,Admins",
    "ubuntu22-default,Default template for Ubuntu22 installations"
    ",admin,Admins",
    "ubuntu23-default,Default template for Ubuntu23 installations"
    ",admin,Admins"
]

ROLES = [
    'USER_SANDBOX,Has no access to resources',
    'USER_RESTRICTED,Control owned resources only',
    'USER,Control owned resources and create new systems',
    'USER_PRIVILEGED,Same as User + use systems from others',
    'ADMIN_PROJECT,Control all resources in the project, except for lab '
    'resources (i.e. subnets)',
    'OWNER_PROJECT,Assigns user roles in project',
    'ADMIN_LAB,Control infrastructure resources (storage volumes, subnets, ip '
    'addresses)',
]

ROLE_ACTIONS = [
    # Normal user
    'USER,SYSTEMS,CREATE',
    'USER,SUBNETS,CREATE',
    'USER,NET_ZONES,CREATE',
    'USER,STORAGE_POOLS,CREATE',
    'USER,LOGICAL_VOLUMES,CREATE',
    # privileged user
    # first, create the same privileges as 'USER'
    'USER_PRIVILEGED,SYSTEMS,CREATE',
    'USER_PRIVILEGED,SUBNETS,CREATE',
    'USER_PRIVILEGED,NET_ZONES,CREATE',
    'USER_PRIVILEGED,STORAGE_POOLS,CREATE',
    'USER_PRIVILEGED,LOGICAL_VOLUMES,CREATE',
    # now the additional ones to allow managing other users' systems
    'USER_PRIVILEGED,SYSTEMS,UPDATE',
    'USER_PRIVILEGED,STORAGE_POOLS,UPDATE',
    'USER_PRIVILEGED,LOGICAL_VOLUMES,UPDATE',
    # Project owner, only assigns roles
    'OWNER_PROJECT,USER_ROLES,CREATE',
    'OWNER_PROJECT,USER_ROLES,DELETE',
    # Project admin
    # first, the same privileges as 'USER_PRIVILEGED'
    'ADMIN_PROJECT,SYSTEMS,CREATE',
    'ADMIN_PROJECT,SUBNETS,CREATE',
    'ADMIN_PROJECT,NET_ZONES,CREATE',
    'ADMIN_PROJECT,STORAGE_POOLS,CREATE',
    'ADMIN_PROJECT,LOGICAL_VOLUMES,CREATE',
    'ADMIN_PROJECT,SYSTEMS,UPDATE',
    'ADMIN_PROJECT,STORAGE_POOLS,UPDATE',
    'ADMIN_PROJECT,LOGICAL_VOLUMES,UPDATE',
    # additional ones to allow managing the resources
    'ADMIN_PROJECT,SYSTEMS,DELETE',
    'ADMIN_PROJECT,STORAGE_POOLS,DELETE',
    'ADMIN_PROJECT,LOGICAL_VOLUMES,DELETE',
    'ADMIN_PROJECT,TEMPLATES,CREATE',
    'ADMIN_PROJECT,TEMPLATES,DELETE',
    'ADMIN_PROJECT,TEMPLATES,UPDATE',
    'ADMIN_PROJECT,REPOSITORIES,CREATE',
    'ADMIN_PROJECT,REPOSITORIES,DELETE',
    'ADMIN_PROJECT,REPOSITORIES,UPDATE',
    # Lab admin
    'ADMIN_LAB,IP_ADDRESSES,CREATE',
    'ADMIN_LAB,IP_ADDRESSES,DELETE',
    'ADMIN_LAB,IP_ADDRESSES,UPDATE',
    'ADMIN_LAB,NET_ZONES,CREATE',
    'ADMIN_LAB,NET_ZONES,DELETE',
    'ADMIN_LAB,NET_ZONES,UPDATE',
    'ADMIN_LAB,STORAGE_SERVERS,CREATE',
    'ADMIN_LAB,STORAGE_SERVERS,DELETE',
    'ADMIN_LAB,STORAGE_SERVERS,UPDATE',
    'ADMIN_LAB,STORAGE_VOLUMES,CREATE',
    'ADMIN_LAB,STORAGE_VOLUMES,DELETE',
    'ADMIN_LAB,STORAGE_VOLUMES,UPDATE',
    'ADMIN_LAB,SUBNETS,CREATE',
    'ADMIN_LAB,SUBNETS,DELETE',
    'ADMIN_LAB,SUBNETS,UPDATE',
    'ADMIN_LAB,SYSTEMS,CREATE',
    'ADMIN_LAB,SYSTEMS,DELETE',
    'ADMIN_LAB,SYSTEMS,UPDATE',
    'ADMIN_LAB,REPOSITORIES,CREATE',
    'ADMIN_LAB,REPOSITORIES,DELETE',
    'ADMIN_LAB,REPOSITORIES,UPDATE',
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
    'NVME, NVME storage server',
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
    'AVAILABLE,System can be used normally',
    'LOCKED,System is protected by owner from unwanted actions',
    'RESERVED,System is reserved for a project/team and cannot be used',
    'UNASSIGNED,System does not belong to any user and cannot be used',
]

VOLUME_TYPES = [
    'DASD,DASD disk type',
    'HPAV,HPAV alias for DASD disks',
    'FCP,FCP-SCSI disk type',
    'ISCSI,ISCSI disk type',
    'RAW,RAW (loopback file)',
    'QCOW2,Compressed file format',
    'LVM,LVM Logical Volume',
    'NVME,NVME disk type',
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
        row = row.split(',', 6)
        if row[0] == 'cms':
            template = None
        else:
            template = row[5]
        data.append(
            {
                'name': row[0],
                'type': row[1],
                'major': row[2],
                'minor': row[3],
                'pretty_name': row[4],
                'template': template,
            }
        )

    return {'OperatingSystem': data}

def get_projects():
    """
    Create the built-in projects
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
    Create the built-in roles for users
    """
    data = []
    for row in ROLES:
        row = row.split(',', 1)
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
    Add the default auto install templates
    """
    data = []
    for row in TEMPLATES:
        row = row.split(',', 4)
        template_filename = '{}.jinja'.format(row[0])
        with open(TEMPLATES_DIR + template_filename, "r") as template_file:
            template_content = template_file.read()
        data.append(
            {
                'name': row[0],
                'desc': row[1],
                'owner': row[2],
                'modifier': row[2],
                'project': row[3],
                'content': template_content,
            }
        )

    return {'Template': data}
# get_templates()

def get_token_users():
    """
    Generate an auth token for each of the built-in users.
    """
    data = []
    for row in USERS:
        row = row.split(',', 5)
        data.append(
            {
                'user': row[2],
                'key_id': str(uuid.uuid4()).replace('-', ''),
                'key_secret': str(uuid.uuid4()).replace('-', '')
            }
        )

    return {'UserKey': data}
# get_token_users()

def get_users():
    """
    Create the built-in users in the application.
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
    data.update(get_token_users())
    data.update(get_projects())
    data.update(get_templates())
    data.update(get_oses())
    db_insert(data)
# create_all()
