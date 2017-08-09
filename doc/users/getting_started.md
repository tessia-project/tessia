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
# Getting started

If you are not yet familiar with the different types of resources available in the tool we strongly suggest that you read about them first. You can learn about tessia's resources
model [here](resources_model.md).

## Initial configuration

Upon first usage the client needs to learn two things from you:

- where the API server is located
- what are your credentials (login/password) in order to create an authentication token to validate you with the server

If you have those already configured, just skip the next two sections.

### API server hostname

If the server is running under HTTPS (most likely), you have to place a copy of the SSL certificate beforehand either in `~/.tessia-cli/ca.crt` (local user) or
`/etc/tessia-cli/ca.crt` (global). If you don't do so, you will see an error like this:

```
[user@host ~]$ tessia conf set-server https://server.domain.com:5000
Error: The validation of the server's SSL certificate failed. In order to assure the connection is safe, place a copy of the trusted CA's certificate file in /home/user/.tessia-cli/ca.crt and try again.
```

The CA's certificate file is usually provided by the server administrator through a trusted link or some other trusted method. You should verify with your sysadmin how to download it.

Once the certificate file is available, we can enter the API server's hostname successfully:

```
[user@host ~]$ tessia conf set-server https://server.domain.com:5000
Server successfully configured.
```

### User credentials

The client must generate an authentication token for communication with the server. Here's how to do it:

```console
[user@host ~]$ tessia conf key-gen
Login: user@domain.com
Password: 
Key successfully created and added to client configuration.
[user@host ~]$ 
```

Let's confirm that the operation worked by checking the client configuration:
```
[user@host ~]$ tessia conf show

Authentication key in use : 9e5e749c135740269b5e64cab32a6b1f
Key owner login           : user@domain.com
Client API version        : 20160916
Server address            : https://server.domain.com:5000
Server API version        : 20160916

[user@host ~]$ 
```

Looks good, we can start using the tool now.

## Creating your first system

A system can have many different attributes and some of them are required when creating a system. To have an idea of the attributes available, check the help menu for the add action:
```console
[user@host ~]$ tessia system add --help
Usage: tessia system add [OPTIONS]

  create a new system

Options:
  --name TEXT      system name  [required]
  --hostname TEXT  resolvable hostname or ip address  [required]
  --hyp TEXT       system's hypervisor
  --type TEXT      system type (see types)  [required]
  --model TEXT     system model (see model-list)
  --state TEXT     system state (see states)
  --project TEXT   project owning system
  --desc TEXT      free form field describing system
  -h, --help       Show this message and exit.
```

The text menu is mostly self-explanatory, so let's try to create a system based on that information. Assume we have a System z LPAR named 'lpar65' on a CPC called 'cpc50'.
Since the lpar control is done with actions on the CPC, we should start by verifying first if the CPC is already present in the tool. This is a chance to learn about list commands, so we use the system list command and specify the system type:
```console
[user@host ~]$ tessia system list --type=CPC

Name            : cpc50
Hostname        : hmc2.domain.com
Hypervisor name : 
Type            : CPC
Model           : ZEC12_H20
Current state   : AVAILABLE
Owner           : sysadmin@domain.com
Project         : Devops
Last modified   : 2017-02-08 10:28:44
Modified by     : sysadmin@domain.com
Description     : CPC for Performance tests


Name            : cpc20
Hostname        : hmc2.domain.com
Hypervisor name : 
Type            : CPC
Model           : ZEC12_H20
Current state   : AVAILABLE
Owner           : sysadmin@domain.com
Project         : Devops
Last modified   : 2017-02-08 10:28:44
Modified by     : sysadmin@domain.com
Description     : Production systems
```

Here we filtered the list by type with the use of the parameter `--type`. Other filters are possible, you can check the available ones by typing `tessia system list --help`.

Good, our CPC is already registered. Note that it does not have a hypervisor defined (because CPCs have no hypervisors), but most times a system will have one. In our example, cpc50
is the hypervisor for lpar65 which in turn could be the hypervisor of a KVM guest 'guest39', and so on.

It's time to add our lpar to the tool. Our command looks like:

