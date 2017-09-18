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
# Supported features

Using the tool may help you in different areas of the testing activity.   
But there are some restrictions in each area.

## System installation

You may install systems with different system parameters.  
The tables below provide you with the information about combinations of system parameters which are supported by the tool.  
- "+" means that the feature is supported by the tool;    
- "-" means that the feature is not supported yet (or can't be supported at all);   
- empty cell means that the feature has not been checked yet.  

### Network and volume features in the context of distros and system types:
```
-----------------------------------------------------------------------------------------
Distro                   !        RHEL        !        SLES        !       Ubuntu
-----------------------------------------------------------------------------------------
system type              ! LPAR ! KVM  ! ZVM  ! LPAR ! KVM  ! ZVM  ! LPAR ! KVM  ! ZVM  !
-----------------------------------------------------------------------------------------
volume type:
- DASD                   !  +   !  -   !  -   !  +   !  -   !  -   !  +   !  +   !  -   !
- FCP                    !  +   !  +   !  -   !  +   !  +   !  -   !  +   !  +   !  -   !
volume mpath (FCP only)
- true                   !  +   !  +   !  -   !  +   !  +   !  -   !  +   !  +   !  -   !
- false                  !  +   !  -   !  -   !  +   !  -   !  -   !  +   !  -   !  -   !
network interface type:  
- OSA                    !  +   !  -   !  -   !  +   !  -   !  -   !  +   !  -   !  -   !
- MACVTAP                !  -   !  +   !  -   !  -   !  +   !  -   !  -   !  +   !  -   !  
layer2 (OSA only):
- true                   !  +   !  -   !  -   !  +   !  -   !  -   !  +   !  -   !  -   ! 
- false                  !  +   !  -   !  -   !  +   !  -   !  -   !  +   !  -   !  -   ! 
```

### Partition features in the context of distros, system types and volume types:
```
-----------------------------------------------------------------------------------
Distro                   !        RHEL      !        SLES      !       Ubuntu
-----------------------------------------------------------------------------------
system type              !    LPAR    ! KVM !    LPAR    ! KVM !    LPAR    ! KVM !
-----------------------------------------------------------------------------------
volume type              ! DASD ! FCP ! FCP ! DASD ! FCP ! FCP ! DASD ! FCP ! FCP !
-----------------------------------------------------------------------------------
partition table type:
- dasd                   !  +   !  -  !  -  !  +   !  -  !  -  !  +   !  -  !  -  !
- gpt                    !  -   !  -  !  -  !  -   !  -  !  -  !  -   !  -  !  -  !
- msdos                  !  -   !  +  !  +  !  -   !  +  !  +  !  -   !  +  !  +  !
filesystem type:
- Ext2                   !  +   !  +  !  +  !  +   !  +  !  +  !  +   !  +  !  +  !
- Ext3                   !  +   !  +  !  +  !  +   !  +  !  +  !  +   !  +  !  +  !
- Ext4                   !  +   !  +  !  +  !  +   !  +  !  +  !  +   !  +  !  +  !
- XFS                    !  +   !  +  !  +  !  -   !  -  !  -  !  +   !  +  !  +  !
- BtrFS (not '/' only)   !  -   !  -  !  -  !  -   !  -  !  -  !  +   !  +  !  +  !
- ReiserFS               !  -   !  -  !  -  !  -   !  -  !  -  !  -   !  -  !  -  !
- JFS                    !  -   !  -  !  -  !  -   !  -  !  -  !  -   !  -  !  -  !
- FAT16                  !  -   !  -  !  -  !  -   !  -  !  -  !  -   !  -  !  -  !
- FAT32                  !  -   !  -  !  -  !  -   !  -  !  -  !  -   !  -  !  -  !
mount options:           !  +   !  +  !  +  !  -   !  -  !  -  !  -   !  -  !  -  ! 
```

TODO  
	.	.	.
