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

At the end of this guide you will have learned:

- how to create the initial resources in the tool so that the first system installation can happen;
- how to use the command line client.

Before systems can be installed, the tool needs information about the datacenter resources available. That means you need to specify:

- a storage server;
- volumes (disks) on the storage server;
- a network zone;
- a network subnet in the network zone;
- an IP address of the network subnet;
- a URL to a distribution package repository.

If you are not yet familiar with the definitions of different resource names used, we suggest that you read the [Resources model](resources_model.md) page first.

Note that the tool does not have the capability (yet) to actually create these resources in the infrastructure.
It is assumed that they are already in place. For example, the tool will **NOT**:

- connect to the storage server and create the volumes;
- connect to a switch/firewall appliance to configure network zones/subnets/ip addresses;
- create a new LPAR on the HMC (it will, however, change the LPAR's activation profile as necessary for the desired cpus, memory, etc.).

# Initial client configuration

Upon first usage the client needs to learn two things from you:

- where the API server is located
- what are your credentials (login/password) in order to create an authentication token to validate you with the server

If you have those already configured, just skip the next two sections.

## API server location

If the server is running under HTTPS (most likely), you have to place a copy of the SSL certificate beforehand either in `~/.tessia-cli/ca.crt` (local user) or
`/etc/tessia-cli/ca.crt` (global). If you don't do so, you will see an error like this:

```
$ tess conf set-server https://server.domain.com:5000
Error: The validation of the server's SSL certificate failed. In order to assure the connection is safe, place a copy of the trusted CA's certificate file in /home/user/.tessia-cli/ca.crt and try again.
```

The CA's certificate file is usually provided by the server administrator through a trusted link or some other trusted method. You should verify with your sysadmin how to download it.

Once the certificate file is available, we can enter the API server's hostname successfully:

```
$ tess conf set-server https://server.domain.com:5000
Server successfully configured.
```

## User credentials

The client must generate an authentication token for communication with the server. Here's how to do it:

```
$ tess conf key-gen
Login: user@domain.com
Password: 
Key successfully created and added to client configuration.
```

Let's confirm that the operation worked by checking the client configuration:
```
$ tess conf show

Authentication key in use : 9e5e749c135740269b5e64cab32a6b1f
Key owner login           : user@domain.com
Client API version        : 20160916
Server address            : https://server.domain.com:5000
Server API version        : 20160916
```

Looks good, we can start using the tool now.

# Define user permissions

The permissions system is composed of projects (groups), users and roles.
One can configure them according to the needs of their organization by using the `perm` sub-family of commands.

A common scenario is where a group of lab administrators handles the creation of datacenter resources like storage servers, volumes and ip addresses,
while the other users control their systems in their own groups.

We are going to use this described setup as an example. Assuming you are currently using the admin token (as explained in the [installation](server_install.md) instructions),
 create the first projects and users:

```
# create the lab administrator user and grant the admin_lab role
$ tess perm project-add --name='devops' --desc='Devops team (lab administrators)'
Item added successfully.
$ tess perm user-add --login=jstone@example.com --name='Jack Stone' --title='Lab administrator'
User added successfully.
$ tess perm role-grant --login=jstone@example.com --name='ADMIN_LAB' --project='devops'
User role added successfully.

# create a developer user with access to control systems
$ tess perm project-add --name='developers' --desc='Developers team'
Item added successfully.
$ tess perm user-add --login=msmith@example.com --name='Mark Smith' --title='Developer'
User added successfully.
$ tess perm role-grant --login=msmith@example.com --name='USER' --project='developers'
User role added successfully.
```

# Create the resources

For the next sections the resources can be created either by the admin user or by the user with the `ADMIN_LAB` role. **For education purposes on the next sections we assume you
 are logged in as the lab admin user we just created**.

## Storage server

A storage server is needed so that we can create volumes. For storage related commands (servers, volumes), we use the `storage` sub-family of commands.
A server can be created with:

```
$ tess storage server-add --name=ds8k16 --model=DS8000 --type=DASD-FCP --project='devops' --desc='Storage server 1'

$ tess storage server-list --long --name=ds8k16

Name           : ds8k16
Hostname       : 
Model          : DS8000
Server type    : DASD-FCP
Firmware level : 
Owner          : jstone@example.com
Project        : devops
Last modified  : 2017-12-07 09:14:33
Modified by    : jstone@example.com
Description    : Storage server 1

```

## Storage volume (disk)

Again by using the `storage` sub-family we can register the first volumes in the tool:

```
$ tess storage vol-add --server=ds8k16 --type=DASD --id=7e2d --size=7gb --desc='to be used as the live-image disk on cpc3'
Item added successfully.
$ tess storage vol-add --server=ds8k16 --type=DASD --id=7e2e --size=7gb --desc='for use by lpar cpc3lp25'
Item added successfully.
$ tess storage vol-add --server=ds8k16 --type=DASD --id=7e2f --size=7gb --desc='for use by lpar cpc3lp25'
Item added successfully.

$ tess storage vol-list --long --server=ds8k16

Volume id                  : 7e2f
Storage server             : ds8k16
Volume size                : 6.52 GiB
Volume specifications      : {}
Volume type                : DASD
Attached to system         : 
System related attributes  : {}
Associated system profiles : 
Attached to storage pool   : 
Owner                      : jstone@example.com
Project                    : devops
Last modified              : 2017-12-07 09:59:50
Modified by                : jstone@example.com
Description                : for use by lpar cpc3lp25


Volume id                  : 7e2e
Storage server             : ds8k16
Volume size                : 6.52 GiB
Volume specifications      : {}
Volume type                : DASD
Attached to system         : 
System related attributes  : {}
Associated system profiles : 
Attached to storage pool   : 
Owner                      : jstone@example.com
Project                    : devops
Last modified              : 2017-12-07 09:59:20
Modified by                : jstone@example.com
Description                : for use by lpar cpc3lp25


Volume id                  : 7e2d
Storage server             : ds8k16
Volume size                : 6.52 GiB
Volume specifications      : {}
Volume type                : DASD
Attached to system         : 
System related attributes  : {}
Associated system profiles : 
Attached to storage pool   : 
Owner                      : jstone@example.com
Project                    : devops
Last modified              : 2017-12-07 09:59:02
Modified by                : jstone@example.com
Description                : to be used as live-image disk on cpc3
```

**Note:** pay special attention when specifying the size of the disk as it's not possible to validate the value provided against the actual disk.
An incorrect value (i.e. size entered is bigger than the actual disk) will cause installations to fail.

The volumes will be assigned to the target systems via system activation profiles later.

## Network zone

For network related commands we make use of the `net` sub-family of commands. Let's create a zone for a given network segment:

```
$ tess net zone-add --name='lab1-zone-c' --desc='Lab 1 Zone C'
Item added successfully.
$ tess net zone-list --long

Zone name     : lab1-zone-c
Owner         : jstone@example.com
Project       : devops
Last modified : 2017-12-07 10:15:12
Modified by   : jstone@example.com
Description   : Lab 1 Zone C
```

The network zones exist to organize the subnets ranges so that they can coexist without conflict even if they overlap. A common scenario where this happens is when
different systems use a private subnet range (i.e. 192.168.0.0/24). As these subnets will be in different zones the tool can manage them separately.

## Subnet

A subnet defines a range of IP addresses with information about routing and name servers:

```
$ tess net subnet-add --zone=lab1-zone-c --name='lab1-zone-c-s1' --address=192.168.0.0/24 --gw=192.168.0.1 --dns1=8.8.8.8 --desc='shared subnet on zone-c'
Item added successfully.

$ tess net subnet-list --long --zone=lab1-zone-c

Subnet name     : lab1-zone-c-s1
Network zone    : lab1-zone-c
Network address : 192.168.0.0/24
Gateway         : 192.168.0.1
DNS server 1    : 8.8.8.8
DNS server 2    : 
VLAN            : 
Owner           : jstone@example.com
Project         : devops
Last modified   : 2017-12-07 10:33:46
Modified by     : jstone@example.com
Description     : shared subnet on zone-c
```

## IP address

Create an IP address which will be associated to a system later:

```
$ tess net ip-add --subnet='lab1-zone-c-s1' --ip=192.168.0.9 --desc='Gateway IP for lpar cpc3lp25'
Item added successfully.

$ tess net ip-list --long --subnet='lab1-zone-c-s1'

IP address        : 192.168.0.9
Part of subnet    : lab1-zone-c-s1
Owner             : jstone@example.com
Project           : devops
Last modified     : 2017-12-07 10:50:30
Modified by       : jstone@example.com
Description       : Gateway IP for lpar cpc3lp25
Associated system : 
```

## Hypervisor (CPC)

Each system must have a hypervisor so that it can be managed/installed (except for CPCs, which can't be installed).
As we want to install LPARs the hypervisor is a CPC which we create below:

```
$ tess system add --name=cpc3 --type=cpc --hostname=hmc2.domain.com --model=zec12_h43 --desc='2 books'
Item added successfully.

$ tess system list --long --name=cpc3

Name            : cpc3
Hostname        : hmc2.domain.com
Hypervisor name : 
Type            : CPC
Model           : ZEC12_H43
Current state   : AVAILABLE
Owner           : jstone@example.com
Project         : devops
Last modified   : 2017-12-07 10:58:01
Modified by     : jstone@example.com
Description     : 2 books
```

**Note:** the use of the `--hostname` parameter in the case of CPC systems has a special meaning as it should point to the URL of the HMC that manages them.

We still need to provide the user credentials for logging on the HMC, this is done by defining a profile:

```
$ tess system prof-add --system=cpc3 --name='default' --cpu=43 --memory=800gib --login='hmc_user:hmc_password'
Item added successfully.

$ tess system prof-list --long --system=cpc3

Profile name                : default
System                      : cpc3
Required hypervisor profile : 
Operating system            : 
Default                     : True
CPU(s)                      : 43
Memory                      : 800.0 GiB
Parameters                  : 
Credentials                 : {'admin-password': '****', 'admin-user': '****'}
Storage volumes             : 
Network interfaces          : 
Gateway interface           : 
```

The concept of profiles is explained in more detail later during the creation of the target system.

**Note**: as of today the cpu and memory parameters for CPC systems are only for information purposes and not used.

The user `hmc_user` entered above must be allowed in the HMC configuration to use the Web Services API and must have access to the management tasks
(activate, deactivate, load, and customize/delete activation profiles) for the LPARs to be installed when in classic mode or the equivalent actions
for the partitions to be installed when in DPM mode.

As mentioned in the [installation](server_install.md) instructions, tessia makes use of an auxiliar live image in order to network boot LPARs at installation time.
The strategy adopted to load the live image depends on the machine operation mode (classic or DPM mode). The next sections explain how to set it up for each operation mode.

### CPC in Classic mode

For machines in classic mode the live image must be deployed in a pre-allocated disk. If you haven't deployed it yet, refer to
[Deployment of the auxiliar live-image](server_install.md#deployment-of-the-auxiliar-live-image) for instructions on how to do it.

The pre-allocated live-image disk must be assigned to the CPC so that the tool knows which disk to use when LPARs are to be installed.
This is done by attaching the disk to the CPC's system profile:

```
$ tess system vol-attach --system=cpc3 --profile='default' --server=ds8k16 --vol=7e2d
Volume attached successfully.

$ tess system prof-list --long --system=cpc3

Profile name                : default
System                      : cpc3
Required hypervisor profile : 
Operating system            : 
Default                     : True
CPU(s)                      : 43
Memory                      : 800.0 GiB
Parameters                  : 
Credentials                 : {'admin-password': '****', 'admin-user': '****'}
Storage volumes             : [ds8k16/7e2d]
Network interfaces          : 
Gateway interface           : 
```

## CPC in DPM mode

For machines in DPM mode the live image is loaded directly from an FTP server on the network. If you haven't built the live image yet, refer to
[Deployment of the auxiliar live-image](server_install.md#deployment-of-the-auxiliar-live-image) for instructions on how to do it.

Once the image is available on an FTP server, we enter the URL of the insfile in the CPC system profile so that the tool knows from where to boot
the image when performing a partition installation. This is done by entering the URL in the CPC's system profile parameters:

```
$ tess system prof-edit --system=cpc3 --name='default' --liveimg=ftp://my-ftp-server.example.com/live-image/live-img.ins
Item successfully updated.

$ tess system prof-list --long --system=cpc3

Profile name                : default
System                      : cpc3
Required hypervisor profile : 
Operating system            : 
Default                     : True
CPU(s)                      : 43
Memory                      : 800.0 GiB
Parameters                  : {'liveimg-insfile-url': 'ftp://my-ftp-server.example.com/live-image/live-img.ins'}
Credentials                 : {'admin-password': '****', 'admin-user': '****'}
Storage volumes             : 
Network interfaces          : 
Gateway interface           : 
```

## Target system (LPAR)

It's time to finally add the target LPAR to the tool. During creation we point to the previously created CPC `cpc3` as the LPAR's hypervisor:

```
$ tess system add --name=cpc3lp25 --hyp=cpc3 --type=LPAR --hostname=cpc3lp25.domain.com --desc='System for database performance tests'
Item added successfully.

$ tess system list --long --name=cpc3lp25

Name            : cpc3lp25
Hostname        : cpc3lp25.domain.com
Hypervisor name : cpc3
Type            : LPAR
Model           : ZEC12_H43
Current state   : AVAILABLE
Owner           : jstone@example.com
Project         : devops
Last modified   : 2017-12-07 14:16:22
Modified by     : jstone@example.com
Description     : System for database performance tests
```

The parameter `--hostname` must be a DNS resolvable name or an IP address reachable by the tessia server.

In order to be usable a system needs disks and network interfaces. This is done through a system activation profile on the next section.

## System activation profile

The profile object is the "glue" that puts together a system and its assigned resources. It is a definition of which resources and parameters
 are to be used when booting up a system. In addition to the network interfaces and disks, one can also define the amount of memory and CPUs to use,
 boot parameters (depending on the system type), and so on.

**Note:** although the names are similar, tessia's system activation profile is not the same as the LPAR's activation profile in the HMC.

We have already created a profile for the CPC earlier, the command is similar:

```
$ tess system prof-add --system=cpc3lp25 --name='default' --cpu=2 --memory=4gib --login='root:mypasswd'
Item added successfully.

# attach the volumes previously created
$ tess system vol-attach --system=cpc3lp25 --profile=default --server=ds8k16 --vol=7e2e
Volume attached successfully.
$ tess system vol-attach --system=cpc3lp25 --profile=default --server=ds8k16 --vol=7e2f
Volume attached successfully.


tess system prof-list --long --system=cpc3lp25

Profile name                : default
System                      : cpc3lp25
Required hypervisor profile : 
Operating system            : 
Default                     : True
CPU(s)                      : 2
Memory                      : 4.0 GiB
Parameters                  : 
Credentials                 : {'admin-user': '****', 'admin-password': '****'}
Storage volumes             : [ds8k16/7e2e], [ds8k16/7e2f]
Network interfaces          : 
Gateway interface           : 
```

The `Credentials` field is used as the root password when a new operating system is installed and when connecting to a running system.

We can see the newly attached disks at the `Storage volumes` field. We still need to define a partition table for them before they are installable.

# Define disk partitioning

Initialize the partition tables and define a simple setup with one root partition and one swap:

```
# root disk
$ tess storage part-init --server=ds8k16 --id=7e2e --label=dasd
Partition table successfully initialized.
$ tess storage part-add --server=ds8k16 --id=7e2e --fs=ext4 --size=7gb --mp=/
Partition successfully added.
$ tess storage part-list --server=ds8k16 --id=7e2e

Partition table type: dasd

 number |   size  |   type  | filesystem | mount point | mount options 
--------+---------+---------+------------+-------------+---------------
 1      | 6.52 GiB | primary | ext4       | /           |               


# swap disk
$ tess storage part-init --server=ds8k16 --id=7e2f --label=dasd
Partition table successfully initialized.
$ tess storage part-add --server=ds8k16 --id=7e2f --fs=swap --size=7gb
Partition successfully added.
$ tess storage part-list --server=ds8k16 --id=7e2f

Partition table type: dasd

 number |   size  |   type  | filesystem | mount point | mount options 
--------+---------+---------+------------+-------------+---------------
 1      | 6.52 GiB | primary | swap       |             |               
```

Configuration of disks is done and they are now ready for use.

## Network interface

Create a system network interface and associate the IP address previously created:

```
$ tess system iface-add --system=cpc3lp25 --name='default osa' --type=OSA --devname=enccw0.0.f500 --mac=02:20:10:10:76:00 --layer2=true --ccwgroup=f500,0.0.f501,0.0.f502 --desc='gateway interface' --subnet='lab1-zone-c-s1' --ip=192.168.0.9
Item added successfully.

# assign the network interface to the system profile
$ tess system iface-attach --system=cpc3lp25 --profile=default --iface='default osa'
Network interface attached successfully.

$ tess system iface-list --long --system=cpc3lp25

Interface name             : default osa
Operating system name      : enccw0.0.f500
System                     : cpc3lp25
Interface type             : OSA
IP address                 : lab1-zone-c-s1/192.168.0.9
MAC address                : 02:20:10:10:76:00
Attributes                 : {'layer2': True, 'ccwgroup': '0.0.f500,0.0.f501,0.0.f502'}
Associated system profiles : [default]
Description                : gateway interface
```

**Note:** The field `Operating system name` specifies under Linux how the interface should be named on the operating system.
In the example above we followed the recommended convention and named it after the channel number.

The system configuration is done and it is now ready for installation.

## Register a package repository

At least one package repository must be available for the installation to happen. The example below creates a repository entry pointing to the official Ubuntu URL:

```
$ tess repo add --name=ubuntu-xenial --url=http://ports.ubuntu.com/ubuntu-ports --kernel='/dists/xenial/main/installer-s390x/current/images/generic/kernel.ubuntu' --initrd='/dists/xenial/main/installer-s390x/current/images/generic/initrd.ubuntu' --os=ubuntu16.04.1
Item added successfully.

$ tess repo list --long --name=ubuntu-xenial

Repository name : ubuntu-xenial
Installable OS  : ubuntu16.04.1
Network URL     : http://ports.ubuntu.com/ubuntu-ports
Kernel path     : /dists/xenial/main/installer-s390x/current/images/generic/kernel.ubuntu
Initrd path     : /dists/xenial/main/installer-s390x/current/images/generic/initrd.ubuntu
Owner           : jstone@example.com
Project         : devops
Last modified   : 2017-12-08 10:11:01
Modified by     : jstone@example.com
Description     : 
```

# Install the system

We are going to install the LPAR via the `autoinstall` method, which works as follows:

- the user starts the installation process while specifying a [jinja2](http://jinja.pocoo.org) template from the library and a Linux distro package repository;
- the tool fills the template's variables with the suitable information from the database resulting in a valid distro installer autofile (i.e. kickstart);
- the distro installer is downloaded from the specified package repository and executed with the created autofile on the target system;
- the distro installer does its work and performs the installation as usual;
- once the installation has finished the tool reboots the system and validate that the installed system conforms with the expected values from the database 
(network interfaces, IP addresses, disks and partitions sizes, etc.)

tessia comes with a set of pre-defined templates for each supported Linux distro and users can also create their own templates (see `tess autotemplate --help`).

In this example we use the pre-defined auto template for Ubuntu 16.04 to perform the installation:

```
$ tess system autoinstall --os=ubuntu16.04.1 --system=cpc3lp25

Request #7 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #4
Waiting for installation output (Ctrl+C to stop waiting)
2017-12-08 10:56:56 | INFO | new state: init
2017-12-08 10:56:56 | INFO | new state: collect_info
2017-12-08 10:56:56 | INFO | new state: create_autofile
2017-12-08 10:56:56 | INFO | generating autofile
2017-12-08 10:56:56 | INFO | new state: target_boot

(lots of output from installer ...)

2017-12-08 11:02:06 | INFO | new state: target_reboot
2017-12-08 11:02:06 | INFO | Rebooting the system now!
2017-12-08 11:02:07 | WARNING | Could not determine charmap
2017-12-08 11:02:07 | WARNING | Data in this ssh channel is encoded and decoded in UTF-8, but the shell locale seems to be using a different encoding.
2017-12-08 11:02:08 | INFO | new state: check_installation
2017-12-08 11:02:08 | INFO | Waiting for connection to be available (600 secs)
2017-12-08 11:02:40 | INFO | Verifying if installed system match expected parameters
2017-12-08 11:02:48 | WARNING | Max MiB size expected for disk /dev/disk/by-path/ccw-0.0.7e2e was 6875, but actual is 7043. You might want to adjust the volume size in the db entry.
2017-12-08 11:02:48 | WARNING | Max MiB size expected for partnum 1 disk /dev/disk/by-path/ccw-0.0.7e2e was 6775, but actual is 7043. Certain Linux installers maximize disk usage automatically therefore this difference is ignored.
2017-12-08 11:02:48 | WARNING | Max MiB size expected for disk /dev/disk/by-path/ccw-0.0.7e2f was 6875, but actual is 7043. You might want to adjust the volume size in the db entry.
2017-12-08 11:02:48 | INFO | new state: post_install
2017-12-08 11:02:48 | INFO | Installation finished successfully
```

The password to access the installed system is the one specified in the system profile previously created.

Before you start having fun with your installations, one more thing: you probably noticed that when you executed the `autoinstall` commmand the client reported that a request was submitted and a job started. Job scheduling is an important concept in tessia, so we talk about it in the next section, just don't leave yet :)

# Checking jobs on the scheduler

In tessia every long running action is treated as a job and as such must be scheduled for proper allocation and blocking of the resources involved. That means when you issue the command
to start a system installation the client submits a request to the server to schedule a job. Usually the system in question belongs to the user and will most
likely be free for use which results in immediate execution. But that might not be always the case. If you try to perform a system installation and the job does not get executed immediately
then possibly the system is currenly blocked by a running action/job (i.e. another installation or task execution).

So how can one tell what is going on? That is the purpose of the `job` sub-family of commands. There you will find the commands for dealing with job scheduling, such as verifying the
 state of jobs and requests.

An example of how to verify the jobs queue:

```
$ tess job list

 job_id |   job_type  |     submit_date     |      start_date     |       end_date      |    requester    |   state   |        description           
--------+-------------+---------------------+---------------------+---------------------+---------------------+-----------+------------------------------
 1      | autoinstall | 2017-02-10 10:20:39 | 2017-02-10 10:21:33 | 2017-02-10 10:21:43 | user@domain.com | CANCELED  | Auto installation of OS rhel7.2 
 2      | autoinstall | 2017-02-10 10:22:07 | 2017-02-10 10:22:07 | 2017-02-10 10:23:26 | user@domain.com | CANCELED  | Auto installation of OS rhel7.2 
 3      | autoinstall | 2017-02-10 10:24:35 | 2017-02-10 10:24:35 | 2017-02-10 10:25:04 | user@domain.com | CANCELED  | Auto installation of OS rhel7.2 
 4      | autoinstall | 2017-02-10 10:25:41 | 2017-02-10 10:25:41 | 2017-02-10 10:27:04 | user@domain.com | CANCELED  | Auto installation of OS rhel7.2 
 5      | autoinstall | 2017-02-10 10:27:21 | 2017-02-10 10:27:21 | 2017-02-10 10:31:25 | user@domain.com | COMPLETED | Auto installation of OS rhel7.2 
```

We can see many installation jobs canceled and the last one successfully completed.

The scheduler is a daemon process that constantly consumes the request queue and updates the job queue accordingly. A request is a short lived entity that exists only during the
interval between each time the scheduler processes the request queue.

It is possible to take a look at the request queue if you suspect something was not yet processed:

```
$ tess job req-list

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

The queue shows that all existing requests were already processed (state `COMPLETED`) and a series of requests to submit new jobs (action_type `SUBMIT`) and cancellations
(action_type `CANCEL`) occurred. Let's see which job the request 2 wanted to cancel:

```
$ tess job req-list --id=2

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

The field `Target job ID` says 1, so this request was to stop job 1 which indeed showed up as canceled in the job list.

By now we have covered the essential parts of the client for you to get started. For details on specific commands you can always check the client help with `--help`
 as well as refer to the [users section](../index.md#users) documentation for detailed information on specific topics.
