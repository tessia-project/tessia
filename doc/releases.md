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
# Release notes

## 2.1.0 (2024-02-29)

- Update baselib to new [version](https://gitlab.com/tessia-project/tessia-baselib/-/commits/1.4.0)
- Add [tela](https://gitlab.com/tessia-project/tessia/-/merge_requests/386) state_machine
- Add support for [NVMe](https://gitlab.com/tessia-project/tessia/-/merge_requests/384) load for LPARs
- Check for git default branch in [ansible](https://gitlab.com/tessia-project/tessia/-/merge_requests/383) state_machne
- Update to new container base [images](https://gitlab.com/tessia-project/tessia/-/merge_requests/380)
- Support for RoCE only installations in [SLES](https://gitlab.com/tessia-project/tessia/-/merge_requests/379) and [Ubuntu](https://gitlab.com/tessia-project/tessia/-/merge_requests/377)
- Update default OS templates to support [DASDs](https://gitlab.com/tessia-project/tessia/-/merge_requests/385) with subchannel>0

## 2.0.6 (2023-06-22)

- Fix baselib for SSL/TLS connection [hostname](https://gitlab.com/tessia-project/tessia-baselib/-/merge_requests/74) check
- Fix reduce z/VM installation [time](https://gitlab.com/tessia-project/tessia-baselib/-/merge_requests/73)
- Fix for Ubuntu 22.04 and later [installation](https://gitlab.com/tessia-project/tessia/-/merge_requests/371)
- Tessia CLI better bash [completion](https://gitlab.com/tessia-project/tessia/-/merge_requests/366)

## 2.0.5 (2022-08-05)

- New API [endpoint](https://gitlab.com/tessia-project/tessia/-/merge_requests/354) to download job logs
- Usability improvements: better z/VM [IPL sequence](https://gitlab.com/tessia-project/tessia-baselib/-/merge_requests/70),
  new filter parameters for [jobs](https://gitlab.com/tessia-project/tessia/-/merge_requests/323) in command-line interface,
  clarified messages for [partitioning](https://gitlab.com/tessia-project/tessia/-/merge_requests/357) and [poweron](https://gitlab.com/tessia-project/tessia/-/merge_requests/356) errors
- [Disabled](https://gitlab.com/tessia-project/tessia/-/merge_requests/359) TLS 1.1 by default

If you update an existing tessia instance, you should also update installation templates, because some [template variables](users/autoinstall_machine.md#autotemplate-variables) have changed.

## 2.0.4 (2021-07-05)

- Added HMC and CPC [monitoring](https://gitlab.com/tessia-project/tessia/-/commit/957eec644b3a5e06277f2167f9f2be66221195f6) (preview)
- Support [querying](https://gitlab.com/tessia-project/tessia-baselib/-/commit/8f99699d1462efa4890b3173c955224796a934c8) DPM storage groups to avoid path specification for SCSI volumes
- Usability improvements: system profile [cloning](https://gitlab.com/tessia-project/tessia/-/commit/ace9035f7de2984403f4536a1ba7f31100e588de), lifting [restriction](https://gitlab.com/tessia-project/tessia/-/commit/5c3909ae0027b30ed721ec43c01e5a11a80ae296) on unique repo urls, system info to [include](https://gitlab.com/tessia-project/tessia/-/commit/f66ba9f3a07abaa7cbe6af741e3543fe21b8f7b6) assigned IP addesses and more
- Add SLES 15.3 [support](https://gitlab.com/tessia-project/tessia/-/commit/73990841c41f56f56a94aac05973af8d7497487f)
- Deployment: allow [tweaking](https://gitlab.com/tessia-project/tessia/-/commit/6ae67e6d745e9031876216c0ec55bceede436216) user and group ID of tessia user in server container

## 2.0.3 (2021-04-08)

- Improve Ubuntu 21 installation [support](https://gitlab.com/tessia-project/tessia/-/commit/559bc86bfc6a75f93bc339a7ce43aefd6a6dddbf)
- Updates to build process - [include](https://gitlab.com/tessia-project/tessia/-/commit/136829415f06e89d9b02618cee6cafc27eb4f7ce) Rust compiler for python builds
- Internal [rewrite](https://gitlab.com/tessia-project/tessia/-/commit/369f4e588fb74b80620e0f1e0429649c89ccf3b6) of autoinstall machine

tessia-baselib:
- support [MDISK](https://gitlab.com/tessia-project/tessia-baselib/-/commit/346cb9e97012aca4fcbe3c5f14c273bfc1291532) and [Hipersockets](https://gitlab.com/tessia-project/tessia-baselib/-/commit/885579d74103f5937e39d35ba86fb7df6842cab7) attachments
- puncher device is now [reset](https://gitlab.com/tessia-project/tessia-baselib/-/commit/d30bbf93e35e4836b983602a1c6cff4fc84d2b29) after z/VM installation
- last used device is set for DPM machines [after boot](https://gitlab.com/tessia-project/tessia-baselib/-/commit/055642a10d0ea7e91709e71fea76f6e4e67805c0)

## 2.0.2 (2021-01-21)

- Add z/VM transfer buffer size option [link](https://gitlab.com/tessia-project/tessia/-/commit/64be44fdfd81241226c80831d6dc6cdf0e2b0f40)
- Do not fail poweron job on verification error [link](https://gitlab.com/tessia-project/tessia/-/commit/067216fc6667b1288da6c36855f1ff131f6b27a4)
- Switch off I/O device auto-configuration for SLES15.2 [link](https://gitlab.com/tessia-project/tessia/-/commit/cbae4a640f883d30c07812d2a0b460c5bab7bba7)
- Update kdump options in RHEL8 templates [link](https://gitlab.com/tessia-project/tessia/-/commit/75e4fd3b574896d05068a76e8e9786bf4e17a0ce)

tessia-baselib:
- Proceed with installation on 'Base cpu cannot be detached' [link](https://gitlab.com/tessia-project/tessia-baselib/-/commit/dc9fe84e35170a1fa1ffce7ab73a66807d68cf56)
- Fix broken long kernel command lines [link](https://gitlab.com/tessia-project/tessia-baselib/-/commit/2e74c823b0c8a41b909af89d60c59ed3834b4983)
- Fix sending commands to HMC too early [link](https://gitlab.com/tessia-project/tessia-baselib/-/commit/a7e8967080999f18f841312d8bd854d3bf2aa9a0)
- Improve interaction with HMC [link](https://gitlab.com/tessia-project/tessia-baselib/-/commit/7f7d238233a896af16258be3e167f42904dbdc1d)

## The project switched to a rolling updates strategy.

## 18.06 (2018-06-12)

Attention: if you are upgrading from a previous version, this release includes changes to the following installation templates:

- fedora-default
- ubuntu16-default
- rhel7-default

And adds two new templates:

- fedora-kvmhost
- ubuntu16-kvmhost

Make sure to update existing templates in your database with the `tess autotemplate edit ` command and add new ones with `tess autotemplate add` command.

### Fixes

- power management: do not report error if --noverify is specified
- rhel7 template update: eliminate number of disks contraint by using kickstart's %pre section to activate disks instead of kernel cmdline parameters
- post-installation memory check: use 'lsmem' instead of /proc/meminfo for more accurate information
- pick up baselib 0.2.4 fixes
- client: remove wrong parameter `--os` from autotemplate edit command

### Improvements

- rhel7 template update: add package repository config in %post section
- add kickstart template for fedora installations
- autoinstall: improve connection handling during reboot after installation
- enforce the need for 'UPDATE' permission to run jobs on systems, this means any installation/power management action requires the requester to have update permission to the target system.
- client: improve job handling
    - user can choose to cancel a job upon keyboard interrupt
    - client will wait for job to start before fetching output
- jobs: report in job output when cancel and timeout signals are received
- minor fixes to ubuntu and redhat installations

### Features

- two new installation templates for deployment of KVM hypervisor on Fedora or Ubuntu16.04
- allow user to specify a branch/commit/tag for ansible jobs
- add support to set output verbosity of jobs

## 18.04 (2018-04-27)

### Fixes

- specify root user in autoinst template
- cli: improve verification of input values for network commands ([#1](https://gitlab.com/tessia-project/tessia/issues/1))
- api: verify input values for ip addresses ([#3](https://gitlab.com/tessia-project/tessia/issues/3))
- debian: specify OSA iface to use when multiple ifaces are present
- debian: fix last partition's size math

### Improvements

- post_install: use threads per core when verifying number of cpus (SMT systems)
- ubuntu: set external repositories on installed system
- post_install: issue warning instead of raising error when a mismatch is detected
- zvm: add howto example of how to install a zvm guest
- allow null mac addresses for OSA cards

### Features

- support for enabling/disabling case sensitive in logins

## 18.03 (2018-03-18)

### New features

- Support installation of z/VM guests
- Allow administrator to enter new operating systems for installation

### Improvements

- Make auto templates reusable by multiple operating systems
- client: fix vol-add dealing with fcp disks
- client: warn user when job output is interrupted

## 18.01 (2018-02-01)

### New features

- Initial release
- Support to installation of zHMC LPARs in classic mode and KVM guests
