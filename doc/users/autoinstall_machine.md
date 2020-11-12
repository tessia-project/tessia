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
# Autoinstall machine

The autoinstall feature allows you to perform Linux installations using the distro's installer capabilities by means of an autofile (i.e. kickstart/autoinst/preseed).
The autofiles are [jinja2](http://jinja.pocoo.org) templates stored in the tool's database which can be managed via the `tess autotemplate ...` family of commands.

As an example, to list what templates are available and see the content of the template `distro_template_name`, type:

```
$ tess autotemplate list

(many entries...)

$ tess autotemplate print --name=distro_template_name
```

The tool already provides a set of templates for the supported operating systems and users can also create their own templates with `tess autotemplate add ...`.
For a reference of which variables/objects are available in a template, see the section [Autotemplate variables](#autotemplate-variables).

For each supported operating system there is a default template associated so that installations can be performed without the need for the user to specify which template to use.
You can list all OSes supported and their corresponding default templates by typing `tess os list`.
Although users can create their own templates, *only administrators* can register new OSes. This is to prevent the creation of multiple redundant entries for the same OS version.

# How the auto installation works

What happens when the user submits a job to perform a Linux installation with the following command:

```
$ tess system autoinstall --os=ubuntu16.04.1 --system=cpc3lp25
```

- As no profile was specified, the system's default profile is used (to specify one enter `--profile=`)
- As no custom template was specified, the default template for the OS is used (to specify one enter `--template=`)
- As no custom repository was specified, the tool queries the database for a repository associated with the target OS.
If multiple entries are available, the tool uses preferably the repository which is on the same subnet as the system being installed to improve network performance (it's also possible to specify custom repositories with `--repo=`, see the section [Using custom repositories](#using-custom-repositories) for details)
- The template then gets rendered using the determined values; the resulting file is a valid distro installer autofile (kickstart, autoinst, preseed)
- Autofile is placed on tessia's HTTP server
- Target system is booted with distro's installer image (kernel and initrd) downloaded from the distro's install repository
- The distro installer downloads the generated autofile from tessia's HTTP server and performs the automated installation
- Once the installation is finished tessia's autoinstaller machine validates the parameters of the resulting system (network interfaces, IP addresses, disks and partitions sizes, etc.) to assure the installation completed successfully

# Using custom repositories

There are two types of repositories recognized by the autoinstaller machine:

- install repository: can be used for distro installation; provides distro's installer image files (kernel and initrd)
- package repository: not used during system installation; instead it is added after installation to the package manager configuration of the resulting installed filesystem

Only repositories registered in the database and associated with a target OS are recognized as install repositories and as such suitable for use in distro installations.
You can check which install repositories are available for a given OS by typing:

```
$ tess repo list --os=os_version
```

If a repository in the database does not have an associated OS then it is regarded by the tool as a package repository only.

It's possible to specify custom repositories for a system installation by using the `--repo=` parameter for both types of repository. Examples:

```
# system installation using install repository named 'osinstall-1'
$ tess system autoinstall --os=os_version --system=cpc3lp25 --repo=osinstall-1

# system installation using default install repository (therefore not specified)
# and 'packages-1' as a package repository (gets added to the resulting installed system):
$ tess system autoinstall --os=os_version --system=cpc3lp25 --repo=packages-1

# package repositories can also be entered multiple times or directly in URL form:
$ tess system autoinstall --os=os_version --system=cpc3lp25 --repo=packages-1 --repo=http://myserver.com/packages/mydistro/

# and you can also combine both types in the same installation:
$ tess system autoinstall --os=os_version --system=cpc3lp25 --repo=osinstall-1 --repo=packages-1 --repo=http://myserver.com/packages/mydistro/
```

# Custom kernel command line arguments

Autoinstall machine uses some kernel command line arguments which are predefined. For the reference see the section [Predefined kernel command line parameters](#predefined-kernel-command-line-parameters). 

For Linux systems you can specify additional kernel command line arguments both for the target (installed) system as well as for the Linux distro's installer during installation time.

To define additional custom kernel command line arguments for your installed system (final state), edit the desired system activation profile with the `--kargs-target` parameter. Example:

```
$ tess system prof-edit --name=default --system=cpc3lp25 --kargs-target='selinux=0 nosmt=false'
```

These arguments will then be added to the generated autofile and included in the boot loader configuration of the resulting installation by the distro installer.

If you want to define additional kernel arguments for the distro installer to be used only during installation time, edit the desired profile with the `--kargs-installer` parameter. Example:

```
$ tess system prof-edit --name=default --system=cpc3lp25 --kargs-installer='nosmt=true zfcp.allow_lun_scan=0'
```

Any kernel arguments for the distro installer defined in this manner will take precedence over default values used by the autoinstall machine.

# Autotemplate variables

All the necessary information for a template is contained in the `config` dictionary.   
The following variables/objects are available in the `config` and can be used in a template:

- [ifaces](#ifaces) - interfaces which are attached to the target system profile   
- [svols](#svols) - storage volumes attached to the system profile   
- [repos](#repos) - repositories recognized by the autoinstall machine   
- [server_hostname](#server_hostname) - tessia server hostname   
- [system_type](#system_type) - target system type   
- [credentials](#credentials) - credentials used during installation except for ssh root password   
- [sha512rootpwd](#sha512rootpwd) - ssh root password generated with sha512 algorithm   
- [hostname](#hostname) - resolvable hostname of the target system or ip address   
- [autofile](#autofile) - path to the autofile (i.e. kickstart/autoinst/preseed)  
- [operating_system](#operating_system) - operating system which should be installed   
- [profile_parameters](#profile_parameters) - custom kernel cmdline parameters for the Linux installer and for the installed system   
- [gw_iface](#gw_iface) - gateway interface for the target system (i.e. a network interface to perform installation)  
- [root_disk](#root_disk) - disk for root partition, the only disk supported during installation, for Ubuntu templates only   
- [webhook](#webhook) - installer-webhook for Ubuntu20 subiquity installer only  

Below you can find structure description and a sample of each object.

### ifaces
```
ifaces [
        {'attributes': {'layer2': True|False,
                        'portno': '0|1',
                        'ccwgroup': '0.0.f500,0.0.f501,0.0.f502',
                        'portname': 'OSAPORT'},
         'type': 'OSA',
         'mac_addr': '02:20:10:10:76:00',
         'ip': '192.168.0.9',
         'ip_type': 'ipv4'|'ipv6',
         'subnet': '192.168.0.0',
         'mask': '255.255.255.0',
         'mask_bits': '24',
         'search_list': None,
         'vlan': None,
         'dns_1': '8.8.8.8',
         'dns_2': None,
         'osname': 'encf500',
         'is_gateway': True,
         'gateway': '192.168.0.1',
         'systemd_osname': 'enccw0.0.f500'},

        {'attributes': {'fid': '111'}, 
         'type': 'ROCE', 
         'mac_addr': '02:20:10:10:76:00', 
         'ip': None, 
         'subnet': None, 
         'mask_bits': None, 
         'mask': None, 
         'vlan': None, 
         'osname': 'en518', 
         'is_gateway': False},

        ...
]

ifaces [
        {'attributes': {'hostiface': 'enccw0.0.f500'},
         'type': 'MACVTAP',   
         'mac_addr': '02:20:10:10:76:01',
         'ip': '192.168.2.9',
         'ip_type': 'ipv4'|'ipv6',
         'subnet': '192.168.0.0',
         'mask': '255.255.255.0',
         'mask_bits': '24',
         'search_list': None,
         'vlan': None,
         'dns_1': '8.8.8.8',
         'dns_2': None,
         'osname': 'en0',
         'is_gateway': True,
         'gateway': '192.168.0.1'}
]
```
```
$ tess system iface-types

 Type name |            Description
-----------+-----------------------------------
 OSA       | OSA card
 MACVTAP   | KVM macvtap configured by libvirt
 ROCE      | PCI card
```
### svols
```
svols [
       {'type': 'DASD',
        'volume_id': '7e2e',
        'server': 'DS8K16',
        'system_attributes': {'device': '/dev/disk/by-path/ccw-0.0.7e2e'},
        'specs': {},
        'size': 19073,
        'part_table': {'type': 'dasd',
                       'table': [{'fs': 'ext3',
                                  'mo': None,
                                  'mp': '/',
                                  'size': 19072,
                                  'type': 'primary'}]},
        'is_root': True},

       {'type': 'DASD',
        'volume_id': '7e2f',
        'server': 'DS8K16',
        'system_attributes': {'device': '/dev/disk/by-path/ccw-0.0.7e2f'},
        'specs': {},
        'size': 19073,
        'part_table': {'type': 'dasd',
                       'table': [{'fs': 'swap',
                                  'mo': None,
                                  'mp': None,
                                  'size': 19072,
                                  'type': 'primary'}]},
        'is_root': False},

       {'type': 'FCP',
        'volume_id': '1020304500000000',
        'server': 'DS8K22',
        'system_attributes': {'device': '/dev/disk/by-id/dm-uuid-mpath-33005566777fff5f30000000000008888'},
        'specs': {'wwid': '33005566777fff5f30000000000008888',
                  'adapters': [{'devno': '0.0.1900', 'wwpns': ['50050555050555e3']}, 
                               {'devno': '0.0.1940', 'wwpns': ['50050555051555e3']}], 
                  'multipath': True},
        'size': 19073,
        'part_table': {'type': 'msdos',
                       'table': [{'fs': 'ext4',
                                  'mo': None,
                                  'mp': '/home/user1',
                                  'size': 9536,
                                  'type': 'primary'},

                                 {'fs': 'ext2',
                                  'mo': None,
                                  'mp': '/home/user2',
                                  'size': 9536,
                                  'type': 'primary'}]},
        'is_root': False},

       {'type': 'HPAV', 
        'volume_id': 'ed52', 
        'server': 'DS8K16', 
        'system_attributes': {'device': '/dev/disk/by-path/ccw-0.0.ed52'}, 
        'specs': {}, 
        'size': 0, 
        'part_table': None, 
        'is_root': False}
]
```
These volume types are supported:
```
$ tess storage vol-types

 Type name |        Description
-----------+---------------------------
 DASD      | DASD disk type
 HPAV      | HPAV alias for DASD disks
 FCP       | FCP-SCSI disk type
```
### repos
```
repos [
       {'url': 'http://myserver.com/suse/s390x/SLES12.3/DVD/',
        'desc': 'SLES12.3',
        'name': 'SLES12.3',
        'os': 'sles12.3',
        'install_image': None},

       {'url': 'http://myserver.com/ubuntu/UBUNTU20.04/CD',
        'desc': 'Ubuntu20.04',
        'name': 'Ubuntu20.04',
        'os': 'ubuntu20.04',
        'install_image': 'http://myserver.com/ubuntu/UBUNTU20.04/focal-live-server-20200702-s390x.iso'},

       {'url': 'http://myserver.com/Packages/packages-1/', 
        'desc': 'packages-1', 
        'name': 'packages-1', 	
        'os': None, 
        'install_image': None}
]
```
`install_image` - differs from 'None' for Ubuntu20 subiquity installer only
### server_hostname
```
server_hostname server.domain
```
### system_type
```
system_type LPAR|ZVM|KVM
```
```
$ tess system types

 Type name | Architecture |    Description
-----------+--------------+--------------------
 CPC       | s390x        | System z CPC
 LPAR      | s390x        | System z LPAR
 ZVM       | s390x        | zVM guest
 KVM       | s390x        | System z KVM guest
```
### credentials
```
credentials {'admin-user': 'root', 
             'admin-password': 'mypasswd',
             'zvm-password': 'zvmpasswd' 
             'vnc-password': '5Tizv6tj'}
```
`zvm-password` - for ZVM system type only  
`vnc-password` - generated pseudo-random password for VNC session
### sha512rootpwd
```
sha512rootpwd $6$wDDkH53WXF.WgV36$l.3o7Uv01NzJ/klvmjeNVcDMis/jSOeQKhP1aR/ZviC1Ef6vxJmWVfAwzLFJr/RapYTOtu5Kr7DKQqrvJjJW6/
```
### hostname
```
hostname cpc3lp25.domain.com|192.168.0.9
```
### autofile
```
autofile http://server.domain.com/static/cpc3lp25-profile1
```
### operating_system
```
operating_system {'major': 12, 
                  'minor': 3, 
                  'pretty_name': 'SUSE Linux Enterprise Server 12 SP3'}
```
### profile_parameters
```
profile_parameters {'linux-kargs-target': 'selinux=0 nosmt=false', 
                    'linux-kargs-installer': 'nosmt=true zfcp.allow_lun_scan=0'}
```
or
```
profile_parameters None
```
### gw_iface
```
gw_iface {'attributes': {'layer2': True|False,
                         'portno': '0|1',
                         'ccwgroup': '0.0.f500,0.0.f501,0.0.f502',
                         'portname': 'OSAPORT'},
          'type': 'OSA',
          'mac_addr': '02:20:10:10:76:00',
          'ip': '192.168.0.9',
          'ip_type': 'ipv4'|'ipv6',
          'subnet': '192.168.0.0',
          'mask': '255.255.255.0',
          'mask_bits': '24',
          'search_list': None,
          'vlan': None,
          'dns_1': '8.8.8.8',
          'dns_2': None,
          'osname': 'encf500',
          'is_gateway': True,
          'gateway': '192.168.0.1',
          'systemd_osname': 'encf500'}

```
### root_disk
```
root_disk {'type': 'FCP',
           'volume_id': '1020304500000000',
           'server': 'DS8K22',
           'system_attributes': {'device': '/dev/disk/by-id/dm-uuid-mpath-33005566777fff5f30000000000008888'},
           'specs': {'wwid': '33005566777fff5f30000000000008888',
                     'adapters': [{'devno': '0.0.1900', 'wwpns': ['50050555050555e3']}, 
                                  {'devno': '0.0.1940', 'wwpns': ['50050555051555e3']}], 
                     'multipath': True},
           'size': 19073,
           'part_table': {'type': 'msdos',
                          'table': [{'fs': 'ext4',
                                     'mo': None,
                                     'mp': '/',
                                     'size': 19072,
                                     'type': 'primary',
                                     'start': 1,
                                     'end': 19073,
                                     'parted_fs': 'ext2',
                                     'device': ''/dev/disk/by-id/dm-uuid-mpath-33005566777fff5f30000000000008888'}]},
           'is_root': True}
```
### webhook
```
webhook {'endpoint': 'http://server.domain.com:7223/log/',
         'key': 'cpc3lp25-profile1',
         'token': 'a1BCdIxFnHIqJK_L4MoNhOPuRSxTUVVcuW7caX5Ygdc'}
```

# Predefined kernel command line parameters

Autoinstall machine uses several predefined kernel command line arguments. If necessary, you can override some or specify additional parameters, 
for the reference see the section [Custom kernel command line arguments](#custom-kernel-command-line-arguments).  

The predefined kernel command line arguments depend on a distro type, system type and iface type. The following predefined parameters are used by autoinstall machine:

### redhat
LPAR, zVM:  
`ro ramdisk_size=50000 inst.sshd cio_ignore=all,!condev`  
KVM:  
`ro ramdisk_size=50000 inst.sshd`  

### suse
all system types:  
`root=/dev/ram1 ro init=/linuxrc TERM=dumb UseVNC=1 linuxrclog=/dev/console UseSSH=1 start_shell`  
additional parameters for OSA iface type:  
`zfcp.dif=0 MANUAL=0 InstNetDev=osa OSAInterface=qdio OSAMedium=eth`  

### debian:
LPAR, zVM:  
`zfcp.allow_lun_scan=0 zfcp.dif=0 netcfg/use_autoconfig=false netcfg/disable_autoconfig=true netcfg/confirm_static=true priority=critical network-console/start=continue`   
KVM:  
`netcfg/use_autoconfig=false netcfg/disable_autoconfig=true netcfg/confirm_static=true priority=critical network-console/start=continue` 

### subiquity:
all system types:  
`autoinstall`  
