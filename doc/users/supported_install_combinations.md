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

This page contains a detailed view of the current supported combinations and usage restrictions regarding system installation.

- [Network and volumes on LPAR](#network-and-volumes-on-lpar)
- [Network and volumes on z/VM](#network-and-volumes-on-zvm)
- [Network and volumes on KVM](#network-and-volumes-on-kvm)
- [Partitioning on LPAR](#partitioning-on-lpar)
- [Partitioning on z/VM](#partitioning-on-zvm)
- [Partitioning on KVM](#partitioning-on-kvm)

# Network and volumes on LPAR

| Distro                   | RHEL | SLES | Ubuntu |
| ------                   | ---- | ---- | -----  |
| volume type DASD         | Y    | Y    | Y      |
| volume type FCP          | Y    | Y    | Y      |
| multipath on (FCP only)  | Y    | Y    | Y      |
| multipath off (FCP only) | Y    | Y    | Y      |
| network interface OSA    | Y    | Y    | Y      |
| layer2 on (OSA only)     | Y    | Y    | Y      |
| layer2 off (OSA only)    | Y    | Y    | Y      |

# Network and volumes on z/VM

The supported network and volumes combinations for z/VM are the same as for LPAR.

# Network and volumes on KVM

| Distro                            | RHEL | SLES | Ubuntu |
| ------                            | ---- | ---- | ------ |
| volume type DASD (through virtio) | N    | N    | Y      |
| volume type FCP (through virtio)  | Y    | Y    | Y      |
| multipath on (FCP only)           | Y    | Y    | Y      |
| multipath off (FCP only)          | N    | N    | N      |
| network interface MACVTAP         | Y    | Y    | Y      |

# Partitioning on LPAR

Remarks:

- due to a DASD architecture constraint, DASD volumes can only use the partition table type `dasd`.
- `gpt` partition tables are not supported, which means currently only the `msdos` type can be used for FCP volumes.

| Distro               | RHEL | SLES | Ubuntu |
| -----                | ---  | ---  | ---    |
| Ext2                 | Y    | Y    | Y      |
| Ext3                 | Y    | Y    | Y      |
| Ext4                 | Y    | Y    | Y      |
| XFS                  | Y    | N    | Y      |
| BtrFS (not '/' only) | N    | N    | Y      |
| ReiserFS             | N    | N    | N      |
| JFS                  | N    | N    | N      |
| FAT16                | N    | N    | N      |
| FAT32                | N    | N    | N      |
| set mount options    | Y    | Y    | Y      |

# Partitioning on z/VM

The supported partitioning combinations for z/VM are the same as for LPAR.

# Partitioning on KVM

| Distro               | RHEL | SLES | Ubuntu |
| -----                | ---  | ---  | ---    |
| Ext2                 | Y    | Y    | Y      |
| Ext3                 | Y    | Y    | Y      |
| Ext4                 | Y    | Y    | Y      |
| XFS                  | Y    | N    | Y      |
| BtrFS (not '/' only) | N    | N    | Y      |
| ReiserFS             | N    | N    | N      |
| JFS                  | N    | N    | N      |
| FAT16                | N    | N    | N      |
| FAT32                | N    | N    | N      |
| set mount options    | Y    | Y    | Y      |
