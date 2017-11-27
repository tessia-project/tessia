<!--
Copyright 2017 IBM Corp.

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
# Resources model

Tessia keeps an inventory and manages the availability of a myriad of resources that comprise the IT Infrastructure: disks, ip addresses, storage servers, systems, and so on.
In order to effectively track all of them in a way that logically makes sense for the user, the tool defines a model where each type of resource has certain attributes and relationships
with other resources. Below you can find a detailed explanation of each type of resource and how it relates to the others.


## Storage servers

* Associations: [Storage volumes](#storage-volumes-disks)
* Description: a storage server is an entity that contains a collection of storage volumes (or disks). It has attributes like name, type, and model.
This resource is important as it allows to distinguish between multiple volumes that have the same ID but are from different servers for example.

## Storage volumes (disks)

* Associations: [Storage servers](#storage-servers), [System activation profiles](#system-activation-profiles)
* Description: a storage volume represents an actual disk or volume from a storage server (i.e. a DASD or FCP disk, or iSCSI LUN).
When a storage volume is created in the tool is has to belong to an already registered storage server. Once created, the volume is usable by further associating it with a system
activation profile. Once the associated system is activated by using such profile the volume is attached and activated as well.

## Storage pools

* Associations: [Storage volumes](#storage-volumes-disks), [Logical volumes](#logical-volumes)
* Description: as the name suggests the storage pool is an entity whose purpose is to group storage volumes in a logical way so that they can be used as backing store for the creation
of logical volumes. As an analogy with Linux LVM the storage volume is the physical volume (PV), the storage pool is a volume group (VG) and on top of it one or more logical volumes
can be created.

## Logical volumes

* Associations: [Storage pools](#storage-pools), [System activation profiles](#system-activation-profiles)
* Description: this resource has the same purpose of a storage volume (to serve as disks to systems), but it has a different nature as it depends on a logical backing store to exist
(the storage pool). When a logical volume is created it must belong to a previously created storage pool. In order to use the volume it has to be associated with a system activation
profile and will be available once the associated system is activated with such profile, similarly to how it works for storage volumes.

## Network zones

* Associations: [Network subnets](#network-subnets)
* Description: this resource is a logical entity that represents a network infrastructure containing various subnets. Its definition is heavily dependent on the network setup of the
IT infrastructure in question, like switches and firewalls. It can represent for example a network area in a lab, or a private subnet in a KVM hypervisor. The network zones are necessary
because they are the recipient of the network subnets.

## Network subnets

* Associations: [Network zones](#network-zones), [IP addresses](#ip-addresses)
* Description: this resource represents an actual network subnet, which means it has attributes like network address range, gateway, dns servers, and possibly vlan. It always belongs to
a network zone, which means it's possible that two subnets exist with the same network address range, as long as they are in different zones (as it is the case for actual network
infrastructures).

## IP addresses

* Associations: [Network subnets](#network-subnets), [System network interfaces](#system-network-interfaces)
* Description: represents an actual IP address in a given subnet. The address is usable through association with a network interface of a system. The network interface is in turn associated
with a system activation profile and once the system is activated with such profile the network interface is activated and configured with the associated IP address.

## Systems

* Associations: [System network interfaces](#system-network-interfaces), [System activation profiles](#system-activation-profiles), [Storage volumes](#storage-volumes-disks), [Logical volumes](#logical-volumes)
* Description: this is the central resource representing an actual machine or guest, depending on its type (i.e. System z CPC or KVM guest). A system has network interfaces and volumes
associated and can be activated using different combinations of them. Each combination is represented by a system activation profile.

## System network interfaces

* Associations: [Systems](#systems), [IP addresses](#ip-addresses)
* Description: Every system that needs network communication capability needs a network interface associated, thus the purpose of this resource type. A network interface is always created
as part of a system, and its type is dependent on the system type (can be an actual OSA port on a System z LPAR or virtual libvirt-based if it's a KVM guest). In order to be used
the interface has to be associated with one of the activation profiles of its system and is activated as part of the system activation.

## System activation profiles

* Associations: [Systems](#systems), [System network interfaces](#system-network-interfaces), [Storage volumes](#storage-volumes-disks), [Logical Volumes](#logical-volumes)
* Description: the concept of activation profiles provides flexibility in the usage of a system as it allows different combinations of resources and operating systems to be used for the same
system. For example, one might like to simultaneously perform tests on a KVM guest with one profile using macvtap interface and FCP backed disks running Ubuntu and another profile with
a Openvswitch interface with qcow backed disks using RHEL. This is possible by creating two activation profiles and associating the correspondent resources to each of them.
