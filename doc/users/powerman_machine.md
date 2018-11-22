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
# Power Manager machine

This pages describes how you can poweron and poweroff your installed systems.

# How to poweron (activate) a system

In order to power on a system tessia uses so called activation profiles. Profiles describe how the configuration of a system should be done during activation,
i.e. the volumes and network interfaces to be attached (for details about activation profiles, see
[System Activation Profiles](resources_model.md#system-activation-profiles)). Each system has a default activation profile defined which is used in the different
operations when none is specified.

Let's see how this works in practice. Assume a given LPAR system with the following two profiles:

```
user@tessia-cli:~$ tess system prof-list --long --system=cpc3lp52

Profile name                : fcp1
System                      : cpc3lp52
Required hypervisor profile : cpc3/default
Operating system            : 
Default                     : False
CPU(s)                      : 2
Memory                      : 4.0 GiB
Parameters                  : 
Credentials                 : {'admin-password': '****', 'admin-user': '****'}
Storage volumes             : [ds8k16/1022400200000000], [ds8k16/1022400000000000]
Network interfaces          : [gb-extern/192.168.161.222]
Gateway interface           : 


Profile name                : dasd-default
System                      : cpc3lp52
Required hypervisor profile : cpc3/default
Operating system            : 
Default                     : True
CPU(s)                      : 2
Memory                      : 4.0 GiB
Parameters                  : 
Credentials                 : {'admin-password': '****', 'admin-user': '****'}
Storage volumes             : [ds8k16/3957], [ds8k16/3956]
Network interfaces          : [gb-extern/192.168.161.222]
Gateway interface           : 
```

By powering on the system without specifying a profile, the default profile named 'dasd-default' is used:

```
user@tessia-cli:~$ tess system poweron --name=cpc3lp52

Request #192 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #173
Waiting for job output (Ctrl+C to stop waiting)
2017-09-26 11:43:08 | INFO | new stage: execute-action
2017-09-26 11:43:08 | INFO | Current action is poweron system cpc3lp52
2017-09-26 11:43:08 | INFO | System topology is: cpc3 (CPC) -> cpc3lp52 (LPAR)
2017-09-26 11:43:08 | INFO | Checking if target system cpc3lp52 is already up
2017-09-26 11:43:23 | INFO | Executing poweron of system cpc3lp52
2017-09-26 11:43:41 | INFO | System cpc3lp52 successfully powered on
2017-09-26 11:43:41 | INFO | new stage: verify-configuration
2017-09-26 11:43:41 | INFO | Waiting for system cpc3lp52 to come up (90 seconds)
2017-09-26 11:44:01 | INFO | Verifying if current state of system cpc3lp52 matches profile 'dasd-default'
2017-09-26 11:44:09 | INFO | new stage: cleanup
2017-09-26 11:44:09 | INFO | Task finished successfully
```

If we wanted instead to use the profile `fcp1` we just need to add `--profile=fcp1` to the command:

```
user@tessia-cli:~$ tess system poweron --name=cpc3lp52 --profile=fcp1

Request #198 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #178
Waiting for job output (Ctrl+C to stop waiting)
2017-09-26 12:16:06 | INFO | new stage: execute-action
2017-09-26 12:16:06 | INFO | Current action is poweron system cpc3lp52
2017-09-26 12:16:06 | INFO | System topology is: cpc3 (CPC) -> cpc3lp52 (LPAR)
2017-09-26 12:16:06 | INFO | Checking if target system cpc3lp52 is already up
2017-09-26 12:16:06 | INFO | System is already up
2017-09-26 12:16:06 | INFO | Verifying if current state of system cpc3lp52 matches profile 'fcp1'
2017-09-26 12:16:10 | WARNING | State verification of system cpc3lp52 failed: Command failed, output: cpc3lp52.domain.com | FAILED! => {
    "changed": false,
    "err": "Error: Could not stat device /dev/disk/by-id/dm-uuid-mpath-11002076305aac1a0000000000002202 - No such file or directory.\n",
    "failed": true,
    "msg": "Error while getting device information with parted script: '/sbin/parted -s -m /dev/disk/by-id/dm-uuid-mpath-11002076305aac1a0000000000002202 -- unit 'B' print'",
    "out": "",
    "rc": 1
}

2017-09-26 12:16:10 | INFO | Current state does not match profile therefore restart is needed
2017-09-26 12:16:10 | INFO | Powering off system cpc3lp52
2017-09-26 12:16:11 | INFO | System cpc3lp52 successfully powered off
2017-09-26 12:16:11 | INFO | Executing poweron of system cpc3lp52
2017-09-26 12:17:36 | INFO | System cpc3lp52 successfully powered on
2017-09-26 12:17:36 | INFO | new stage: verify-configuration
2017-09-26 12:17:36 | INFO | Waiting for system cpc3lp52 to come up (90 seconds)
2017-09-26 12:18:16 | INFO | Verifying if current state of system cpc3lp52 matches profile 'fcp1'
2017-09-26 12:18:25 | WARNING | Max MiB size expected for disk /dev/disk/by-id/dm-uuid-mpath-11002076305aac1a0000000000002202 was 10200, but actual is 10240. You might want to adjust the volume size in the db entry.
2017-09-26 12:18:25 | WARNING | Max MiB size expected for disk /dev/disk/by-id/dm-uuid-mpath-11002076305aac1a0000000000002200 was 10200, but actual is 10240. You might want to adjust the volume size in the db entry.
2017-09-26 12:18:25 | WARNING | Max MiB size expected for partnum 2 disk /dev/disk/by-id/dm-uuid-mpath-11002076305aac1a0000000000002200 was 1100, but actual is 1239. Certain Linux installers maximize disk usage automatically therefore this difference is ignored.
2017-09-26 12:18:25 | INFO | new stage: cleanup
2017-09-26 12:18:25 | INFO | Task finished successfully
```

# How to poweroff (deactivate) a system

Powering off a system is very simple, all you need is to specify the system name. Example:

```
user@tessia-cli:~$ tess system poweroff --name=cpc3lp52

Request #191 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #172
Waiting for job output (Ctrl+C to stop waiting)
2017-09-26 11:35:20 | INFO | new stage: execute-action
2017-09-26 11:35:20 | INFO | Current action is poweroff system cpc3lp52
2017-09-26 11:35:20 | INFO | System topology is: cpc3 (CPC) -> cpc3lp52 (LPAR)
2017-09-26 11:35:20 | INFO | Powering off system cpc3lp52
2017-09-26 11:35:20 | INFO | System cpc3lp52 successfully powered off
2017-09-26 11:35:21 | INFO | new stage: verify-configuration
2017-09-26 11:35:21 | INFO | new stage: cleanup
2017-09-26 11:35:21 | INFO | Task finished successfully
```

# Poweron Exclusive

The poweron in exclusive mode is a special mode in which all the other systems under the same hypervisor of the target system are powered
off before the actual power on is performed. This is useful for example when one needs to execute performance measurements and do not want the workload of other
systems to affect the system being evaluated. In this operation mode the tool informs which systems are powered off before the target system is powered
on. Example:

```
user@tessia-cli:~$ tess system poweron --name=cpc3lp52 --profile=fcp1 --exclusive

Request #199 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #179
Waiting for job output (Ctrl+C to stop waiting)
2017-09-26 12:22:54 | INFO | new stage: execute-action
2017-09-26 12:22:54 | INFO | Current action is poweron-exclusive system cpc3lp52
2017-09-26 12:22:54 | INFO | System topology is: cpc3 (CPC) -> cpc3lp52 (LPAR)
2017-09-26 12:22:54 | INFO | Exclusive poweron requested for system cpc3lp52, powering off all sibling systems: cpc3lp53, cpc3lp54, cpc3lp55, cpc3lp56, cpc3lp57
2017-09-26 12:22:55 | INFO | Powering off system cpc3lp53
2017-09-26 12:22:55 | INFO | System cpc3lp53 successfully powered off
2017-09-26 12:22:55 | INFO | Powering off system cpc3lp54
2017-09-26 12:22:55 | INFO | System cpc3lp54 successfully powered off
2017-09-26 12:22:55 | INFO | Powering off system cpc3lp55
2017-09-26 12:22:55 | INFO | System cpc3lp55 successfully powered off
2017-09-26 12:22:55 | INFO | Powering off system cpc3lp56
2017-09-26 12:22:55 | INFO | System cpc3lp56 successfully powered off
2017-09-26 12:22:55 | INFO | Powering off system cpc3lp57
2017-09-26 12:22:55 | INFO | System cpc3lp57 successfully powered off
2017-09-26 12:22:55 | INFO | Checking if target system cpc3lp52 is already up
2017-09-26 12:22:55 | INFO | System is already up
2017-09-26 12:22:55 | INFO | Verifying if current state of system cpc3lp52 matches profile 'fcp1'
2017-09-26 12:23:03 | WARNING | Max MiB size expected for disk /dev/disk/by-id/dm-uuid-mpath-11002076305aac1a0000000000002202 was 10200, but actual is 10240. You might want to adjust the volume size in the db entry.
2017-09-26 12:23:03 | WARNING | Max MiB size expected for disk /dev/disk/by-id/dm-uuid-mpath-11002076305aac1a0000000000002200 was 10200, but actual is 10240. You might want to adjust the volume size in the db entry.
2017-09-26 12:23:03 | WARNING | Max MiB size expected for partnum 2 disk /dev/disk/by-id/dm-uuid-mpath-11002076305aac1a0000000000002200 was 1100, but actual is 1239. Certain Linux installers maximize disk usage automatically therefore this difference is ignored.
2017-09-26 12:23:03 | INFO | System cpc3lp52 is already running as expected, no poweron needed
2017-09-26 12:23:03 | INFO | new stage: verify-configuration
2017-09-26 12:23:03 | INFO | new stage: cleanup
2017-09-26 12:23:03 | INFO | Task finished successfully
```

# Force mode

By default the tool will not perform a poweron if it detects that the system is already powered on and its current state matches the expected profile.
If you want to force the power on to happen in such scenario, use `--force`.

# No verify mode

In order to make sure the environment runs according to the database configuration the tool checks the state (cpu, memory, volumes, network interfaces) of each
system in the hypervisor chain and the target system itself during the power on operation. If you would like to bypass these checks (say, the hypervisor got a cpu hotplugged
and its profile was not updated), use `--noverify`. Keep in mind that by using this parameter the tool cannot guarantee the correct system configuration.

# Profile overrides

In certain situations it might be useful to temporarily power on the system with a different number of cpus or memory size than what is defined in the profile.
For such case the options `--cpu=` and `--memory=` are available. In this mode the tool will boot up the system with the given parameters and verify if the resulting
state conforms to the profile + the overrides. However, it **will not** update the profile entry in the database, therefore a new poweron without specifying any overrides
will restore the system to the state with the original profile parameters.
