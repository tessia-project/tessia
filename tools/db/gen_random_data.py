#!/usr/bin/env python3
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
Generate random entries to populate the database for devel or or testing
purposes.
"""

#
# IMPORTS
#
import json
import random

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
def create_permissions():
    """
    Some information on the data generated:
    - user_{project}_0@domain.com is always admin;
    - user_{project}_1@domain.com is always restricted;
    - user_{project}_2@domain.com has always 'hardware admin' role;
    - user_{project}_3@domain.com has always 'project admin' role;
    - user_{project}_4@domain.com has always 'restricted user' role;
    - user_{project}_5@domain.com has always 'Privileged user' role;
    - user_{project}_6@domain.com has no role at all;
    - all others have 'user' role;
    """
    # create projects
    projects = []
    for dep_id in ('x', 'y', 'z'):
        name = 'Department ' + dep_id
        desc = 'Description of ' + name
        department = {
            'name': name,
            'desc': desc,
            'avatar': None,
        }
        projects.append(department)
        for team_id in range(0, 5):
            name = 'Team {}-{}'.format(dep_id, team_id)
            desc = 'Description of ' + name
            projects.append({
                'name': name,
                'desc': desc,
                'avatar': None,
            })

    # create users and their roles
    # TODO: create user api keys
    users = []
    roles = []
    for project in projects:
        project_id = project['name'].split()[-1]
        # create 10 users per project
        for i in range(0, 10):
            suffix = '{}_{}'.format(project_id, i)
            login = 'user_{}@domain.com'.format(suffix)
            name = 'Name of user {}'.format(suffix)
            title = 'Title of user {}'.format(suffix)
            admin = False
            restricted = False
            role = 'User'

            # admin user; complete access without role needed
            if i == 0:
                admin = True
            # restricted user; can only do what role permits and cannot
            # list/view resources from other projects
            elif i == 1:
                restricted = True
            # hardware admin
            elif i == 2:
                role = 'Hardware admin'
            # project admin
            elif i == 3:
                role = 'Project admin'
            # restricted user
            elif i == 4:
                role = 'Restricted user'
            # privileged user
            elif i == 5:
                role = 'Privileged user'
            # no role
            elif i == 6:
                role = None

            # login,name,title,restricted,admin
            users.append({
                'login': login,
                'name': name,
                'title': title,
                'restricted': restricted,
                'admin': admin
            })
            if role is not None:
                roles.append({
                    'user': login,
                    'role': role,
                    'project': project['name']
                })

    permissions = {'User': users, 'UserRole': roles, 'Project': projects}
    return permissions
# create_permissions()

def create_network(data):
    """
    Generate network related data
    - network zones
    - subnets
    - systems network interfaces
    - ip addresses

    Args:
        data (dict): pre-filled db entries for other entities

    Returns:
        dict: entries for netzones, subnets, netifaces and ip addresses

    Raises:
        RuntimeError: if activation profile for system was not previously
                      created
    """
    def get_new_ip(subnet, system):
        """
        Helper function to allocate next free ip address
        """
        # get next available ip address on the subnet
        free_addr = subnet['next']

        # calculate next ip and store it
        fields = free_addr.split('.')
        fields[-1] = str(int(fields[-1]) + 1)
        # we assume the subnet will not grow past a class b size
        if fields[-1] == '256':
            fields[-2] = str(int(fields[-2]) + 1)
            fields[-1] = '1'
        subnet['next'] = '.'.join(fields)

        ip_addr = {
            'address': free_addr,
            'subnet': subnet['subnet']['name'],
            'owner': system['owner'],
            'project': system['project'],
            'modifier': system['owner'],
            'desc': None,
        }
        return ip_addr
    # get_new_ip()

    subnet_index = 1
    # auxiliar dict used later to know the next ip to assign to a system iface
    ip_by_system = {}

    # the following loop will create:
    # - one shared zone and a subnet per cpc
    # - one private (to be used by guests) zone and a subnet for lpar
    net_zones = []
    subnets = []
    for system in data['System']:
        # kvm and zvm guests don't get subnets for them
        if system['type'] not in ('cpc', 'lpar'):
            continue

        # owner and project is the same as the system
        zone = {
            'project': system['project'],
            'owner': system['owner'],
            'modifier': system['modifier']
        }

        subnet = zone.copy()

        if system['type'] == 'cpc':
            # zone related information
            zone['desc'] = 'Network zone for CPC ' + system['name']
            zone['name'] = '{}'.format(system['name'])

            # subnet related information
            subnet['zone'] = zone['name']
            subnet['name'] = '{} shared'.format(system['name'])
            subnet['address'] = '10.{}.0.0/16'.format(subnet_index)
            subnet['gateway'] = '10.{}.0.1'.format(subnet_index)
            subnet['dns_1'] = '10.{}.0.2'.format(subnet_index)
            subnet['dns_2'] = '10.{}.0.3'.format(subnet_index)
            subnet['vlan'] = 1800 + subnet_index
            subnet['desc'] = 'Shared subnet of {}'.format(system['name'])

            # store subnet information indexed by system to be used for
            # netifaces creation later
            ip_by_system[system['name']] = {
                'next': '10.{}.0.4'.format(subnet_index),
                'subnet': subnet
            }
        else:
            # zone related information
            zone['desc'] = 'Private network zone for LPAR ' + system['name']
            zone['name'] = '{}'.format(system['name'])

            # subnet related information
            subnet['zone'] = zone['name']
            subnet['name'] = '{} private'.format(system['name'])
            subnet['address'] = '192.168.0.0/24'
            subnet['gateway'] = '192.168.0.1'
            subnet['dns_1'] = '192.168.0.2'
            subnet['dns_2'] = '192.168.0.3'
            subnet['vlan'] = None
            subnet['desc'] = 'Private subnet of {}'.format(system['name'])

            # store subnet information indexed by system to be used for
            # netifaces creation later
            ip_by_system[system['name']] = {
                'next': '192.168.0.4',
                'subnet': subnet
            }

        net_zones.append(zone)
        subnets.append(subnet)
        subnet_index += 1

    # create ifaces and ips
    ip_addresses = []
    net_ifaces = []
    profile_ifaces_associations = []
    roce = True
    for system in data['System']:
        if system['type'] == 'cpc':
            continue

        # get the corresponding activation profile to which the created
        # interfaces will be added to
        profile = None
        for find_profile in data['SystemProfile']:
            if find_profile['system'] == system['name']:
                profile = find_profile
                break
        # sanity check
        if profile is None:
            raise RuntimeError('Activation profile for system {} not '
                               'found'.format(system['name']))

        # get next available ip address on the cpc subnet
        ip_addr = get_new_ip(ip_by_system[system['hypervisor']], system)
        ip_addresses.append(ip_addr)

        if system['type'] == 'lpar':
            # create osa
            net_iface = {
                'name': 'external osa',
                'osname': 'enccwf500',
                'attributes': (
                    "{'layer2': True, 'devicenr': '0xf500,0xf501,0xf502'}"),
                'type': 'OSA',
                'mac_address': ':'.join(
                    ['%x' % random.randint(0x00, 0xff) for i in range(0, 6)]),
                'system': system['name'],
                'ip_address': '{}/{}'.format(
                    ip_addr['subnet'], ip_addr['address']),
            }
            net_ifaces.append(net_iface)
            profile_ifaces_associations.append({
                'profile': '{}/{}'.format(
                    net_iface['system'], profile['name']),
                'iface': '{}/{}'.format(
                    net_iface['system'], net_iface['name'])
            })

            if roce:
                # switch for next iteration
                roce = False
                net_iface = {
                    'name': 'internal roce',
                    'osname': 'roce0',
                    'attributes': None,
                    'type': 'ROCE',
                    'mac_address': None,
                    'system': system['name'],
                }
            # odd number: create hsi
            else:
                # switch for next iteration
                roce = True
                net_iface = {
                    'name': 'internal hsi',
                    'osname': 'hsi0',
                    'attributes': None,
                    'type': 'HSI',
                    'mac_address': ':'.join(
                        ['%x' % random.randint(0x00, 0xff)
                         for i in range(0, 6)]),
                    'system': system['name'],
                }
            net_ifaces.append(net_iface)
            profile_ifaces_associations.append({
                'profile': '{}/{}'.format(
                    net_iface['system'], profile['name']),
                'iface': '{}/{}'.format(
                    net_iface['system'], net_iface['name'])
            })

            # now add the ovs bridge
            ovs_bridge = {
                'name': 'ovs_bridge',
                'attributes': (
                    "{'physical_ports': [{'name': '%s', 'mtu': 1500, "
                    "'txqueuelen': 500}]}" % net_iface['osname']),
                'osname': 'vswitch0',
                'system': system['name'],
                'type': 'OVS_BRIDGE',
                'mac_address': ':'.join(
                    ['%x' % random.randint(0x00, 0xff) for i in range(0, 6)])
            }
            net_ifaces.append(ovs_bridge)
            profile_ifaces_associations.append({
                'profile': '{}/{}'.format(
                    ovs_bridge['system'], profile['name']),
                'iface': '{}/{}'.format(
                    ovs_bridge['system'], ovs_bridge['name'])
            })

        elif system['type'] == 'zvm':
            # get next available ip address on the lpar subnet
            ip_addr = get_new_ip(ip_by_system[system['hypervisor']], system)
            ip_addresses.append(ip_addr)

            # create osa
            net_iface = {
                'name': 'external osa',
                'osname': 'enccw1200',
                'attributes': (
                    "{'layer2': True, 'devicenr': '0x1200,0x1201,0x1202'}"),
                'type': 'OSA',
                'mac_address': ':'.join(
                    ['%x' % random.randint(0x00, 0xff) for i in range(0, 6)]),
                'system': system['name'],
                'ip_address': '{}/{}'.format(
                    ip_addr['subnet'], ip_addr['address']),
            }
            net_ifaces.append(net_iface)
            profile_ifaces_associations.append({
                'profile': '{}/{}'.format(
                    net_iface['system'], profile['name']),
                'iface': '{}/{}'.format(
                    net_iface['system'], net_iface['name'])
            })

        elif system['type'] == 'kvm':
            # get next available ip address on the lpar subnet
            ip_addr = get_new_ip(ip_by_system[system['hypervisor']], system)
            ip_addresses.append(ip_addr)

            osname = 'en0'
            mac_address = ':'.join(
                ['%x' % random.randint(0x00, 0xff) for i in range(0, 6)])
            # for kvm guests we are accepting libvirt xml directly
            libvirt_xml = (
                '<interface type="direct"><mac address="{}"/>'
                '<source dev="{}" mode="bridge"/><model type="virtio"/>'
                '<address type="ccw" cssid="0xfe" ssid="0x0" devno="0xf500"/>'
                '</interface>').format(mac_address, osname)

            # create a macvtap
            net_iface = {
                'name': 'external macvtap',
                'osname': 'en0',
                'attributes': "{'libvirt': %s}" % libvirt_xml,
                'type': 'KVM_LIBVIRT',
                'mac_address': mac_address,
                'system': system['name'],
                'ip_address': '{}/{}'.format(
                    ip_addr['subnet'], ip_addr['address']),
            }
            net_ifaces.append(net_iface)
            profile_ifaces_associations.append({
                'profile': '{}/{}'.format(
                    net_iface['system'], profile['name']),
                'iface': '{}/{}'.format(
                    net_iface['system'], net_iface['name'])
            })

            # get next available ip address on the lpar subnet
            ip_addr = get_new_ip(ip_by_system[system['hypervisor']], system)
            ip_addresses.append(ip_addr)

            # create a ovs port
            net_iface = {
                'name': 'internal ovs port',
                'osname': 'en1',
                'attributes': (
                    "{'name': 'vport1', 'mtu': 1500, 'txqueuelen': 500}"),
                'type': 'OVS_VPORT',
                'mac_address': ':'.join(
                    ['%x' % random.randint(0x00, 0xff) for i in range(0, 6)]),
                'system': system['name'],
                'ip_address': '{}/{}'.format(
                    ip_addr['subnet'], ip_addr['address']),
            }
            net_ifaces.append(net_iface)
            profile_ifaces_associations.append({
                'profile': '{}/{}'.format(
                    net_iface['system'], profile['name']),
                'iface': '{}/{}'.format(
                    net_iface['system'], net_iface['name'])
            })


    result = {
        'NetZone': net_zones,
        'Subnet' : subnets,
        'IpAddress': ip_addresses,
        'SystemIface': net_ifaces,
        'SystemIfaceProfileAssociation': profile_ifaces_associations,
    }

    return result
# create_network()

def create_storage(data):
    """
    Generate storage related data:
        - storage servers
        - storage volumes
        - storage pool
        - logical volumes

    Args:
        data (dict): pre-filled db entries for other entities

    Returns:
        dict: entries for servers, volumes, and pools

    Raises:
        RuntimeError: if activation profile for system was not previously
                      created
    """
    # used to find the appropriate storage server later when creating volumes
    server_by_dep = {}

    storage_servers = []
    for i in range(0, 3):
        dep_id = chr(ord('x') + i)
        server_by_dep[dep_id] = {}

        # add DASD-FCP entry
        server = {'name': 'DSK8_{}_{}'.format(dep_id, i)}
        server['hostname'] = None
        server['type'] = 'DASD-FCP'
        server['model'] = 'DS8800'
        if i == 0:
            server['fw_level'] = None
        else:
            server['fw_level'] = '87.21.5.' + str(i)
        server['username'] = None
        server['password'] = None
        server['owner'] = 'user_{}_2@domain.com'.format(dep_id)
        server['project'] = 'Department ' + dep_id
        server['modifier'] = 'user_{}_2@domain.com'.format(dep_id)
        # let date be created at insert time
        server['desc'] = (
            '- Storage *DASD-FCP* beloging to Department ' + dep_id)
        storage_servers.append(server)
        server_by_dep[dep_id]['DASD-FCP'] = server

        # add iSCSI entry
        server = server.copy()
        server['name'] = 'iSCSI_{}_{}'.format(dep_id, i)
        server['hostname'] = 'iscsi-{}_{}.domain.com'.format(dep_id, i)
        server['type'] = 'ISCSI'
        server['model'] = 'Generic iSCSI'
        server['fw_level'] = None
        server['username'] = 'root'
        server['password'] = 'somepasswd'
        server['desc'] = '- Storage *ISCSI* beloging to Department ' + dep_id
        storage_servers.append(server)
        server_by_dep[dep_id]['ISCSI'] = server

        # add nfs entry
        server = server.copy()
        server['name'] = 'NFS_{}_{}'.format(dep_id, i)
        server['hostname'] = 'nfs-{}_{}.domain.com'.format(dep_id, i)
        server['type'] = 'NFS'
        server['model'] = 'Linux NFS'
        server['fw_level'] = None
        server['username'] = 'root'
        server['password'] = 'somepasswd'
        server['desc'] = '- Storage *NFS* beloging to Department ' + dep_id
        storage_servers.append(server)
        server_by_dep[dep_id]['NFS'] = server

    disk_counter = 0
    kvm_logical_volume = False
    scsi_specs_template = (
        "{'multipath': true, 'paths': ["
        "{'devno': '0.0.1800', 'wwpns': ['5005076300C213e5', "
        "'5005076300C213e9']}, {'devno': '0.0.1900', 'wwpns': ["
        "'5005076300C213e9']}]}"),
    storage_volumes = []
    prof_storage_volumes_assoc = []
    storage_pools = []
    logical_volumes = []
    prof_logical_volumes_assoc = []
    for system in data['System']:
        if system['type'] == 'cpc':
            continue

        # get the corresponding activation profile to which the created
        # volumes will be added to
        profile = None
        for find_profile in data['SystemProfile']:
            if find_profile['system'] == system['name']:
                profile = find_profile
                break
        # sanity check
        if profile is None:
            raise RuntimeError('Activation profile for system {} not '
                               'found'.format(system['name']))

        project = system['project'].split()[1].split('-')[0]
        servers = server_by_dep[project]

        if system['type'] in ('lpar', 'zvm'):
            # create eckd with root and swap
            volume = {
                'volume_id': '%x' % (0x1800 + disk_counter),
                'server': servers['DASD-FCP']['name'],
                'system': system['name'],
                'type': 'DASD',
                'size': 10000,
                'part_table': {
                    'type': 'msdos',
                    'table': [
                        {'mp': '/', 'size': 8000, 'fs': 'ext4',
                         'type': 'primary', 'mo': None},
                        {'mp': None, 'size': 2000, 'fs': 'swap',
                         'type': 'primary', 'mo': None},
                    ]
                },
                'specs': "{}",
                'system_attributes': "{}",
                'owner': system['owner'],
                'project': system['project'],
                'modifier': system['modifier'],
                'desc': '- DASD disk for regression tests',
            }
            storage_volumes.append(volume)
            prof_storage_volumes_assoc.append({
                'profile': '{}/{}'.format(volume['system'], profile['name']),
                'volume': '{}/{}'.format(volume['server'], volume['volume_id'])
            })

            # create scsi with /home partition
            volume = volume.copy()
            volume['volume_id'] = '%x' % (0x1022400000000000 + disk_counter)
            volume['server'] = servers['DASD-FCP']['name']
            volume['type'] = 'FCP'
            volume['size'] = 20000
            volume['part_table'] = {
                'type': 'msdos',
                'table': [
                    {'mp': '/home', 'size': 20000, 'fs': 'ext4',
                     'type': 'primary', 'mo': None},
                ]
            }
            volume['specs'] = scsi_specs_template,
            volume['desc'] = '- SCSI disk for storing test results'
            storage_volumes.append(volume)
            disk_counter += 1

            prof_storage_volumes_assoc.append({
                'profile': '{}/{}'.format(volume['system'], profile['name']),
                'volume': '{}/{}'.format(volume['server'], volume['volume_id'])
            })


        elif system['type'] == 'kvm':
            # for kvm guests we are accepting libvirt xml directly
            libvirt_disk = (
                '<disk type="block" device="disk">'
                '<driver name="qemu" type="raw" cache="none"/>'
                '<source dev="/dev/mapper/mpath-%s"/>'
                '<target dev="vda" bus="virtio"/>'
                '<address type="ccw" cssid="0xfe" ssid="0x0" devno="0x1111"/>'
                '</disk>')
            libvirt_qcow = (
                '<disk type="file" device="disk">'
                '<driver name="qemu" type="qcow2" cache="none"/>'
                '<source file="/var/images/%s"/>'
                '<target dev="vda" bus="virtio"/>'
                '<address type="ccw" cssid="0xfe" ssid="0x0" devno="0x1111"/>'
                '</disk>')

            if kvm_logical_volume:
                # switch for next iteration
                kvm_logical_volume = False
                scsi_size = 20000

                # create a storage pool
                pool = {
                    'name': 'Pool for system {}'.format(system['name']),
                    'system': system['name'],
                    'type': 'LVM_VG',
                    'total_size': 2 * scsi_size,
                    'used_size': 2 * scsi_size,
                    # this can be set by the user, if has to be generated
                    'attributes': "{'chunksize': '512'}",
                    'owner': system['owner'],
                    'project': system['project'],
                    'modifier': system['modifier'],
                    'desc': '- Storage pool for creating qcow2 images',
                }
                storage_pools.append(pool)

                # create 2 x scsi and add to the storage pool
                volume = {
                    'volume_id': '%x' % (0x1022400000000000 + disk_counter),
                    'server': servers['DASD-FCP']['name'],
                    'system': system['name'],
                    'type': 'FCP',
                    'pool': pool['name'],
                    'size': scsi_size,
                    'part_table': {
                        'type': 'msdos',
                        'table': [
                            {'mp': None, 'size': 20000, 'fs': 'lvm',
                             'type': 'primary', 'mo': None},
                        ]
                    },
                    'specs': scsi_specs_template,
                    'system_attributes': "{}",
                    'owner': system['owner'],
                    'project': system['project'],
                    'modifier': system['modifier'],
                    'desc': '- SCSI disk for storage pool',
                }
                storage_volumes.append(volume)
                disk_counter += 1

                prof_storage_volumes_assoc.append({
                    'profile': '{}/{}'.format(
                        volume['system'], profile['name']),
                    'volume': '{}/{}'.format(
                        volume['server'], volume['volume_id'])
                })

                # make a copy and add again
                volume = volume.copy()
                volume['volume_id'] = '%x' % (
                    0x1022400000000000 + disk_counter)
                storage_volumes.append(volume)
                disk_counter += 1

                prof_storage_volumes_assoc.append({
                    'profile': '{}/{}'.format(
                        volume['system'], profile['name']),
                    'volume': '{}/{}'.format(
                        volume['server'], volume['volume_id'])
                })

                # create two qcow2 images; one for root and swap, the second
                # for /var
                volume = {
                    'name': '{} root image'.format(system['name']),
                    'system': system['name'],
                    'type': 'QCOW2',
                    'pool': pool['name'],
                    'size': scsi_size,
                    'part_table': {
                        'type': 'msdos',
                        'table': [
                            {'mp': '/', 'size': 17000, 'fs': 'ext4',
                             'type': 'primary', 'mo': None},
                            {'mp': None, 'size': 3000, 'fs': 'swap',
                             'type': 'primary', 'mo': None},
                        ]
                    },
                    'specs': "{'thin': true}",
                    'system_attributes': "{'libvirt: '%s'}" % (
                        libvirt_qcow % '{}_root_image'.format(system['name'])),
                    'owner': system['owner'],
                    'project': system['project'],
                    'modifier': system['modifier'],
                    'desc': '- QCOW2 image for kvm guest',
                }
                logical_volumes.append(volume)
                prof_logical_volumes_assoc.append({
                    'profile': '{}/{}'.format(
                        volume['system'], profile['name']),
                    'volume': '{}/{}'.format(
                        volume['pool'], volume['name'])
                })

                # make a copy and add again
                volume = volume.copy()
                volume['name'] = '{} image for /var'.format(system['name'])
                volume['part_table'] = {
                    'type': 'msdos',
                    'table': [
                        {'mp': '/var', 'size': 20000, 'fs': 'ext4',
                         'type': 'primary', 'mo': None},
                    ]
                },
                volume['system_attributes'] = "{'libvirt: '%s'}" % (
                    libvirt_qcow % '{}_image_for__var'.format(system['name'])),

                logical_volumes.append(volume)
                prof_logical_volumes_assoc.append({
                    'profile': '{}/{}'.format(
                        volume['system'], profile['name']),
                    'volume': '{}/{}'.format(
                        volume['pool'], volume['name'])
                })

            else:
                # switch for next iteration
                kvm_logical_volume = True

                # create scsi for root and swap
                volume = {
                    'volume_id': '%x' % (0x1022400000000000 + disk_counter),
                    'server': servers['DASD-FCP']['name'],
                    'system': system['name'],
                    'type': 'FCP',
                    'size': 20000,
                    'part_table': {
                        'type': 'msdos',
                        'table': [
                            {'mp': '/', 'size': 17000, 'fs': 'ext4',
                             'type': 'primary', 'mo': None},
                            {'mp': None, 'size': 3000, 'fs': 'swap',
                             'type': 'primary', 'mo': None},
                        ]
                    },
                    'specs': scsi_specs_template,
                    'system_attributes': "{'libvirt: '%s'}" % (
                        libvirt_disk % disk_counter),
                    'owner': system['owner'],
                    'project': system['project'],
                    'modifier': system['modifier'],
                    'desc': '- SCSI disk for operating system',
                }
                storage_volumes.append(volume)
                prof_storage_volumes_assoc.append({
                    'profile': '{}/{}'.format(
                        volume['system'], profile['name']),
                    'volume': '{}/{}'.format(
                        volume['server'], volume['volume_id'])
                })

                # create eckd for /home
                volume = volume.copy()
                volume['volume_id'] = '%x' % (0x1800 + disk_counter)
                volume['server'] = servers['DASD-FCP']['name']
                volume['type'] = 'DASD'
                volume['size'] = 10000
                volume['part_table'] = {
                    'type': 'msdos',
                    'table': [
                        {'mp': '/home', 'size': 10000, 'fs': 'ext3',
                         'type': 'primary', 'mo': None},
                    ]
                }
                volume['specs'] = "{}"
                volume['system_attributes'] = "{}"
                volume['desc'] = '- DASD disk for test data'
                storage_volumes.append(volume)
                disk_counter += 1

                prof_storage_volumes_assoc.append({
                    'profile': '{}/{}'.format(
                        volume['system'], profile['name']),
                    'volume': '{}/{}'.format(
                        volume['server'], volume['volume_id'])
                })

    result = {
        'StorageServer': storage_servers,
        'StorageVolume': storage_volumes,
        'StoragePool': storage_pools,
        'LogicalVolume': logical_volumes,
        'StorageVolumeProfileAssociation': \
            prof_storage_volumes_assoc,
        'LogicalVolumeProfileAssociation': \
            prof_logical_volumes_assoc,
    }
    return result
# create_storage()

def create_systems(data):
    """
    Generate systems entries (cpcs, lpars, vms, kvm guests)

    Args:
        data (dict): pre-filled db entries for other entities

    Returns:
        dict: entries for systems and activation profiles
    """
    system_models = ('ZEC12_H20', 'Z196_M49', 'ZEC12_H43')
    system_states = ('AVAILABLE', 'LOCKED', 'DEBUG')

    systems = []
    # profiles are created here but they are only complete after the volumes
    # and ifaces are created and added to them
    activation_profiles = []

    # create a CPC for each project
    counter = 0
    cpc_by_project = {}
    for project in data['Project']:
        project_name = project['name'].split()[-1]
        system = {'name': 'cpc' + str(counter)}
        system['hostname'] = 'cpc-{}.domain.com'.format(counter)
        system['type'] = 'cpc'
        system['model'] = system_models[counter % 3]
        system['state'] = 'AVAILABLE'
        system['owner'] = 'user_{}_2@domain.com'.format(project_name)
        system['project'] = project['name']
        system['modifier'] = system['owner']
        system['desc'] = 'CPC for project ' + project['name']
        systems.append(system)
        # store reference to cpc by project to be used later
        cpc_by_project[project['name']] = system
        # increase general counter
        counter += 1

    for user in data['User']:
        # project is part of username so it can be extracted from it
        project = user['login'].split('_')[1]
        if '-' in project:
            project = 'Team {}'.format(project)
        else:
            project = 'Department {}'.format(project)
        hyp_cpc = cpc_by_project[project]

        # for each user, create 3 lpars in each state and 3 guests (zvm for odd
        # numbered, kvm for even numbered)
        for i in range(0, 3):
            lpar = {'name': 'lpar' + str(counter)}
            lpar['hostname'] = 'lpar-{}.domain.com'.format(counter)
            lpar['type'] = 'lpar'
            lpar['model'] = hyp_cpc['model']
            lpar['hypervisor'] = hyp_cpc['name']
            lpar['state'] = system_states[i]
            lpar['owner'] = user['login']
            lpar['project'] = project
            lpar['modifier'] = user['login']
            lpar['desc'] = '- LPAR {} for user {}'.format(i, user['login'])

            systems.append(lpar)
            counter += 1

            # create activation profile
            # TODO: add entry for operating system
            lpar_profile = {
                'name': 'default {}'.format(lpar['name']),
                'cpu': 2,
                'memory': 1024,
                'default': True,
                'system': lpar['name'],
            }
            # linux kvm host
            if i % 2 == 0:
                lpar_profile['credentials'] = (
                    "{'username': 'root', 'password': 'somepasswd'}")
            # zvm hypervisor
            else:
                lpar_profile['credentials'] = (
                    "{'username': 'vmuser', 'password': 'pass4vm'}")
                lpar_profile['parameters'] = "{'loadparams': 'smt'}"

            activation_profiles.append(lpar_profile)

            for j in range(0, 3):
                guest = {'model': hyp_cpc['model']}
                guest['hypervisor'] = lpar['name']
                guest['state'] = lpar['state']
                guest['owner'] = lpar['owner']
                guest['project'] = lpar['project']
                guest['modifier'] = lpar['modifier']
                # kvm guest
                if i % 2 == 0:
                    guest['name'] = 'kvm' + str(counter)
                    guest['hostname'] = 'kvm-{}.domain.com'.format(counter)
                    guest['type'] = 'kvm'
                    guest['desc'] = '- KVM guest {} for user {}'.format(
                        j, guest['owner'])
                else:
                    guest['name'] = 'zvm' + str(counter)
                    guest['hostname'] = 'zvm-{}.domain.com'.format(counter)
                    guest['type'] = 'zvm'
                    guest['desc'] = '- zVM guest {} for user {}'.format(
                        j, guest['owner'])

                systems.append(guest)
                counter += 1

                profile = lpar_profile.copy()
                profile['name'] = 'default {}'.format(guest['name'])
                profile['hypervisor_profile'] = '{}/{}'.format(
                    guest['hypervisor'], lpar_profile['name'])
                profile['system'] = guest['name']
                activation_profiles.append(profile)

    result = {'System': systems, 'SystemProfile': activation_profiles}
    return result
# create_systems()

def create_data():
    """
    Entry point for data generation, calls all other auxility methods and
    returns a data in json format (dictionary).

    Args:
        None

    Returns:
        str: containing a dictionary in json format

    Raises:
        None
    """
    data = {}
    data.update(create_permissions())
    data.update(create_systems(data))
    data.update(create_network(data))
    data.update(create_storage(data))

    return json.dumps(data, indent=4)
# create_data()

def main():
    """
    Entry point for calling the function from command line.
    """
    print(create_data())
# main()

if __name__ == '__main__':
    main()
