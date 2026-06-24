<!--
Copyright 2026 IBM Corp.

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
# Canton Overview

Canton provides an aarch64 KVM-based environment that allows operating system deployments using the same Tessia autoinstall workflow. The installation process uses dedicated Canton repositories and templates available in Tessia. 

Assuming the host operating system is RHEL or Fedora, follow the steps below to set up the Canton environment and perform autoinstallation.

# Pre-requisites

- Install virtualization packages to provide the KVM/Libvirt virtualization to run Canton virtual machines on host
```
dnf group install --with-optional virtualization
```
- Install aarch64 QEMU support to enable emulation and virtualization for aarch64 guest systems
```
dnf install qemu-system-aarch64
```
- Start the libvirt service to activates the virtualization management service used to create and manage Canton guests
```
service libvirtd start
```
- System type has to be `KVMA` to specify that the target system is an arrch64 KVM based guest running on the Canton environment
- Network interface device name should be `enp1s0` configuration as the primary network interface name for aarch64

# Canton Repositories supported in tessia

```
1 rhel9.6-bistro-arm
2 rhel10.1-bistro-arm
3 fedora43-bistro-arm
4 sles15.7-bistro-arm
5 sles16.0-qu1-bistro-arm
```

# Canton Templates Supported in Tessia

```
1 rhel9.6-default-arm
2 rhel10.1-default-arm
3 fedora-internal-f43-arm
4 sles15.7-default-arm
5 sles16.0-default-arm
```

### Note:

- Autoinstall must be performed using the Canton repo and corresponding template. The operating system configuration remains consistent between `s390x` and `Canton`.
- The Canton autoinstall process takes approximately 80 to 100 mins

### Example:

```
tess system autoinstall --system a35kvm01 --os rhel10.1 --repo rhel10.1-bistro-arm --template rhel10.1-default-arm --verbosity debug
```