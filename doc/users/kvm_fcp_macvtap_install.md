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
# Installing a KVM guest with FCP disk and MACVTAP interface

## Pre-requisites

For this task you should have:

- KVM hypervisor installed on a LPAR;
- FCP disk parameters: `LUN`, `ADAPTER_DEVNO` and `WWPN` (with multipathing or not),`SCSI_WWID`;
- `IP address` provided for a KVM guest and `MAC-address`.

We assume that you are already familiar with the [Resources model](resources_model.md) and with the [Getting started](getting_started.md) section.

## Create a project

We assume that you are currently using the admin token and that you are logged in as the admin user:

```
$ tess conf show

Authentication key in use : 39be276190c045d59cb684e59a53d386
Key owner login           : admin
Client API version        : 20160916
Server address            : https://server.domain.com:5000
Server API version        : 20160916
```

First of all let's create our project `Testing`:

```
$ tess perm project-add --name='Testing' --desc='Client testing'
Item added successfully.
$ tess perm project-list

Name        : Admins
Description : Group for built-in resources and admin users

Name        : Testing
Description : Client testing
```

## Create a new KVM system

First look at the supported system types:

```
$ tess system types

Type name    : KVM
Architecture : s390x
Description  : System z KVM guest


Type name    : ZVM
Architecture : s390x
Description  : zVM guest


Type name    : LPAR
Architecture : s390x
Description  : System z LPAR


Type name    : CPC
Architecture : s390x
Description  : System z CPC
```

We are going to create a system for a new KVM guest on the LPAR `lpar68`.

Let's check if our hypervisor system `lpar68` is already present in the tool:

```
$ tess system list --type=LPAR

Name            : lpar68
Hostname        : lpar68.domain.com
Hypervisor name : cpc50
Type            : LPAR
Model           : ZGENERIC
Current state   : AVAILABLE
Owner           : admin
Project         : Testing
Last modified   : 2018-03-27 09:20:39
Modified by     : admin
Description     : System for testing
```

Yes, it is present. If it isn't, you should create it first using the `system add` command:

```
tess system add --name=cpc50 --type=CPC --hostname=cpc50.domain.com --desc='CPC in Testing zone' --project=Testing
tess system add --name=lpar68 --hyp=cpc50 --type=LPAR --hostname=lpar68.domain.com --desc='System for testing' --project=Testing
```