```console
[user@host ~]$ tessia system add --name=lpar65 --hyp=cpc50 --type=LPAR --hostname=lpar65.mydomain.com --desc='System for database performance tests'
Item added successfully.

[user@host ~]$ tessia system list --name=lpar65

Name            : lpar65
Hostname        : lpar65.mydomain.com
Hypervisor name : cpc50
Type            : LPAR
Model           : ZEC12_H20
Current state   : AVAILABLE
Owner           : user@domain.com
Project         : Performance test
Last modified   : 2017-02-09 09:18:57
Modified by     : user@domain.com
Description     : System for database performance tests
```

That's it, our first system registered in the tool. Now we need to add the appropriate resources in order to make the system usable, like network interfaces and disks.

## Creating a network interface

Under the `tessia system` family of commands you will notice the subset of `iface-*` commands. We are going to use them to create a network interface for our system.

Let's start by learning what attributes are necessary, again with the aid of the help menu:

```console
[user@host ~]$ tessia system iface-add --help
Usage: tessia system iface-add [OPTIONS]

  create a new network interface

Options:
  --system TEXT       target system  [required]
  --name TEXT         interface name  [required]
  --type TEXT         interface type (see iface-types)  [required]
  --osname TEXT       interface name in operating system (i.e. en0)
  --mac TEXT          mac address  [required]
  --subnet TEXT       subnet of ip address to be assigned
  --ip TEXT           ip address to be assigned to interface
  --layer2 BOOLEAN    enable layer2 mode (OSA only)
  --ccwgroup TEXT     device channels (OSA only)
  --portno TEXT       port number (OSA only)
  --portname TEXT     port name (OSA only)
  --hostiface TEXT    host iface to bind (KVM only)
  --libvirt XML_FILE  libvirt definition file (KVM only)
  --desc TEXT         free form field describing interface
  -h, --help          Show this message and exit.
```

We need to create an OSA card, so the parameters described as *(OSA only)* are of interest. The help also suggests to check the sub-command `iface-types` in case the user does not
know the name of the interface type. In this case we already know from the help that it is `OSA` so it's not necessary to check it. Our command therefore is:

```console
[user@host ~]$ tessia system iface-add --system=lpar65 --name='default osa' --type=OSA --osname=enccw0.0.f500 --mac=aa:bb:cc:dd:ee:ff --layer2=true --ccwgroup=f500,f501,f502 --desc='default gateway interface'
Item added successfully.
[user@host ~]$ tessia system iface-list --system=lpar65

Interface name             : default osa
Operating system name      : enccw0.0.f500
System                     : lpar65
Interface type             : OSA
IP address                 : 
MAC address                : aa:bb:cc:dd:ee:ff
Attributes                 : {'layer2': True, 'ccwgroup': 'f500,f501,f502'}
Associated system profiles : 
Description                : default gateway interface
```

One field worth mentioning here is *Operating system name*. Under Linux the interfaces have names and this field specifies how the interface should be named in the operating
system. In our example we followed the recommended convention and named it after the channel number.

For the interface to be usable we also need an IP address. Let's learn how to do it in the next section.

## Associating an IP address

Here we get introduced to the `tessia net` family of commands. From the [resources model](resources_model.md) explanation we know that a subnet is required in order to create an IP address.
Usually the management of the network infrastructure is done by a lab administrator and most users will just pick up an IP assigned to them but for learning purposes we are going to create one.

We start by checking which subnets are available with the list command of the subset `subnet-*`:

```console
[user@host ~]$ tessia net subnet-list
Error: at least one of --zone or --name must be specified (hint: use zone-list to find available zones)
```

Oops, something went wrong. As there can be many different subnets in a given infrastructure the client asks us to be more specific so that we don't get lost in hundreds of results. Ok, we have no idea
what is the name of the subnet we want and we don't know which network zones are available either but we can find it out with the `zone-list` sub-command:

```console
[user@host ~]$ tessia net zone-list

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

Let's assume we already know that our lpar65 is located in the Lab1, so the zone `Lab1` is what we want. Back to the subnet listing:

```console
[user@host ~]$ tessia net subnet-list --zone='Lab1'

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

Great, we found a subnet available for systems running on cpc50 which is the hypervisor of our lpar65. Now let's see what IP addresses are registered under this subnet:

