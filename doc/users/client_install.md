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
# Client installation

## Pre-requisites

Before client installation, make sure you have the following pre-requisites installed:

* git
* python >= 3.5.2
* python3-pip

The client is currently known to work on Fedora 25 and Ubuntu 16.04 systems.

## Installation steps

Once you have confirmed the pre-requisites fulfilled, follow these steps:

```
[user@host ~]$ git clone git@gitlab.com:tessia/tessia-engine.git
Cloning into 'tessia-engine'...
remote: Counting objects: 1685, done.
remote: Compressing objects: 100% (874/874), done.
remote: Total 1685 (delta 1029), reused 1272 (delta 773)
Receiving objects: 100% (1685/1685), 2.17 MiB | 1.63 MiB/s, done.
Resolving deltas: 100% (1029/1029), done.
Checking connectivity... done.
[user@host ~]$ cd tessia-engine/cli
[user@host cli]$ sudo pip3 install -r requirements.txt
(lots of output ...)
[user@host cli]$ sudo ./setup.py install
(lots of output ...)
```

That's all. To start using the client, type:

```
[user@host ~]$ tessia
Usage: tessia [OPTIONS] COMMAND [ARGS]...

  Tessia command line client

Options:
  -h, --help  Show this message and exit.

Commands:
  conf     manage the client's configuration
  job      commands related to scheduler jobs
  net      manage addresses and network related resources
  perm     manage users, teams and roles
  storage  manage volumes and storage related resources
  system   manage systems and related resources

[user@host ~]$
```

If you saw a help text like the one above, your client was installed successfully.

**Note:** Some users might see an error regarding ASCII encoding when trying to execute the client for the first time.
In case you see such error, you can solve the problem by setting your environment to use UTF-8 with:
```
export LANG=C.UTF-8
```

You might want to make it permanent by adding it to your ```.bashrc``` file.

At this point the installation process is complete. In order to start using the client you need to tell it where the API server is and generate an authentication token for
secure communication. For instructions on how to do it, see [Getting started with the client](client.md)
