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

[![license](https://img.shields.io/badge/license-Apache%202.0-blue)](https://gitlab.com/tessia-project/tessia/-/blob/master/LICENSE)
[![pipeline status](https://img.shields.io/gitlab/pipeline/tessia-project/tessia)](https://gitlab.com/tessia-project/tessia/)
[![language](https://img.shields.io/github/languages/top/tessia-project/tessia)](https://gitlab.com/tessia-project/tessia/)
[![latest-release](https://img.shields.io/github/v/tag/tessia-project/tessia)](https://gitlab.com/tessia-project/tessia/)

## What is it?

A tool to automate and simplify the installation/configuration/testing of Linux systems running on the IBM Z platform.

Main functions available in the tool:

- Automatic installation and management of Linux operating systems on IBM Z machines
- Datacenter resources management: storage servers, volumes, network subnets, ip addresses
- Job scheduling for automatic execution of tasks/scripts
- Command line client and REST-like API
- Role based permission model

See the documentation's [Users section](doc/index.md#users) for detailed information about what the tool offers.

Hypervisors supported:

- zHMC (classic and DPM modes)
- z/VM
- KVM for IBM Z

Linux distributions supported:

- RHEL 7.2+
- SLES12 SP1+
- Ubuntu 16.04+

A detailed list of supported installation combinations can be found [here](doc/users/supported_install_combinations.md).

## Quickstart

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

The tool is ready for use. To learn how to install your first system, visit [Getting started](doc/users/getting_started.md).

**IMPORTANT**: In order to be able to install LPARs, one more step is needed.
Refer to the section [Deployment of the auxiliar live-image](doc/users/server_install.md#deployment-of-the-auxiliar-live-image) for details.

Other deployment options are listed in [Server installation guide](doc/users/server_install.md).

[Server configuration](doc/users/server_conf.md) explains how to set proper authentication and other configuration details.

## What's new

Check the [Release notes](doc/releases.md).

## Documentation

User documentation is available at the [Users section](doc/index.md#users). For an introduction about the tool concepts, see [Resources model](doc/users/resources_model.md).
To learn how to use the command line client, see [Getting started](doc/users/getting_started.md).

## Contributing

If you are interested in contributing to the project, read [How to contribute (development process)](doc/developers/contributing.md).
Additional topics for developers are available at the [Developers section](doc/index.md#developers).

## Reporting issues

Feel free to open issues and raise questions in [tessia issue tracker](https://gitlab.com/tessia-project/tessia/-/issues). If you are not comfortable disclosing issue details or it is a security related issue, please send an email to (tessia-private at lists.openmainframeproject.org) instead.

## Contact

You can join us on IRC at the `#tessia` channel on [OFTC](http://www.oftc.net) and our mailing list (tessia-user at lists.openmainframeproject.org)

## License

Tessia is licensed under the [Apache 2.0 license](LICENSE).