```console
[user@host ~]$ tessia net ip-list --subnet='CPC50 shared'

IP address        : 192.168.0.15
Part of subnet    : CPC50 shared
Owner             : jdoe@domain.com
Project           : CRM team
Last modified     : 2017-02-09 11:47:38
Modified by       : user@domain.com
Description       : For production usage
Associated system : zVM25
```

Ok, there is one IP registered and already assigned to a system named `zVM25`, so we can't use it. Let's then create a new address for us:

```console
[user@host ~]$ tessia net ip-add --subnet='CPC50 shared' --ip=192.168.0.16 --project='Performance test' --desc='For performance measurements in system lpar65'
Item added successfully.
[user@host ~]$ tessia net ip-list --subnet='CPC50 shared' --ip=192.168.0.16

IP address        : 192.168.0.16
Part of subnet    : CPC50 shared
Owner             : user@domain.com
Project           : Performance test
Last modified     : 2017-02-09 12:07:22
Modified by       : user@domain.com
Description       : For performance measurements in system lpar65
Associated system : 
```

Very good, we have our own IP now. As you can see from the output above the IP is not yet associated with any system so we have to assign it to our lpar65. IP addresses
are not associated to a system directly but to one of its network interfaces. To create such association we use the `iface-edit` command:

```console
[user@host ~]$ tessia system iface-edit --system=lpar65 --name='default osa' --ip='192.168.0.16'
Error: --subnet and --ip must be specified together
```

Oops, another mistake. Of course a private IP like this can belong to many different network zones so we need to be specific and tell the tool which subnet we are referring to. One more try:

```console
[user@host ~]$ tessia system iface-edit --system=lpar65 --name='default osa' --subnet='CPC50 shared' --ip='192.168.0.16'
Item successfully updated.
[user@host ~]$ tessia system iface-list --system=lpar65

Interface name             : default osa
Operating system name      : enccw0.0.f500
System                     : lpar65
Interface type             : OSA
IP address                 : CPC50 shared/192.168.0.16
MAC address                : aa:bb:cc:dd:ee:ff
Attributes                 : {'ccwgroup': 'f500,f501,f502', 'layer2': True}
Associated system profiles : 
Description                : default gateway interface
```

Perfect, we now have a usable network interface for our system. We are almost done, we still need at least one disk.

## Creating a volume

Similiar to IP addresses, volumes are usually managed by a lab administrator and most users are only told which ones to use. But again for education purposes we are going to create one.

Assume we know that our disk is a DASD with id 3950 from the storage server DS8K16. Let's check if such storage server is available on the tool, now by using the `tessia storage` family of commands:

```console
[user@host ~]$ tessia storage server-list

Name           : DS7K16
Hostname       : 
Model          : DS8800
Server type    : DASD-FCP
Firmware level : 
Owner          : sysadmin@domain.com
Project        : Devops
Last modified  : 2017-02-08 10:28:44
Modified by    : jdoe@domain.com
Description    : Storage for CPCs 20 and 21


Name           : DS8K16
Hostname       : 
Model          : DS8800
Server type    : DASD-FCP
Firmware level : 
Owner          : sysdmin@domain.com
Project        : Devops
Last modified  : 2017-02-08 10:28:45
Modified by    : system
Description    : Storage for CPC 50
```

So the server is there and its name is `DS8K16`. Perhaps our disk is already registered, let's check:

```console
[user@host ~]$ tessia storage vol-list --server=DS8K16 --id=3950
No results were found.
[user@host ~]$
```

Not yet, so by using the help menu again we can learn which parameters are necessary to register a volume:

```console
[user@host ~]$ tessia storage vol-add --help
Usage: tessia storage vol-add [OPTIONS]

  create a new storage volume

Options:
  --server TEXT   target storage server  [required]
  --id TEXT       volume id  [required]
  --size TEXT     volume size (i.e. 10gb)  [required]
  --type TEXT     volume type (see vol-types)  [required]
  --pool TEXT     assign volume to this storage pool
  --specs TEXT    volume specification (json)
  --project TEXT  project owning volume
  --desc TEXT     free form field describing volume
  -h, --help      Show this message and exit.
```

Again we must know the name of the volume type for dasd disks and you can learn this with the `vol-types` command. We already know in advance that it is `DASD`, so our command looks like:

