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
# Supported installation combinations

This page contains a detailed view of the current supported combinations and usage restrictions regarding system installation with default templates.

- [Network and volumes on LPAR](#network-and-volumes-on-lpar)
- [Network and volumes on z/VM](#network-and-volumes-on-zvm)
- [Network and volumes on KVM](#network-and-volumes-on-kvm)
- [Partitioning on LPAR](#partitioning-on-lpar)
- [Partitioning on z/VM](#partitioning-on-zvm)
- [Partitioning on KVM](#partitioning-on-kvm)
- [Distro as KVM hypervisor](#distro-as-kvm-hypervisor)
- [ROCE cards on LPAR](#roce-cards-on-lpar)

# Network and volumes on LPAR

| Distro                   | RHEL | SLES | Ubuntu | Fedora*|
| ------                   | ---  | ---  | -----  | -----  |
| volume type DASD         | Y    | Y    | Y**    | Y      |
| volume type FCP          | Y    | Y    | Y      | Y      |
| multipath on (FCP only)  | Y    | Y    | Y      | Y      |
| multipath off (FCP only) | Y    | Y    | Y      | Y      |
| network interface OSA    | Y    | Y    | Y      | Y      |
| layer2 on (OSA only)     | Y    | Y    | Y      | Y      |
| layer2 off (OSA only)    | Y    | Y    | Y      | Y      |

[\*] - latest supported version (Fedora33)  
[\*\*] - except Ubuntu 16.04 (GA) due to distro installer issues, for details see [ReleaseNotes](https://wiki.ubuntu.com/XenialXerus/ReleaseNotes#IBM_LinuxONE_and_z_Systems_specific_known_issues)

# Network and volumes on z/VM

Except Ubuntu16.04.1 which won't boot its installer's initrd on z/VM, the supported network and volumes combinations for z/VM are the same as for LPAR.

# Network and volumes on KVM

| Distro                            | RHEL | SLES | Ubuntu | Fedora*|
| ------                            | ---  | ---  | -----  | -----  |
| volume type DASD (through virtio) | N    | Y**  | Y      | N      |
| volume type FCP (through virtio)  | Y    | Y    | Y      | Y      |
| multipath on (FCP only)           | Y    | Y    | Y      | Y      |
| multipath off (FCP only)          | Y    | Y    | Y      | Y      |
| network interface MACVTAP         | Y    | Y    | Y      | Y      |

[\*] - latest supported version (Fedora33)      
[\*\*] - except SLES15.0 due to an AutoYaST bug and SLES15.2   

# Partitioning on LPAR

Remarks:

- due to a DASD architecture constraint, DASD volumes can only use the partition table type `dasd`.
- FCP volumes can be used with `gpt` and `msdos` partition tables.

| Distro               | RHEL | SLES | Ubuntu | Fedora |
| -----                | ---  | ---  | -----  | -----  |
| dasd                 | Y    | Y    | Y      | Y      |
| gpt                  | N    | Y    | Y      | N      |
| msdos                | Y    | Y    | Y      | Y      |

| Distro               | RHEL | SLES | Ubuntu | Fedora |
| -----                | ---  | ---  | -----  | -----  |
| Ext2                 | Y    | Y    | Y      | Y      |
| Ext3                 | Y    | Y    | Y      | Y      |
| Ext4                 | Y    | Y    | Y      | Y      |
| XFS                  | Y    | Y    | Y      | Y      |
| BtrFS                | N    | Y*   | N      | N      |
| ReiserFS             | N    | N    | N      | Y      |
| JFS                  | N    | N    | N      | N      |
| FAT16                | N    | N    | N      | N      |
| FAT32                | N    | N    | N      | N      |
| set mount options    | Y    | Y    | Y      | Y      |

[*] - except SLES12.\*      

# Partitioning on z/VM

The supported partitioning combinations for z/VM are the same as for LPAR.

# Partitioning on KVM

| Distro               | RHEL | SLES | Ubuntu | Fedora |
| -----                | ---  | ---  | -----  | -----  |
| dasd                 | Y    | Y    | Y      | Y      |
| gpt                  | N    | Y    | N      | N      |
| msdos                | Y    | Y    | Y      | Y      |

| Distro               | RHEL | SLES | Ubuntu | Fedora |
| -----                | ---  | ---  | -----  | -----  |
| Ext2                 | Y    | Y    | Y      | Y      |
| Ext3                 | Y    | Y    | Y      | Y      |
| Ext4                 | Y    | Y    | Y      | Y      |
| XFS                  | Y    | Y    | Y      | Y      |
| BtrFS                | N    | Y*   | N      | N      |
| ReiserFS             | N    | N    | N      | Y      |
| JFS                  | N    | N    | N      | N      |
| FAT16                | N    | N    | N      | N      |
| FAT32                | N    | N    | N      | N      |
| set mount options    | Y    | Y    | Y      | Y      |

[*] - except SLES12.\*      

# Distro as KVM hypervisor

| Distro                         | RHEL | SLES | Ubuntu | Fedora*|
| ------                         | ---  | ---  | -----  | -----  |
| using distro as KVM hypervisor | Y**  | Y    | Y***   | Y      |

[\*] - latest supported version (Fedora33)  
[\*\*] - except RHEL7.\*   
[\*\*\*] - except Ubuntu20.\*   

# ROCE cards on LPAR

| Distro/interface_name  | enp#s# | ens# |
| ------                 | ------ | ---- |
| RHEL7.9                |   Y    |  Y   |
| RHEL8.1                |   Y    |  Y   |
| RHEL9.1                |   Y    |  Y   |
| SLES12.5               |   Y    |  N   |
| SLES15.2               |   Y    |  N   |
| SLES15.5               |   N    |  Y   |
| UBUNTU18.04.5          |   Y    |  Y   |
| UBUNTU20.04.1          |   Y    |  N   |
| UBUNTU22.04.1          |   N    |  Y   |
| UBUNTU23.04            |   Y    |  Y   |

