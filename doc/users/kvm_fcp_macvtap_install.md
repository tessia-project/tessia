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

We suppose that you are already familiar with the [Resources model](resources_model.md).

## Checking the client's configuration

To be sure that you are authenticated check the current configuration (or create an authentication token) with the `tessia conf show` command:


```console
$ tessia conf show

Authentication key in use : e14a813ca971432981e3d6850732aa6b
Key owner login           : user@domain.com
Client API version        : 20160916
Server address            : http://localhost:5000
Server API version        : 20160916
```

For more details see [here](client.md#first-steps).

## Creating a new KVM system

At first look at the supported system types:

```console
$ tessia system types

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

We are going to create a system for a new KVM guest on the LPAR 'lpar68'.

Let's check if our host system 'lpar68' is already present in the tool:

```console
$ tessia system list --type=LPAR

Name            : lpar68
Hostname        : lpar68.mydomain.com
Hypervisor name : cpc80
Type            : LPAR
Model           : ZGENERIC
Current state   : AVAILABLE
Owner           : user@domain.com
Project         : Performance test
Last modified   : 2017-03-30 14:09:17
Modified by     : user@domain.com
Description     : System for database performance tests
```

Yes, it is present. If it isn't you should create it at first. How to do this and also for more details see [here](client.md#creating-your-first-system). 

And what about KVM systems?

```console
$ tessia system list --type=KVM
No results were found.
$
```

Let's create our first KVM system 'kvm25' with IP address '192.168.0.25' provided for it. We will use the command `system add`.
The necessary options for the command can be seen in the help menu with `--help`.

```console
$ tessia system add --name=kvm25 --type=KVM --hostname=192.168.0.25 --desc='KVM for Perf test'
Item added successfully.
$ tessia system list --type=KVM

Name            : kvm25
Hostname        : 192.168.0.25
Hypervisor name :
Type            : KVM
Model           : ZGENERIC
Current state   : AVAILABLE
Owner           : user@domain.com
Project         : Performance test
Last modified   : 2017-03-31 09:58:01
Modified by     : user@domain.com
Description     : KVM for Perf test
```

The field 'Hypervisor name' is empty. It makes sense to associate the created system with a hypervisor. The host system 'lpar68' will be a hypervisor for a KVM guest:

```console
$ tessia system edit --name=kvm25 --hyp=lpar68
Item successfully updated.
$ tessia system list --type=KVM

Name            : kvm25
Hostname        : 192.168.0.25
Hypervisor name : lpar68
Type            : KVM
Model           : ZGENERIC
Current state   : AVAILABLE
Owner           : user@domain.com
Project         : Performance test
Last modified   : 2017-03-31 09:58:01
Modified by     : user@domain.com
Description     : KVM for Perf test
```

The new KVM system 'kvm25' is created.

## Creating a volume

Assume we know the parameters of our FCP disk on which we plan to install the KVM guest:

LUN: `0x10203045`(20G) from the storage server `DS8K22`;

SCSI_WWID: `33005566777fff5f30000000000008888`;

ADAPTER_DEVNO: `1900`, `1940`;

WWPN: `0x50050555050555e3`, `0x50050555051555e3`.

Let's check at first if such storage server is available in the tool:

```console
$ tessia storage server-list

Name           : DS8K22
Hostname       :
Model          : DS8800
Server type    : DASD-FCP
Firmware level :
Owner          : user@domain.com
Project        : Performance test
Last modified  : 2017-03-29 16:10:59
Modified by    : user@domain.com
Description    : Storage for cpc50
```

The server is there. Let's see if perhaps our disk is already registered:

```console
$ tessia storage vol-list --server=DS8K22 --id=1020304500000000
No results were found.
$
```

The disk is not registered. So, let's do it.

By using the help menu for the `storage vol-add` command you can learn which options are necessary to register a volume.
The name of the volume-type for a disk can be learnt with the `vol-types` command.

```console
$ tessia storage vol-add --server=DS8K22 --type=FCP --id=1020304500000000 --size=20gb
Item added successfully.
$ tessia storage vol-list --server=DS8K22 --id=1020304500000000

Volume id                  : 1020304500000000
Storage server             : DS8K22
Volume size                : 19.53GB
Volume specifications      : {}
Volume type                : FCP
Attached to system         :
System related attributes  : {}
Associated system profiles :
Attached to storage pool   :
Owner                      : user@domain.com
Project                    : Performance test
Last modified              : 2017-04-03 14:29:08
Modified by                : user@domain.com
Description                :
```

The disk is registered but it is not enough for FCP disk. To know which attributes should be added use help menu for the command `storage vol-edit`:

```console
$ tessia storage vol-edit --help
Usage: tessia storage vol-edit [OPTIONS]

  change properties of an existing storage volume

Options:
  --server TEXT                 server containing volume  [required]
  --id TEXT                     volume id  [required]
  --newid TEXT                  new volume's id in form volume-id
  --size TEXT                   volume size (i.e. 10gb)
  --type TEXT                   volume type (see vol-types)
  --owner TEXT                  owner login
  --project TEXT                project owning volume
  --desc TEXT                   free form field describing volume
  --mpath BOOLEAN               enable/disable multipath (FCP only)
  --addpath ADAPTER_DEVNO,WWPN  add a FCP path (FCP only)
  --delpath ADAPTER_DEVNO,WWPN  delete a FCP path (FCP only)
  --wwid SCSI_WWID              scsi world wide identifier (FCP only)
  -h, --help                    Show this message and exit.
```

At least one path should be defined for FCP disk with `--addpath ADAPTER_DEVNO,WWPN`. SCSI world wide identifier should also be defined with `--wwid SCSI_WWID`.

In our case we will use multipathing enabled, and we will define two FCP paths:

```console
$ tessia storage vol-edit --server=DS8K22 --id=1020304500000000 --addpath 1900,0x50050555050555e3 --addpath 1940,0x50050555051555e3 --mpath=true --wwid=33005566777fff5f30000000000008888
Item successfully updated.
$ tessia storage vol-list --server=DS8K22 --id=1020304500000000

Volume id                  : 1020304500000000
Storage server             : DS8K22
Volume size                : 19.53GB
Volume specifications      : {'multipath': True, 'adapters': [{'devno': '0.0.1900', 'wwpns': ['50050555050555e3']}, {'devno': '0.0.1940', 'wwpns': ['50050555051555e3']}], 'wwid': '33005566777fff5f30000000000008888'}
Volume type                : FCP
Attached to system         :
System related attributes  : {}
Associated system profiles : [profile2]
Attached to storage pool   :
Owner                      : user@domain.com
Project                    : Performance test
Last modified              : 2017-04-12 12:10:26
Modified by                : user@domain.com
Description                :
```

The disk is ready but it is empty. We also need to initialize  a partition table and to create partitions:

```console
$ tessia storage part-init --server=DS8K22 --id=1020304500000000 --label=msdos
Partition table successfully initialized.   
```

To perform the installation it would be enough to have two partitions - root and swap:

```console
$ tessia storage part-add --server=DS8K22 --id=1020304500000000 --fs=ext4 --size=15gb --mp=/
Partition successfully added.
$ tessia storage part-add --server=DS8K22 --id=1020304500000000 --fs=swap --size=5gb
Partition successfully added.
$ tessia storage part-list --server=DS8K22 --id=1020304500000000

Partition table type: msdos

 number |   size  |   type  | filesystem | mount point | mount options
--------+---------+---------+------------+-------------+---------------
 1      | 14.65GB | primary | ext4       | /           |
 2      | 4.88GB | primary | swap       |             |
```

So, the FCP disk is ready.

## Creating a network interface

We were provided with IP address '192.168.0.25' for our 'kvm25' system. Let's check if this address is registered in any subnet.

At first let's check available network zones and subnets with `net zone-list` and `net subnet-list` commands:

```console
$ tessia net zone-list

Zone name     : Production zone
Owner         : sysadmin@domain.com
Project       : Devops
Last modified : 2017-02-08 10:28:44
Modified by   : sysadmin@domain.com
Description   : Network zone for production systems


Zone name     : Lab1
Owner         : sysadmin@domain.com
Project       : Devops
Last modified : 2017-02-09 10:09:31
Modified by   : sysadmin@domain.com
Description   : Lab1 network infrastructure
```

Assume we already know that our lpar68 is located in the 'Lab1' zone, so check subnets in it:

```console
$ tessia net subnet-list --zone='Lab1'

Subnet name     : CPC50 shared
Network zone    : Lab1
Network address : 192.168.0.0/24
Gateway         : 192.168.0.1
DNS server 1    : 192.168.0.5
DNS server 2    :
VLAN            :
Owner           : sysadmin@domain.com
Project         : Performance test
Last modified   : 2017-02-09 10:04:55
Modified by     : sysadmin@domain.com
Description     : CPC50 LPARs network
```

It looks like the subnet 'CPC50 shared' is suitable for our IP address. Let's check if IP address '192.168.0.25' is registered in the subnet:

```console
$ tessia net ip-list --subnet='CPC50 shared' --ip=192.168.0.25

IP address        : 192.168.0.25
Part of subnet    : CPC50 shared
Owner             : user@domain.com
Project           : Performance test
Last modified     : 2017-04-05 08:51:18
Modified by       : user@domain.com
Description       : For performance measurements in system kvm25
Associated system :
```

We see our IP address in the 'CPC50 shared' subnet.

If this address wasn't found in the subnet ip list, it could be registered with the following command:

```console
tessia net ip-add --subnet='CPC50 shared' --ip=192.168.0.25 --project='Performance test' --desc='For performance measurements in system kvm25'
```

But at first you should ask your **lab administrator**, who usually manages the network infrastructure.

So, the IP address is registered, but it is not associated with the system yet.

Now it's time to create a network interface with the command `system iface-add`. You can see the required options for this command in the help menu:

```console
$ tessia system iface-add --help
Usage: tessia system iface-add [OPTIONS]

  create a new network interface

Options:
  --system TEXT               target system  [required]
  --name TEXT                 interface name  [required]
  --type STRING               interface type (see iface-types)  [required]
  --osname TEXT               interface name in operating system (i.e. en0)
                              [required]
  --mac TEXT                  mac address  [required]
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

To choose a correct id for the interface type you may use the `system iface-types` command. We know already that we will use KVM macvtap interface type with the name 'MACVTAP'.
The provided IP address may be assigned to the interface at once. Don't forget to specify a subnet also, otherwise you will get an error. Let's create the interface:

```console
$ tessia system iface-add --system=kvm25 --name='KVM macvtap' --type=MACVTAP --desc='KVM macvtap interface' --osname=eth0 --hostiface='enccw0.0.1260' --mac=aa:bb:cc:dd:ee:11 --subnet='CPC50 shared' --ip=192.168.0.25 --system=kvm25
Item added successfully.
$ tessia system iface-list --system=kvm25

Interface name             : KVM macvtap
Operating system name      : eth0
System                     : kvm25
Interface type             : MACVTAP
IP address                 : CPC50 shared/192.168.0.25
MAC address                : aa:bb:cc:dd:ee:11
Attributes                 : {'hostiface': 'enccw0.0.1260'}
Associated system profiles :
Description                : KVM macvtap interface
```

We can see that the interface is associated with the IP address. And we can also see that the IP address is already associated with the 'kvm25' system:

```console
$ tessia net ip-list --subnet='CPC50 shared' --ip=192.168.0.25

IP address        : 192.168.0.25
Part of subnet    : CPC50 shared
Owner             : user@domain.com
Project           : Performance test
Last modified     : 2017-04-05 08:51:18
Modified by       : user@domain.com
Description       : For performance measurements in system kvm25
Associated system : kvm25
```

It's all right now.

## Defining an activation profile

There are left several steps that we should complete before installing a KVM guest:

- define an activation profile for the 'kvm25' system (`system prof-add`);
- attach our network interface to the 'kvm25' system (`system iface-attach`);
- attach the FCP disk to the 'kvm25' system (`system vol-attach`).

More details and explanations about an activation profile you can find [here](client.md#defining-an-activation-profile).
Let's first look at the options of the command `system prof-add`:

```console
$ tessia system prof-add --help
Usage: tessia system prof-add [OPTIONS]

  create a new system activation profile

Options:
  --system TEXT        target system  [required]
  --name TEXT          profile name  [required]
  --cpu INTEGER RANGE  number of cpus
  --memory TEXT        memory size (i.e. 1gb)
  --default            set as default for system
  --hyp TEXT           hypervisor profile required for activation
  --login TEXT         user:passwd for admin access to operating system
                       [required]
  -h, --help           Show this message and exit.
```

As for a hypervisor profile, our LPAR 'lpar68' is used as a hypervisor for the 'kvm25' system.
Let's see which profiles are available for 'lpar68':

```console
$ tessia system prof-list --system=s83lp68

Profile name                : profile1
System                      : lpar68
Required hypervisor profile : CPC50/default
Operating system            : rhel7.2
Default                     : True
CPU(s)                      : 2
Memory                      : 1.0GB
Parameters                  :
Credentials                 : {'user': 'root', 'passwd': 'mypasswd'}
Storage volumes             : [DS8K22/3960]
Network interfaces          : [default osa/192.168.0.20]
Gateway interface           :
```

So, 'profile1' may be used as a hypervisor profile required for the KVM system profile. Let's define the activation profile for 'kvm25' with the name 'profile2':

```console
$ tessia system prof-add --system=kvm25 --name='profile2' --cpu=2 --memory=1024mb --login='root:mypasswd' --hyp=profile1
Item added successfully.
$ tessia system prof-list --system=kvm25

Profile name                : profile2
System                      : kvm25
Required hypervisor profile : lpar68/profile1
Operating system            :
Default                     : True
CPU(s)                      : 2
Memory                      : 1.0GB
Parameters                  :
Credentials                 : {'user': 'root', 'passwd': 'mypasswd'}
Storage volumes             :
Network interfaces          :
Gateway interface           :
```

Now let's attach our network interface to the 'kvm25' system:

```console
$ tessia system iface-attach --system=kvm25 --profile='profile2' --iface='KVM macvtap'
Network interface attached successfully.
$ tessia system iface-list --system=kvm25

Interface name             : KVM macvtap
Operating system name      : eth0
System                     : kvm25
Interface type             : MACVTAP
IP address                 : CPC50 shared/192.168.0.25
MAC address                : aa:bb:cc:dd:ee:11
Attributes                 : {'hostiface': 'enccw0.0.1260'}
Associated system profiles : [profile2]
Description                : KVM macvtap interface
```

Let's also attach the FCP disk to the 'kvm25' system:

```console
$ tessia system vol-attach --system=kvm25 --profile=profile2 --server=DS8K22 --vol=1020304500000000
Volume attached successfully.
$ tessia storage vol-list --server=DS8K22 --id=1020304500000000

Volume id                  : 1020304500000000
Storage server             : DS8K22
Volume size                : 19.53GB
Volume specifications      : {'multipath': True, 'adapters': [{'devno': '0.0.1900', 'wwpns': ['50050555050555e3']}, {'devno': '0.0.1940', 'wwpns': ['50050555051555e3']}], 'wwid': '33005566777fff5f30000000000008888'}
Volume type                : FCP
Attached to system         : kvm25
System related attributes  : {}
Associated system profiles : [profile2]
Attached to storage pool   :
Owner                      : user@domain.com
Project                    : Performance test
Last modified              : 2017-04-17 09:52:11
Modified by                : user@domain.com
Description                :
```

Check the profile for the 'kvm25' system now:

```console
$ tessia system prof-list --system=kvm25

Profile name                : profile2
System                      : kvm25
Required hypervisor profile : lpar68/profile1
Operating system            :
Default                     : True
CPU(s)                      : 2
Memory                      : 1.0GB
Parameters                  :
Credentials                 : {'user': 'root', 'passwd': 'mypasswd'}
Storage volumes             : [DS8K22/1020304500000000]
Network interfaces          : [KVM macvtap/192.168.0.25]
Gateway interface           :
```

We can see that the network interface and the volume are associated with the system profile.

## Installing an operating system with an autotemplate

Choose a template for an operating system installation from the autotemplate list:

```console
$  tessia autotemplate list

Template name : SLES12.1
Supported OS  : sles12.1
Owner         : system
Project       : System project
Last modified : 2017-02-08 10:28:43
Modified by   : system
Description   : Template for SLES12.1


Template name : RHEL7.2
Supported OS  : rhel7.2
Owner         : system
Project       : System project
Last modified : 2017-02-08 10:28:43
Modified by   : system
Description   : Template for RHEL7.2
```

For more details about templates and about installing see [here](client.md#installing-an-operating-system-with-an-autotemplate).

Let's perform a RHEL installation:

```console
$ tessia system autoinstall --template=RHEL7.2 --system=kvm25 --profile=profile2

Request #64 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #53
Waiting for installation output (Ctrl+C to stop waiting)
2017-04-18 11:26:30,105|INFO|transport.py(1572)|Connected (version 2.0, client OpenSSH_6.6.1)
2017-04-18 11:26:30,318|INFO|transport.py(1572)|Authentication (password) successful!
2017-04-18 11:26:30,561|INFO|plat_kvm.py(261)|Volume DS8K22/4080408700000000 has no libvirt xml, generating one
2017-04-18 11:26:30,561|INFO|sm_base.py(336)|new state: init
2017-04-18 11:26:30,563|INFO|sm_base.py(339)|new state: collect_info
2017-04-18 11:26:30,597|INFO|sm_base.py(342)|new state: create_autofile
2017-04-18 11:26:30,597|INFO|sm_base.py(281)|generating autofile
2017-04-18 11:26:30,612|INFO|sm_base.py(345)|new state: target_boot
(lots of output ...)
...
...
2017-04-18 11:29:41,212|INFO|sm_base.py(354)|new state: check_installation
2017-04-18 11:29:48,220|WARNING|sm_base.py(130)|connection not available yet, retrying in 5 seconds.
2017-04-18 11:29:53,235|INFO|transport.py(1572)|Connected (version 2.0, client OpenSSH_6.6.1)
2017-04-18 11:29:53,332|INFO|transport.py(1572)|Authentication (password) successful!
2017-04-18 11:29:53,467|INFO|sm_base.py(357)|new state: post_install
2017-04-18 11:29:53,469|INFO|sm_base.py(360)|Installation finished successfully
$
```

The installation finished successfully. Let's take a look at its results. 
First connect via ssh to lpar68 using the credentials from the activation profile for lpar68 'profile1':

```console
$ ssh root@lpar68.mydomain.com
Failed to add the host to the list of known hosts (/home/user/.ssh/known_hosts).
root@lpar68.mydomain.com's password: 
Last login: Tue Apr 18 11:26:57 2017 from laptop.mydomain.com
[root@lpar68 ~]# 
```

Look at the KVM domains which were created on the host:

```console
[root@s83lp68kvm ~]# virsh list --all
setlocale: No such file or directory
 Id    Name                           State
----------------------------------------------------
 1     kvm25                         running
```

Our KVM guest 'kvm25' is running. Let's connect to it using the credentials from the activation profile for kvm25 'profile2' and check the installation results:

```console
[root@s83lp68kvm ~]# virsh -e @  console  kvm25
setlocale: No such file or directory
Connected to domain kvm25
Escape character is @


Red Hat Enterprise Linux Server 7.2 (Maipo)
Kernel 3.10.0-327.el7.s390x on an s390x

9 login: root
Password:
Last login: Tue Apr 18 05:29:53 from tessia-host.domain.com
[root@9 ~]#
[root@9 ~]# cat /etc/os-release
NAME="Red Hat Enterprise Linux Server"
VERSION="7.2 (Maipo)"
ID="rhel"
ID_LIKE="fedora"
VERSION_ID="7.2"
PRETTY_NAME="Red Hat Enterprise Linux Server 7.2 (Maipo)"
ANSI_COLOR="0;31"
CPE_NAME="cpe:/o:redhat:enterprise_linux:7.2:GA:server"
HOME_URL="https://www.redhat.com/"
BUG_REPORT_URL="https://bugzilla.redhat.com/"

REDHAT_BUGZILLA_PRODUCT="Red Hat Enterprise Linux 7"
REDHAT_BUGZILLA_PRODUCT_VERSION=7.2
REDHAT_SUPPORT_PRODUCT="Red Hat Enterprise Linux"
REDHAT_SUPPORT_PRODUCT_VERSION="7.2"
[root@9 ~]# lsblk
NAME   MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
vda    253:0    0   20G  0 disk
+-vda1 253:1    0 14.7G  0 part /
L-vda2 253:2    0  4.9G  0 part [SWAP]
[root@9 ~]# parted /dev/vda print
Model: Virtio Block Device (virtblk)
Disk /dev/vda: 21.5GB
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags:

Number  Start   End     Size    Type     File system     Flags
 1      1049kB  15.7GB  15.7GB  primary  ext4
 2      15.7GB  21.0GB  5243MB  primary  linux-swap(v1)
```

As expected, the disk partitioning corresponds to what we have configured and the operating system version too.

So, the installation was successful.