```console
[user@host ~]$ tessia storage vol-add --server=DS8K16 --type=DASD --id=3950 --size=7gb
Item added successfully.
[user@host ~]$ tessia storage vol-list --server=DS8K16 --id=3950
Volume id                  : 3950
Storage server             : DS8K16
Volume size                : 7.0GB
Volume specifications      : {}
Volume type                : DASD
Attached to system         : 
System related attributes  : {}
Associated system profiles : 
Attached to storage pool   : 
Owner                      : user@domain.com
Project                    : Performance test
Last modified              : 2017-02-09 12:49:43
Modified by                : user@domain.com
Description                : 
```

An empty disk is not very useful so we need to create partitions. Let's have a look at the `part-*` sub-commands, particularly the one to initialize a partition table:

```console
[user@host ~]$ tessia storage part-init --server=DS8K16 --id=3950 --label=dasd
Partition table successfully initialized.
```

Note that we used `--label=dasd` as we are dealing with a DASD disk but it could be a different type for other volume types. Remember to check the help menu with `--help` to learn the possible
options.

For the installation we want to perform one root partition and one swap should be enough:

```console
[user@host ~]$ tessia storage part-add --server=DS8K16 --id=3950 --fs=ext4 --size=6gb --mp=/
Partition successfully added.
[user@host ~]$ tessia storage part-add --server=DS8K16 --id=3950 --fs=swap --size=1gb
Partition successfully added.
[user@host ~]$ tessia storage part-list --server=DS8K16 --id=3950

Partition table type: dasd

 number |  size |   type  | filesystem | mount point | mount options
--------+-------+---------+------------+-------------+---------------
 1      | 6.0GB | primary | ext4       | /           |               
 2      | 1.0GB | primary | swap       |             |               
```

Looks good, so we already have a disk and a network interface. Time to tell the tool how we want the system to be activated by creating an activation profile.

## Defining an activation profile

An activation profile is a definition of which resources and parameters should be used when booting up a system. In addition to the network interfaces and disks we can also define the
amount of memory and CPUs to use, boot parameters (depending on the hypervisor type), and so on.

In order to have a usable system for installation we are going to create a profile and attach the previously created network interface and volume to it. That leads us to the `prof-*` family of sub-commands.
We start by creating the profile:

```console
[user@host ~]$ tessia system prof-add --system=lpar65 --name='profile1' --cpu=2 --memory=2048mb --login='root:mypasswd'
Item added successfully.
[user@host ~]$ tessia system prof-list --system=lpar65 

Profile name                : profile1
System                      : lpar65
Required hypervisor profile : 
Operating system            : 
Default                     : True
CPU(s)                      : 2
Memory                      : 2.0GB
Parameters                  : 
Credentials                 : {'user': 'root', 'passwd': 'mypasswd'}
Storage volumes             : 
Network interfaces          : 
```

Most parameters are self-explanatory and the *Credentials* field is used when a new operating system is installed. We will see this working soon in the next step, but before we move to
the installation we still need to attach our network interface:

```console
[user@host ~]$ tessia system iface-attach --system=lpar65 --profile='profile1' --iface='default osa'
Network interface attached successfully.
[user@host ~]$ tessia system prof-list --system=lpar65

Profile name                : profile1
System                      : lpar65
Required hypervisor profile : 
Operating system            : 
Default                     : True
CPU(s)                      : 2
Memory                      : 2.0GB
Parameters                  : 
Credentials                 : {'passwd': 'mypasswd', 'user': 'root'}
Storage volumes             : 
Network interfaces          : [default osa/192.168.0.16]
```

We can see our interface and the IP we assigned to it in the *Network interfaces*  list. We are almost done, let's not forget to attach our volume as well:

```console
[user@host ~]$ tessia system vol-attach --system=lpar65 --profile=profile1 --server=DS8K16 --vol=3950
Volume attached successfully.
[user@host ~]$ tessia system prof-list --system=lpar65 

Profile name                : profile1
System                      : lpar65
Required hypervisor profile : 
Operating system            : 
Default                     : True
CPU(s)                      : 2
Memory                      : 1.0GB
Parameters                  : 
Credentials                 : {'user': 'root', 'passwd': 'mypasswd'}
Storage volumes             : [DS8K16/3950]
Network interfaces          : [default osa/192.168.0.16]
```

We can see the newly attached disk in the *Storage volumes* field. We are ready to do our first installation!

## Installing an operating system with an autotemplate

