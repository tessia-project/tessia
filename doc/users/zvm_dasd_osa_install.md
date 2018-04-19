<!--
Copyright 2018 IBM Corp.

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
# Installing linux on zVM with DASD volumes and OSA interface

## Pre-requisites

For this task you should have:

- a zVM hypervisor installed on a LPAR;
- `IP address` provided for zVM guest and `MAC-address` (optional);
- a pair of DASD volumes.

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

## Create a new zVM system

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

We are going to create a system for zVM guest `vm70002`. The zVM hypervisor is assumed to be installed on the LPAR `lpar70`.

Let's check if our hypervisor system `lpar70` is already present in the tool:

```
$ tess system list --name lpar70
No results were found.
```

So, we should create the system for hypervisor first. We will use the command `system add`.
The necessary options for the command can be seen in the help menu with `--help`.

```
$ tess system add --name=lpar70 --type=LPAR --hostname=lpar70.domain.com --desc='ZVMs in Testing zone' --project=Testing
Item added successfully.
$ tess system list --name lpar70

Name            : lpar70
Hostname        : lpar70.domain.com
Hypervisor name :
Type            : LPAR
Model           : ZGENERIC
Current state   : AVAILABLE
Owner           : admin
Project         : Testing
Last modified   : 2018-03-22 12:46:02
Modified by     : admin
Description     : ZVMs in Testing zone
```

Let's create zVM system `vm70002` using the host system `lpar70` as its hypervisor:

```
$ tess system add --name=vm70002 --hyp=lpar70 --type=ZVM --hostname=vm70002.domain.com --desc='zVM for testing' --project=Testing
Item added successfully.
$ tess system list --type=ZVM
Name            : vm70002
Hostname        : vm70002.domain.com
Hypervisor name : lpar70
Type            : ZVM
Model           : ZGENERIC
Current state   : AVAILABLE
Owner           : admin
Project         : Testing
Last modified   : 2018-03-22 12:55:48
Modified by     : admin
Description     : zVM for testing
```

The new zVM system `vm70002` is created.

## Create a network interface

We were provided with IP address `192.168.0.30` for our `vm70002` system. Let's check if this address is registered in any subnet.

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

Assume we already know that `lpar70` is located in the `Testing zone`, so check subnets in it:

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
If the proper network zone or the subnet are not registered in the tool, then add them with `net zone-add` and `net subnet-add` commands:

```
tess net zone-add --name='Testing zone' --desc='Network zone for testing systems' --project=Testing
tess net subnet-add --zone='Testing zone' --name='CPC50 shared' --address='192.168.0.0/24' --gw='192.168.0.1' --dns1='192.168.0.5' --desc='CPC50 LPARs and VMs network' --project=Testing
```

