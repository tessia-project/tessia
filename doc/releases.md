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

## 2.0.2 (the latest)

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