Tessia offers a library of templates powered by the [jinja2](http://jinja.pocoo.org) engine for operating system installations (i.e. kickstart, autoinst, preseed). During the installation
process these templates are fulfilled with the system information from the database and passed to the installer (i.e. Anaconda, AutoYast). Therefore in order to install our system we need to choose one template and for that we can use the `tessia autotemplate` family of commands:

```console
[user@host ~]$  tessia autotemplate list

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

We have to choose from one of the operating systems versions shown above. If you are curious about the content of a template you can print it with `tessia autotemplate print` and
if you are even more interested you can use it as a reference to create your own template and add it to the library with `tessia autotemplate add`.

Now that we know the available versions, let's perform a RHEL installation:

```console
[user@host ~]$ tessia system autoinstall --template=RHEL7.2 --system=lpar65 --profile=profile1

Request #7 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #4
Waiting for installation output (Ctrl+C to stop waiting)
2017-02-10 11:25:42,774|INFO|sm_base.py(334)|new state: init
2017-02-10 11:25:42,776|INFO|sm_base.py(337)|new state: collect_info
2017-02-10 11:25:42,834|INFO|sm_base.py(340)|new state: create_autofile
2017-02-10 11:25:42,834|INFO|sm_base.py(279)|generating autofile
2017-02-10 11:25:42,853|INFO|sm_base.py(343)|new state: target_boot
2017-02-10 11:28:20,293|INFO|sm_base.py(346)|new state: wait_install
2017-02-10 11:28:47,134|WARNING|sm_base.py(218)|connection not available yet, retrying in 5 seconds.
2017-02-10 11:28:52,457|INFO|sm_anaconda.py(146)|10:29:13,210 INFO anaconda: /usr/sbin/anaconda 21.48.22.56-1
10:29:13,359 INFO anaconda: created new libuser.conf at /tmp/libuser.8xVrzl with instPath="/mnt/sysimage"
10:29:13,360 INFO anaconda: 2097152 kB (2048 MB) are available
10:29:13,372 INFO anaconda: check_memory(): total:2097152, needed:1070, graphical:1160

(lots of output ...)

10:29:14,513 INFO anaconda.stdout: The VNC server is now running.
10:29:14,513 WARN anaconda.stdout: 

(lots of output ...)

2017-02-10 11:30:52,640|INFO|sm_base.py(349)|new state: target_reboot
2017-02-10 11:30:52,640|INFO|plat_lpar.py(102)|Rebooting the system now!
2017-02-10 11:30:52,991|INFO|sm_base.py(352)|new state: check_installation
2017-02-10 11:31:20,734|WARNING|sm_base.py(218)|connection not available yet, retrying in 5 seconds.
2017-02-10 11:31:25,982|INFO|sm_base.py(355)|new state: post_install
2017-02-10 11:31:25,992|INFO|sm_base.py(358)|Installation finished successfully
[user@host ~]$
```

We ommitted certain parts of the anaconda installer output to make it short. Let's take a look at the resulting installation. Remember, we use the credentials from
the activation profile to connect to the installed system:

```console
[user@host ~]$ ssh root@lpar65.mydomain.com
Failed to add the host to the list of known hosts (/home/user/.ssh/known_hosts).
root@lpar65.mydomain.com's password: 
Last login: Fri Feb 10 05:42:58 2017 from laptop.mydomain.com
[root@lpar65 ~]# cat /etc/os-release
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
[root@lpar65 ~]# parted /dev/dasda print
Model: IBM S390 DASD drive (dasd)
Disk /dev/dasda: 7385MB
Sector size (logical/physical): 512B/4096B
Partition Table: dasd
Disk Flags: 

Number  Start   End     Size    File system     Flags
 1      98.3kB  6292MB  6291MB  ext4
 2      6292MB  7340MB  1049MB  linux-swap(v1)
```

As expected, disk partition corresponds to what we have configured and the operating system version too.

Before you start having fun with your installations, one more thing: you probably noticed that when we executed the `autoinstall` commmand the client reported that a request was submitted and a job started. Job scheduling is an important concept in tessia, so we talk about it in the next section, just don't leave yet :)

## Checking jobs on the scheduler

In tessia every long running action is treated as a job and as such must be scheduled for proper allocation and blocking of the resources involved. That means when we issue the command
to start a system installation what the client actually does is to submit a request to the server to schedule a job. Usually the system in question belongs to the user and will most
likely be free for use which means immediate execution, but that might not be always the case. So if you try to perform a system installation and the job does not get executed immediately
then possibly the system is currenly blocked by a running action/job (i.e. task execution or another installation).

So how can one tell what is going on? That is the purpose of the `tessia job` family of commands. There you find the commands for dealing with job scheduling, such as verifying the state of
job and requests.

An example of how to verify which jobs are currently running:

```console
[user@host ~]$ tessia job list

 job_id |   job_type  |     submit_date     |      start_date     |       end_date      |    requester    |   state   |        description           
--------+-------------+---------------------+---------------------+---------------------+---------------------+-----------+------------------------------
 1      | autoinstall | 2017-02-10 10:20:39 | 2017-02-10 10:21:33 | 2017-02-10 10:21:43 | user@domain.com | CANCELED  | Auto installation of OS rhel7.2 
 2      | autoinstall | 2017-02-10 10:22:07 | 2017-02-10 10:22:07 | 2017-02-10 10:23:26 | user@domain.com | CANCELED  | Auto installation of OS rhel7.2 
 3      | autoinstall | 2017-02-10 10:24:35 | 2017-02-10 10:24:35 | 2017-02-10 10:25:04 | user@domain.com | CANCELED  | Auto installation of OS rhel7.2 
 4      | autoinstall | 2017-02-10 10:25:41 | 2017-02-10 10:25:41 | 2017-02-10 10:27:04 | user@domain.com | CANCELED  | Auto installation of OS rhel7.2 
 5      | autoinstall | 2017-02-10 10:27:21 | 2017-02-10 10:27:21 | 2017-02-10 10:31:25 | user@domain.com | COMPLETED | Auto installation of OS rhel7.2 
```

Here we can see many installation jobs canceled and the last one successfully completed.

The scheduler is a daemon process which constantly consumes the queue of requests to update the job queue accordingly. A request is a short lived entity that exists only during the
interval between each time the scheduler processes the request queue.

It is possible to take a look at the request queue if you suspect something was not yet processed:

```console
[user@host ~]$ tessia job req-list

 request_id | action_type |   job_type  |     submit_date     |    requester    |   state   
------------+-------------+-------------+---------------------+---------------------+--------
 1          | SUBMIT      | autoinstall | 2017-02-10 10:20:39 | user@domain.com | COMPLETED 
 2          | CANCEL      |             | 2017-02-10 10:21:42 | user@domain.com | COMPLETED 
 3          | SUBMIT      | autoinstall | 2017-02-10 10:22:07 | user@domain.com | COMPLETED 
 4          | CANCEL      |             | 2017-02-10 10:23:24 | user@domain.com | COMPLETED 
 5          | SUBMIT      | autoinstall | 2017-02-10 10:24:35 | user@domain.com | COMPLETED 
 6          | CANCEL      |             | 2017-02-10 10:25:03 | user@domain.com | COMPLETED 
 7          | SUBMIT      | autoinstall | 2017-02-10 10:25:41 | user@domain.com | COMPLETED 
 8          | CANCEL      |             | 2017-02-10 10:27:03 | user@domain.com | COMPLETED 
 9          | SUBMIT      | autoinstall | 2017-02-10 10:27:21 | user@domain.com | COMPLETED 
```

The queue shows that all existing requests were already processed (state COMPLETED) and a series of requests to submit new jobs (action_type SUBMIT) and cancellations
(action_type CANCEL) occurred. Let's see which job the request 2 wanted to cancel:

```console
[user@host ~]$ tessia job req-list --id=2

Request ID           : 2
Action type          : CANCEL
Machine type         : 
Date submitted       : 2017-02-10 10:21:42
Request owner        : user@domain.com
Request state        : COMPLETED
Target job ID        : 1
Job time slot        : DEFAULT
Allowed job duration : 0
Job priority         : 0
Start date           : 
Request result       : OK
Machine parameters   : 
```

The field *Target job ID* says 1, so this request was to stop job 1 which indeed showed up as canceled in the job list.

By now we have covered the essential parts of the client to get you started. For details on specific commands you can always check the help menu with `--help` and the
[users section](../index.md#users) for detailed information on specific topics.
