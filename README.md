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

[![pipeline status](https://gitlab.com/tessia-project/tessia/badges/master/pipeline.svg)](https://gitlab.com/tessia-project/tessia/commits/master)
[![coverage report](https://gitlab.com/tessia-project/tessia/badges/master/coverage.svg)](https://gitlab.com/tessia-project/tessia/commits/master)

# What is it?

A tool to automate and simplify the installation/configuration/testing of Linux systems running on the IBM Z platform.

Main functions available in the tool:

- Automatic installation and management of Linux operating systems on IBM Z machines
- Datacenter resources management: storage servers, volumes, network subnets, ip addresses
- Job scheduling for automatic execution of tasks/scripts
- Command line client and REST-like API
- Role based permission model

See the documentation's [Users section](doc/index.md#users) for detailed information about what the tool offers.

Hypervisors supported:

- zHMC (classic mode)
- KVM for IBM Z

Support for z/VM guests is currently under development.

Linux distributions supported:

- RHEL 7.2+
- SLES12 SP1+
- Ubuntu 16.04+

A detailed list of supported installation combinations can be found [here](doc/users/supported_install_combinations.md).

# Quickstart

Deploy using docker containers, you will need docker 1.12.0+ and docker-compose 1.9.0+ installed on your system.

```
# install pip for python3
$ apt-get install python3-pip

# clone repo and install the deploy tool requirements
$ git clone https://gitlab.com/tessia-project/tessia.git
$ cd tessia && pip3 install -r tools/ci/requirements.txt

# build the docker images
$ tools/ci/orc build

# start the containers (it's done via docker-compose)
$ tools/ci/orc run

# see the 3 containers running - server, database, and client
$ docker-compose ps

# use the admin user available in the client container to test the service:
$ docker exec -ti --user admin tessia_cli_1 tess conf show
```

You can manage the service with the usual `docker-compose` commands. If you want to manage it from a different folder, simply copy the generated files
`.env` and `.docker-compose.yaml` to the desired folder.

The `admin` user in the client container is the entry point for creating additional users, resources, etc. Note that you need to adjust the server
authentication configuration before newly created users are able to login. See the [Server configuration](doc/users/server_conf.md) page to learn how to set proper authentication
and other configuration details. See also the [Permissions model](doc/users/permissions_model.md) page to understand how to manage multiple users.

If you prefer a manual installation method (without docker), see [Manual method](doc/users/server_install.md#manual-method).

# Documentation

User documentation is available at the [Users section](doc/index.md#users). For an introduction about the tool concepts, see [Resources model](doc/users/resources_model.md).
To learn how to use the command line client, see [Getting started](doc/users/getting_started.md).

# Contributing

If you are interested in contributing to the project, please read the following pages:

- [How to setup a development environment](doc/developers/dev_env.md)
- [Coding guidelines](doc/developers/coding_guidelines.md)
- [Development process](doc/developers/dev_process.md)
- [Working with documentation](doc/developers/documentation.md)

More topics are available at the [Developers section](doc/index.md#developers).

# License

Tessia is licensed under the [Apache 2.0 license](LICENSE).
