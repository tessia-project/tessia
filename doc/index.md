<!--
Copyright 2016, 2017 IBM Corp.

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
# Tessia - Task Execution Supporter and System Installation Assistant

Welcome to the *Tessia* solution!

This software aims to automate and simplify all the steps involved in the systems management activity. Features include:

- *Systems provisioning*: install systems with different combinations of software
- *Jobs execution*: schedule and execute any kind of program

## **Users**

This section provides documentation and howtos for those who want to learn how to use the tool.

- The basics
    - To best understand the resources model and terminology used within the solution, we recommend to read the [Resources model](users/resources_model.md)
    - If you are a new user and want to learn how to use the command line client, visit [Getting started](users/getting_started.md)
- Features
    - **System installation**: automatically install your systems, see examples in [Installations](users/howtos.md#installations).
    - **System Management**: power on systems with different activation profiles, see details in [Power Manager machine](users/powerman_machine.md)
    - **Task execution**: schedule a job to perform automated tasks on a system, currently supported machines are:
        - [Ansible machine](users/ansible_machine.md)
- Misc
    - [Howtos](users/howtos.md) main page with usage examples
    - Explanation about the project's [versioning scheme](users/versioning.md)
    - [Client Installation](users/client_install.md): if you would like to install the command line client to use from your Linux workstation
    - [REST-like API](users/api.md): if you are interested in using tessia with your own automation tools

## **Developers**

This section is for people wanting to collaborate with tessia's development.

- [Coding guidelines](developers/coding_guidelines.md)
- [Development process](developers/dev_process.md)
- [How to setup a development environment](developers/dev_env.md)
- [Integration and unit tests](developers/tests.md)
- [Working with documentation](developers/documentation.md)
- [Continuous Integration](developers/continuous_integration.md)
- [Design topics](developers/design.md)
    - [Architecture](developers/design.md#architecture)
    - [Database](developers/design.md#database) (and how to make changes to its schema)
    - [Authentication subsystem](developers/design.md#authentication-subsystem)