For more details see [here](getting_started.md#target-system-lpar).

And what about KVM systems?

```
$ tess system list --type=KVM
No results were found.
```

Let's create our first KVM system `kvm25` with IP address `192.168.0.25` provided for it. We will use the command `system add`.
The necessary options for the command can be seen in the help menu with `--help`.

```
$ tess system add --name=kvm25 --type=KVM --hostname=192.168.0.25 --desc='KVM for Testing' --project=Testing
Item added successfully.
$ tess system list --type=KVM

Name            : kvm25
Hostname        : 192.168.0.25
Hypervisor name :
Type            : KVM
Model           : ZGENERIC
Current state   : AVAILABLE
Owner           : admin
Project         : Testing
Last modified   : 2018-03-27 09:28:44
Modified by     : admin
Description     : KVM for Testing
```

The field `Hypervisor name` is empty. It makes sense to associate the created system with a hypervisor. The host system `lpar68` will be a hypervisor for a KVM guest:

```
$ tess system edit --name=kvm25 --hyp=lpar68
Item successfully updated.
$ tess system list --type=KVM

Name            : kvm25
Hostname        : 192.168.0.25
Hypervisor name : lpar68
Type            : KVM
Model           : ZGENERIC
Current state   : AVAILABLE
Owner           : admin
Project         : Testing
Last modified   : 2018-03-27 09:28:44
Modified by     : admin
Description     : KVM for Testing
```
In fact a hypervisor may be associated with the system at the first step when using the `system add` command.

The new KVM system `kvm25` is created.

## Create a volume

Assume we know the parameters of our FCP disk on which we plan to install the KVM guest:

LUN: `0x10203045`(20G) from the storage server `DS8K22`;

SCSI_WWID: `33005566777fff5f30000000000008888`;

ADAPTER_DEVNO: `1900`, `1940`;

WWPN: `0x50050555050555e3`, `0x50050555051555e3`.

Let's check first if such storage server is available in the tool:

```
$ tess storage server-list

Name           : DS8K22
Hostname       :
Model          : DS8800
Server type    : DASD-FCP
Firmware level :
Owner          : admin
Project        : Testing
Last modified  : 2018-03-23 09:08:24
Modified by    : admin
Description    : Storage for cpc50
```

The server is there. If it isn't, it can be added with the `storage server-add` command:

```
tess storage server-add --name=DS8K22 --model=DS8800 --type=DASD-FCP --project=Testing --desc='Storage for CPC50'
```

Let's see if perhaps our disk is already registered:

```
$ tess storage vol-list --server=DS8K22 --id=1020304500000000
No results were found.
```

The disk is not registered. Let's do it.

By using the help menu for the `storage vol-add` command you can learn which options are necessary to register a volume:

```
$ tess storage vol-add --help
Usage: tess storage vol-add [OPTIONS]

  create a new storage volume

Options:
  --server TEXT              target storage server  [required]
  --id VOLUME_ID             volume id  [required]
  --size TEXT                volume size (i.e. 10gb)  [required]
  --type TEXT                volume type (see vol-types)  [required]
  --owner TEXT               owner login
  --project TEXT             project owning volume
  --desc TEXT                free form field describing volume
  --mpath BOOLEAN            enable/disable multipath (FCP only)
  --path ADAPTER_DEVNO,WWPN  add a FCP path (FCP only)
  --wwid SCSI_WWID           scsi world wide identifier (FCP only)
  -h, --help                 Show this message and exit.
```

The name of the volume-type for a disk can be learnt with the `storage vol-types` command.

At least one path should be defined for FCP disk with `--addpath ADAPTER_DEVNO,WWPN`. SCSI world wide identifier should also be defined with `--wwid SCSI_WWID`.
In our case we will use multipathing enabled, and we will define two FCP paths:

```
$ tess storage vol-add --server=DS8K22 --type=FCP --id=1020304500000000 --size=20gb --project=Testing --path 1900,0x50050555050555e3 --path 1940,0x50050555051555e3 --mpath=true --wwid=33005566777fff5f30000000000008888
Item added successfully.
$ tess storage vol-list --server=DS8K22 --id=1020304500000000

Volume id                  : 1020304500000000
Storage server             : DS8K22
Volume size                : 18.63 GiB
Volume specifications      : {'adapters': [{'devno': '0.0.1900', 'wwpns': ['50050555050555e3']}, {'devno': '0.0.1940', 'wwpns': ['50050555051555e3']}], 'wwid': '33005566777fff5f30000000000008888', 'multipath': True}
Volume type                : FCP
Attached to system         :
System related attributes  : {}
Associated system profiles :
Attached to storage pool   :
Owner                      : admin
Project                    : Testing
Last modified              : 2018-03-27 09:53:23
Modified by                : admin
Description                :
```

The disk is ready but it is empty. We also need to initialize a partition table and to create partitions:

```
$ tess storage part-init --server=DS8K22 --id=1020304500000000 --label=msdos
Partition table successfully initialized.
```

To perform the installation it would be enough to have two partitions - root and swap:

```
$ tess storage part-add --server=DS8K22 --id=1020304500000000 --fs=ext4 --size=10gb --mp=/
Partition successfully added.
$ tess storage part-add --server=DS8K22 --id=1020304500000000 --fs=swap --size=10gb
Partition successfully added.
$ tess storage part-list --server=DS8K22 --id=1020304500000000

Partition table type: msdos

 number |   size   |   type  | filesystem | mount point | mount options
--------+----------+---------+------------+-------------+---------------
 1      | 9.31 GiB | primary | ext4       | /           |
 2      | 9.31 GiB | primary | swap       |             |
```

So, the FCP disk is ready.

**Note**: this action has no real effect on the disk yet, it's just information stored in tessia's database.
The defined changes will only be applied to the disk at installation time.

## Create a network interface

We were provided with IP address `192.168.0.25` for our `kvm25` system. Let's check if this address is registered in any subnet.

First let's check available network zones and subnets with `net zone-list` and `net subnet-list` commands:

```
$ tess net zone-list

Zone name     : Production zone
Owner         : admin
Project       : Devops
Last modified : 2017-02-08 10:28:44
Modified by   : admin
Description   : Network zone for production systems


Zone name     : Testing zone
Owner         : admin
Project       : Testing
Last modified : 2018-03-22 16:30:16
Modified by   : admin
Description   : Network zone for testing systems
```

Assume we already know that our lpar68 is located in the `Testing zone` zone, so check subnets in it:

```
$ tess net subnet-list --zone='Testing zone'

Subnet name     : CPC50 shared
Network zone    : Testing zone
Network address : 192.168.0.0/24
Gateway         : 192.168.0.1
DNS server 1    : 192.168.0.5
DNS server 2    :
VLAN            :
Owner           : admin
Project         : Testing
Last modified   : 2018-03-22 16:30:57
Modified by     : admin
Description     : CPC50 LPARs and VMs network
```

It looks like the subnet `CPC50 shared` is suitable for our IP address.
If the proper network zone or the subnet are not registered in the tool, they can be added with `net zone-add` and `net subnet-add` commands:

```
tess net zone-add --name='Testing zone' --desc='Network zone for testing systems' --project=Testing
tess net subnet-add --zone='Testing zone' --name='CPC50 shared' --address='192.168.0.0/24' --gw='192.168.0.1' --dns1='192.168.0.5' --desc='CPC50 LPARs and VMs network' --project=Testing
```

For more details see [here](getting_started.md#network-zone).

Let's check if IP address `192.168.0.25` is registered in the subnet:

```
$ tess net ip-list --subnet='CPC50 shared' --ip=192.168.0.25

IP address        : 192.168.0.25
Part of subnet    : CPC50 shared
Owner             : admin
Project           : Testing
Last modified     : 2018-03-22 16:31:49
Modified by       : admin
Description       : IP for system kvm25
Associated system :
```

We see our IP address in the `CPC50 shared` subnet.

If this address wasn't found in the subnet ip list, it could be registered with the following command:

```
tess net ip-add --subnet='CPC50 shared' --ip=192.168.0.25 --project='Testing' --desc='IP for system kvm25'
```

So, the IP address is registered, but it is not associated with the system yet.

Now it's time to create a network interface with the command `system iface-add`. You can see the required options for this command in the help menu:

```
$ tess system iface-add --help
Usage: tess system iface-add [OPTIONS]

  create a new network interface

Options:
  --system NAME               target system  [required]
  --name NAME                 interface name  [required]
  --type STRING               interface type (see iface-types)  [required]
  --osname NAME               interface name in operating system (i.e. en0)
                              [required]
  --mac TEXT                  mac address
  --subnet TEXT               subnet of ip address to be assigned
  --ip TEXT                   ip address to be assigned to interface
  --layer2 BOOLEAN            enable layer2 mode (OSA only)
  --ccwgroup READ,WRITE,DATA  device channels (OSA only)
  --portno TEXT               port number (OSA only)
  --portname TEXT             port name (OSA only)
  --hostiface TEXT            host iface to bind (KVM only)
  --libvirt XML_FILE          libvirt definition file (KVM only)
  --desc TEXT                 free form field describing interface
  -h, --help                  Show this message and exit.
```

To choose a correct id for the interface type you may use the `system iface-types` command. We know already that we will use KVM macvtap interface type with the name `MACVTAP`.
The provided IP address may be assigned to the interface at once. Don't forget to specify a subnet also, otherwise you will get an error. Let's create the interface:

```
$ tess system iface-add --system=kvm25 --name='KVM macvtap' --type=MACVTAP --desc='KVM macvtap interface' --osname=eth0 --hostiface='enccw0.0.f500' --mac=aa:bb:cc:dd:ee:11 --subnet='CPC50 shared' --ip=192.168.0.25 --system=kvm25
Item added successfully.
$ tess system iface-list --system=kvm25

Interface name             : KVM macvtap
Operating system name      : eth0
System                     : kvm25
Interface type             : MACVTAP
IP address                 : CPC50 shared/192.168.0.25
MAC address                : aa:bb:cc:dd:ee:11
Attributes                 : {'hostiface': 'enccw0.0.f500'}
Associated system profiles :
Description                : KVM macvtap interface
```

We can see that the interface is associated with the IP address. And we can also see that the IP address is already associated with the `kvm25` system:

```
$ tess net ip-list --subnet='CPC50 shared' --ip=192.168.0.25

IP address        : 192.168.0.25
Part of subnet    : CPC50 shared
Owner             : admin
Project           : Testing
Last modified     : 2018-03-22 16:31:49
Modified by       : admin
Description       : IP for system kvm25
Associated system : kvm25
```

It's all right now.

## Define an activation profile

There are some steps left that we should complete before installing a KVM guest:

- define an activation profile for the `kvm25` system (`system prof-add`);
- attach our network interface to the system activation profile (`system iface-attach`);
- attach the FCP disk to the system activation profile (`system vol-attach`).

More details and explanations about an activation profile you can find [here](getting_started.md#system-activation-profile).
Let's first look at the options of the command `system prof-add`:

```
$ tess system prof-add --help
Usage: tess system prof-add [OPTIONS]

  create a new system activation profile

Options:
  --system NAME    target system  [required]
  --name NAME      profile name  [required]
  --cpu INTEGER    number of cpus
  --memory TEXT    memory size (i.e. 1gb)
  --default        set as default for system
  --hyp NAME       hypervisor profile required for activation
  --login LOGIN    user:passwd for admin access to operating system
                   [required]
  --os NAME        operating system (if installed manually)
  --zvm-pass TEXT  password for access to zvm hypervisor (zVM guests only)
  --zvm-by TEXT    byuser for access to zvm hypervisor (zVM guests only)
  -h, --help       Show this message and exit.
```

As for a hypervisor profile, our LPAR `lpar68` is used as a hypervisor for the `kvm25` system.
Let's first create a profile for `lpar68`:

```
$ tess system prof-add --system=lpar68 --name='profile1' --cpu=4 --memory=2gib --login='root:hyp_passwd'
Item added successfully.
$ tess system prof-list --system=lpar68

Profile name                : profile1
System                      : lpar68
Required hypervisor profile :
Operating system            :
Default                     : True
CPU(s)                      : 4
Memory                      : 2.0 GiB
Parameters                  :
Credentials                 : {'user': 'root', 'passwd': 'hyp_passwd'}
Storage volumes             :
Network interfaces          :
Gateway interface           :
```

So, `profile1` may be used as a hypervisor profile.

Let's define the activation profile for `kvm25` with the name `profile2`:

```
$ tess system prof-add --system=kvm25 --name='profile2' --cpu=2 --memory=1gib --login='root:mypasswd' --hyp=profile1
Item added successfully.
$ tess system prof-list --system=kvm25

Profile name                : profile2
System                      : kvm25
Required hypervisor profile : lpar68/profile1
Operating system            :
Default                     : True
CPU(s)                      : 2
Memory                      : 1.0 GiB
Parameters                  :
Credentials                 : {'user': 'root', 'passwd': 'mypasswd'}
Storage volumes             :
Network interfaces          :
Gateway interface           :
```

Now let's attach our network interface to the `kvm25` system profile:

```
$ tess system iface-attach --system=kvm25 --profile='profile2' --iface='KVM macvtap'
Network interface attached successfully.
$ tess system iface-list --system=kvm25

Interface name             : KVM macvtap
Operating system name      : eth0
System                     : kvm25
Interface type             : MACVTAP
IP address                 : CPC50 shared/192.168.0.25
MAC address                : aa:bb:cc:dd:ee:11
Attributes                 : {'hostiface': 'enccw0.0.f500'}
Associated system profiles : [profile2]
Description                : KVM macvtap interface
```

Let's also attach the FCP disk to the system profile:

```
$ tess system vol-attach --system=kvm25 --profile=profile2 --server=DS8K22 --vol=1020304500000000
Volume attached successfully.
$ tess storage vol-list --server=DS8K22 --id=1020304500000000

Volume id                  : 1020304500000000
Storage server             : DS8K22
Volume size                : 18.63 GiB
Volume specifications      : {'multipath': True, 'adapters': [{'devno': '0.0.1900', 'wwpns': ['50050555050555e3']}, {'devno': '0.0.1940', 'wwpns': ['50050555051555e3']}], 'wwid': '33005566777fff5f30000000000008888'}
Volume type                : FCP
Attached to system         : kvm25
System related attributes  : {}
Associated system profiles : [profile2]
Attached to storage pool   :
Owner                      : admin
Project                    : Testing
Last modified              : 2018-03-27 09:53:23
Modified by                : admin
Description                :
```

Check the profile for the `kvm25` system now:

```
$ tess system prof-list --system=kvm25

Profile name                : profile2
System                      : kvm25
Required hypervisor profile : lpar68/profile1
Operating system            :
Default                     : True
CPU(s)                      : 2
Memory                      : 976.0 MiB
Parameters                  :
Credentials                 : {'user': 'root', 'passwd': 'mypasswd'}
Storage volumes             : [DS8K22/1020304500000000]
Network interfaces          : [KVM macvtap/192.168.0.25]
Gateway interface           :
```

We can see that the network interface and the volume are associated with the system profile.

## Add the package repository

A package repository must be available for the installation. Let's create a repo for RHEL7.4:

```
$ tess repo add --name=RHEL7.4-GA --url=http://distro.domain.com/redhat/s390x/RHEL7.4/DVD/ --os=rhel7.4 --kernel=images/kernel.img --initrd=images/initrd.img --project=Testing
Item added successfully.
$ tess repo list

Repository name : RHEL7.4-GA
Installable OS  : rhel7.4
Network URL     : http://distro.domain.com/redhat/s390x/RHEL7.4/DVD/
Kernel path     : images/kernel.img
Initrd path     : images/initrd.img
Owner           : admin
Project         : Testing
Last modified   : 2018-03-27 14:17:21
Modified by     : admin
Description     :
```


## Install the system

Let's perform a RHEL installation using the `system autoinstall` command.

For more details about installing see [here](getting_started.md#install-the-system).

```
$ tess system autoinstall --os=rhel7.4 --system=kvm25 --profile=profile2

Request #3 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #2
Waiting for installation output (Ctrl+C to stop waiting)
2018-03-28 09:37:18 | INFO | Applying user-defined libvirt xml for volume DS8K22/1020304500000000
2018-03-28 09:37:18 | INFO | new state: init
2018-03-28 09:37:18 | INFO | new state: collect_info
2018-03-28 09:37:18 | INFO | auto-generated password for VNC is qxmR5VAz
2018-03-28 09:37:18 | INFO | new state: create_autofile
2018-03-28 09:37:18 | INFO | generating autofile
2018-03-28 09:37:18 | INFO | new state: target_boot
...
(lots of output ...)
...
2018-03-28 09:40:08 | INFO | new state: post_install
2018-03-28 09:40:08 | INFO | Installation finished successfully
```

The installation finished successfully. Let's take a look at its results.
First connect via ssh to `lpar68` using the credentials from the activation profile `profile1`
and look at the KVM domains which were created on the host:

```
[root@lpar68 ~]# virsh list --all
 Id    Name                           State
----------------------------------------------------
 1     kvm25                         running
```

Our KVM guest `kvm25` is running. Let's connect to it using the credentials from the activation profile `profile2` and check the installation results:

```
[root@lpar68 ~]# virsh -e @ console kvm25
Connected to domain kvm25
Escape character is @

Red Hat Enterprise Linux Server 7.4 (Maipo)
Kernel 3.10.0-693.el7.s390x on an s390x

9 login: root
Password:
Last login: Wed Mar 28 05:40:35 from tessia-host.domain.com
[root@9 ~]# cat /etc/os-release
NAME="Red Hat Enterprise Linux Server"
VERSION="7.4 (Maipo)"
ID="rhel"
ID_LIKE="fedora"
VARIANT="Server"
VARIANT_ID="server"
VERSION_ID="7.4"
PRETTY_NAME="Red Hat Enterprise Linux Server 7.4 (Maipo)"
ANSI_COLOR="0;31"
CPE_NAME="cpe:/o:redhat:enterprise_linux:7.4:GA:server"
HOME_URL="https://www.redhat.com/"
BUG_REPORT_URL="https://bugzilla.redhat.com/"

REDHAT_BUGZILLA_PRODUCT="Red Hat Enterprise Linux 7"
REDHAT_BUGZILLA_PRODUCT_VERSION=7.4
REDHAT_SUPPORT_PRODUCT="Red Hat Enterprise Linux"
REDHAT_SUPPORT_PRODUCT_VERSION="7.4"
[root@9 ~]# lsblk
NAME   MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
vda    253:0    0   20G  0 disk
├─vda1 253:1    0  9.3G  0 part /
└─vda2 253:2    0  9.3G  0 part [SWAP]
[root@9 ~]# parted /dev/vda print
Model: Virtio Block Device (virtblk)
Disk /dev/vda: 21.5GB
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags:

Number  Start   End     Size    Type     File system     Flags
 1      1049kB  10.0GB  9999MB  primary  ext4
 2      10.0GB  20.0GB  9999MB  primary  linux-swap(v1)
```

As expected, the disk partitioning corresponds to what we have configured and the operating system version too.

So, the installation was successful.
