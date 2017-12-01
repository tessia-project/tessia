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

This tool aims to automate and simplify the installation/configuration/testing of Linux systems running on the IBM Z platform.

# Users

Documentation explaining how to install and use the tool.

- Installation
    - How to to deploy a server: [Server installation](users/server_install.md)
    - Server configuration reference: [Server configuration](users/server_conf.md)
    - How to install the command line client: [Client installation](users/client_install.md)
- First usage steps
    - To learn how to use the command line client, visit [Getting started](users/getting_started.md)
    - To understand the resources model and terminology used within the solution, we recommend to read the [Resources model](users/resources_model.md)
- Features
    - **Autofile based system installation**: automatically install systems with kickstart/preseed/autoinst templates, see examples in [Installations](users/howtos.md#installations).
        - Which installation combinations are supported by the tool can be found at [Supported installation combinations](users/supported_install_combinations.md)
    - **System Management**: power on systems with different activation profiles, see details in [Power Manager machine](users/powerman_machine.md)
    - **Task execution**: schedule a job to perform automated tasks on one or more system(s). Supported methods:
        - Ansible playbooks via [Ansible machine](users/ansible_machine.md)
- Misc
    - [Howtos](users/howtos.md) main page with usage examples
    - Explanation about the project's [versioning scheme](users/versioning.md)
    - [REST-like API](users/api.md): if you are interested in using tessia with your own automation tools

# Developers

Information for people interested in collaborating with tessia's development.

- [How to contribute (development process)](developers/contributing.md)
- [How to setup a development environment](developers/dev_env.md)
- [Coding guidelines](developers/coding_guidelines.md)
- [Integration and unit tests](developers/tests.md)
- [Working with documentation](developers/documentation.md)
- [Continuous Integration](developers/continuous_integration.md)
- [Design topics](developers/design.md)
    - [Architecture](developers/design.md#architecture)
    - [Database](developers/design.md#database) (and how to make changes to its schema)
    - [Authentication subsystem](developers/design.md#authentication-subsystem)