For more details see [here](getting_started.md#network-zone).

Let's check if IP address `192.168.0.30` is registered in the subnet:

```
$ tess net ip-list --subnet='CPC50 shared' --ip=192.168.0.30

IP address        : 192.168.0.30
Part of subnet    : CPC50 shared
Owner             : admin
Project           : Testing
Last modified     : 2018-03-22 16:31:49
Modified by       : admin
Description       : IP for zVM vm70002
Associated system :
```

We see our IP address in the `CPC50 shared` subnet.

If this address wasn't found in the subnet ip list, it could be registered with the following command:

```
tess net ip-add --subnet='CPC50 shared' --ip=192.168.0.30 --project='Testing' --desc='IP for zVM vm70002'
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

To see the supported interface types you may use the `system iface-types` command.
We will use OSA card interface type (the name `OSA`) with layer2 mode enabled, so mac address should also be specified.
The provided IP address may be assigned to the interface at once. Don't forget to specify a subnet also, otherwise you will get an error. Let's create the interface:

```
$ tess system iface-add --system=vm70002 --name='default osa' --type=OSA --osname=enccw0.0.f500 --mac=aa:bb:cc:dd:ee:11 --layer2=true --ccwgroup=f500,0.0.f501,0.0.f502 --subnet='CPC50 shared' --ip=192.168.0.30 --desc='default gateway interface'
Item added successfully.
$ tess system iface-list --system=vm70002

Interface name             : default osa
Operating system name      : enccw0.0.f500
System                     : vm70002
Interface type             : OSA
IP address                 : CPC50 shared/192.168.0.30
MAC address                : aa:bb:cc:dd:ee:11
Attributes                 : {'layer2': True, 'ccwgroup': '0.0.f500,0.0.f501,0.0.f502'}
Associated system profiles :
Description                : default gateway interface
```

We can see that the interface is associated with the IP address. And we can also see that the IP address is already associated with the `vm70002` system:

```
$ tess net ip-list --subnet='CPC50 shared' --ip=192.168.0.30

IP address        : 192.168.0.30
Part of subnet    : CPC50 shared
Owner             : admin
Project           : Testing
Last modified     : 2018-03-22 16:31:49
Modified by       : admin
Description       : IP for zVM vm70002
Associated system : vm70002
```

It's all right now.

## Create volumes

Assume that we plan to install linux on the following DASD volumes:

`e1ab`, `e1ac` from the storage server `DS8K22`.

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

The server is there. If it isn't, then use the `storage server-add` command:

```
tess storage server-add --name=DS8K22 --model=DS8800 --type=DASD-FCP --project=Testing --desc='Storage for CPC50'
```

Let's see if perhaps our disks are already registered:

```
$ tess storage vol-list --server=DS8K22 --id=e1ab
No results were found.
$ tess storage vol-list --server=DS8K22 --id=e1ac
No results were found.
```

The disks are not registered. So, let's do it.

By using the help menu for the `storage vol-add` command you can learn which options are necessary to register a volume.
The name of the volume-type for a disk can be learnt with the `vol-types` command.

```
$ tess storage vol-add --server=DS8K22 --type=DASD --id=e1ab --size=20gb --project=Testing --desc='belongs to zVM guest vm70002'
Item added successfully.
$ tess storage vol-add --server=DS8K22 --type=DASD --id=e1ac --size=20gb --project=Testing --desc='belongs to zVM guest vm70002'
Item added successfully.
$ tess storage vol-list --server=DS8K22 --id=e1ab

Volume id                  : e1ab
Storage server             : DS8K22
Volume size                : 18.63 GiB
Volume specifications      : {}
Volume type                : DASD
Attached to system         :
System related attributes  : {}
Associated system profiles :
Attached to storage pool   :
Owner                      : admin
Project                    : Testing
Last modified              : 2018-03-23 09:27:17
Modified by                : admin
Description                : belongs to zVM guest vm70002
$ tess storage vol-list --server=DS8K22 --id=e1ac

Volume id                  : e1ac
Storage server             : DS8K22
Volume size                : 18.63 GiB
Volume specifications      : {}
Volume type                : DASD
Attached to system         :
System related attributes  : {}
Associated system profiles :
Attached to storage pool   :
Owner                      : admin
Project                    : Testing
Last modified              : 2018-03-23 09:27:43
Modified by                : admin
Description                : belongs to zVM guest vm70002
```

The disks are registered but they are not ready yet. We also need to initialize a partition table and to create partitions:

```
$ tess storage part-init --server=DS8K22 --id=e1ab --label=dasd
Partition table successfully initialized.
$ tess storage part-init --server=DS8K22 --id=e1ac --label=dasd
Partition table successfully initialized.
```

To perform the installation we should have at least two partitions - root and swap:

```
$ tess storage part-add --server=DS8K22 --id=e1ab --fs=ext4 --size=10gb --mp=/
Partition successfully added.
$ tess storage part-add --server=DS8K22 --id=e1ac --fs=swap --size=10gb
Partition successfully added.
$ tess storage part-list --server=DS8K22 --id=e1ab

Partition table type: dasd

 number |   size   |   type  | filesystem | mount point | mount options
--------+----------+---------+------------+-------------+---------------
 1      | 9.31 GiB | primary | ext4       | /           |
$ tess storage part-list --server=DS8K22 --id=e1ac

Partition table type: dasd

 number |   size   |   type  | filesystem | mount point | mount options
--------+----------+---------+------------+-------------+---------------
 1      | 9.31 GiB | primary | swap       |             |
```

So, the disks are ready.

**Note**: these actions have no real effect on the disks yet, it's just information stored in tessia's database.
The defined changes will only be applied to the disks at installation time.

## Define an activation profile

There are some steps left that we should complete before installing a zVM guest:

- define an activation profile for the `vm70002` system (`system prof-add`);
- attach our network interface to the system activation profile (`system iface-attach`);
- attach the DASD volumes to the system activation profile (`system vol-attach`).

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

As for a hypervisor profile, CMS on the LPAR `lpar70` is used as a hypervisor profile for the `vm70002` system.
Let's create it first.
Please pay attention that the option `--os=cms` is required in this case for the hypervisor profile:

```
$ tess system prof-add --system=lpar70 --os=cms --name=cms_profile --login=zvm:zvm
Item added successfully.
$ tess system prof-list --system=lpar70

Profile name                : cms_profile
System                      : lpar70
Required hypervisor profile :
Operating system            : cms
Default                     : True
CPU(s)                      : 1
Memory                      : 953.0 MiB
Parameters                  :
Credentials                 : {'passwd': 'zvm', 'user': 'zvm'}
Storage volumes             :
Network interfaces          :
Gateway interface           :
```

So, `cms_profile` may be used as a hypervisor profile required for the zVM system profile. Let's define the activation profile for `vm70002` with the name `vm_profile`:

```
$ tess system prof-add --system=vm70002 --name='vm_profile' --cpu=1 --memory=1024mib --hyp=cms_profile --login='root:mypasswd' --zvm-pass=zvmpasswd
Item added successfully.
$ tess system prof-list --system=vm70002

Profile name                : vm_profile
System                      : vm70002
Required hypervisor profile : lpar70/cms_profile
Operating system            :
Default                     : True
CPU(s)                      : 1
Memory                      : 1.0 GiB
Parameters                  :
Credentials                 :  {'host_zvm': {'passwd': 'zvmpasswd'}, 'passwd': 'mypasswd', 'user': 'root'}
Storage volumes             :
Network interfaces          :
Gateway interface           :
```

Now let's attach our network interface to the `vm70002` system profile:

```
$ tess system iface-attach --system=vm70002 --profile='vm_profile' --iface='default osa'
Network interface attached successfully.
$ tess system iface-list --system=vm70002

Interface name             : default osa
Operating system name      : enccw0.0.f500
System                     : vm70002
Interface type             : OSA
IP address                 : CPC50 shared/192.168.0.30
MAC address                : aa:bb:cc:dd:ee:11
Attributes                 : {'layer2': True, 'ccwgroup': '0.0.f500,0.0.f501,0.0.f502'}
Associated system profiles : [vm_profile]
Description                : default gateway interface
```

Let's also attach the disks to the system profile:

```
$ tess system vol-attach --system=vm70002 --profile=vm_profile --server=DS8K22 --vol=e1ab
Volume attached successfully.
$ tess system vol-attach --system=vm70002 --profile=vm_profile --server=DS8K22 --vol=e1ac
Volume attached successfully.
$ tess storage vol-list --server=DS8K22 --id=e1ab

Volume id                  : e1ab
Storage server             : DS8K22
Volume size                : 18.63 GiB
Volume specifications      : {}
Volume type                : DASD
Attached to system         : vm70002
System related attributes  : {}
Associated system profiles : [vm_profile]
Attached to storage pool   :
Owner                      : admin
Project                    : Testing
Last modified              : 2018-03-23 13:50:37
Modified by                : admin
Description                : belongs to zVM guest vm70002
$ tess storage vol-list --server=DS8K22 --id=e1ac

Volume id                  : e1ac
Storage server             : DS8K22
Volume size                : 18.63 GiB
Volume specifications      : {}
Volume type                : DASD
Attached to system         : vm70002
System related attributes  : {}
Associated system profiles : [vm_profile]
Attached to storage pool   :
Owner                      : admin
Project                    : Testing
Last modified              : 2018-03-23 13:51:01
Modified by                : admin
Description                : belongs to zVM guest vm70002
```

Check the profile for the `vm70002` system now:

```
$ tess system prof-list --system=vm70002

Profile name                : vm_profile
System                      : vm70002
Required hypervisor profile : lpar70/cms_profile
Operating system            :
Default                     : True
CPU(s)                      : 1
Memory                      : 1.0 GiB
Parameters                  :
Credentials                 : {'user': 'root', 'passwd': 'mypasswd',  'host_zvm': {'passwd': 'zvmpasswd'}}
Storage volumes             : [DS8K22/e1ab], [DS8K22/e1ac]
Network interfaces          : [default osa/192.168.0.30]
Gateway interface           :
```

We can see that the network interface and the volumes are associated with the system profile.

## Add the package repository
A package repository must be available for the installation. Let's create a repo for SLES12.3:

```
$ tess repo add --name=SLES12.3-GA --url=http://distro.domain.com/suse/s390x/SLES12.3/DVD/ --os=sles12.3 --kernel='/boot/s390x/linux' --initrd='/boot/s390x/initrd' --project=Testing
Item added successfully.
$ tess repo list

Repository name : SLES12.3-GA
Installable OS  : sles12.3
Network URL     : http://distro.domain.com/suse/s390x/SLES12.3/DVD/
Kernel path     : /boot/s390x/linux
Initrd path     : /boot/s390x/initrd
Owner           : admin
Project         : Testing
Last modified   : 2018-03-23 13:56:25
Modified by     : admin
Description     :
```


## Install the system

Let's perform a SLES installation using the `system autoinstall` command.

For more details about installing see [here](getting_started.md#install-the-system).

```
$ tess system autoinstall --os=sles12.3 --system=vm70002

Request #3 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #2
Waiting for installation output (Ctrl+C to stop waiting)
...
(lots of output ...)
...
2018-03-23 14:47:46 | INFO | new state: post_install
2018-03-23 14:47:46 | INFO | Installation finished successfully
```

So, the installation was successful.
