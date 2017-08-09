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

There are two possible methods to install and use the command line client:

- [Local installation with pip/setuptools](#local-installation-with-pipsetuptools)
- [Build and run a docker container](#build-and-run-a-docker-container)

# Local installation with pip/setuptools

This method is recommended if you are familiar with python installations.

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

If you see a help text like the one above, your client was installed successfully.

**Note:** Some users might see an error regarding ASCII encoding when trying to execute the client for the first time.
In case you see such error, you can solve the problem by setting your environment to use UTF-8 with:
```
export LANG=C.UTF-8
```

You might want to make it permanent by adding it to your ```.bashrc``` file.

At this point the installation process is complete. In order to start using the client you need to enter the hostname of the API server and generate an authentication token for
secure communication. The server's hostname and credentials are dependent on the environment you are using so if you were following another tutorial you can go back to check
for related information.

# Build and run a docker container

This method is recommended for those who do not want to deal with distro/python dependencies, as everything is included in the docker image.

## Pre-requisites

- docker daemon installed and running

## Installation steps

Create a new directory and clone the repository inside it:

```
[user@host ~]$ mkdir tessia-cli && cd tessia-cli
[user@host tessia-cli]$ git clone git@gitlab.com:tessia/tessia-engine.git
Klone nach 'tessia-engine' ...
remote: Counting objects: 3236, done.
remote: Compressing objects: 100% (1417/1417), done.
remote: Total 3236 (delta 2035), reused 2782 (delta 1764)
Empfange Objekte: 100% (3236/3236), 3.17 MiB | 3.32 MiB/s, Fertig.
Löse Unterschiede auf: 100% (2035/2035), Fertig.
Prüfe Konnektivität ... Fertig.
```

Then, copy the docker files to the current folder and move the whole repository to the `assets` folder:

```
[user@domain tessia-cli]$ cp -r tessia-engine/tools/ci/docker/tessia-cli/* .
[user@domain tessia-cli]$ mv tessia-engine assets/tessia-engine.git
```

Now you just have to execute the build command:

```
[user@domain tessia-cli]$ docker build -t tessia-cli:latest .
Sending build context to Docker daemon  6.671MB
Step 1/8 : FROM ubuntu:latest
 ---> 14f60031763d
Step 2/8 : ARG git_repo=/assets/tessia-engine.git
 ---> Using cache
 ---> cdea02586385
Step 3/8 : ARG DEBIAN_FRONTEND=noninteractive
 ---> Using cache
 ---> 6de0f22150bb
Step 4/8 : RUN apt-get -q update > /dev/null &&     apt-get -yq install --no-install-recommends     locales     python3-pip     git     build-essential     python3-dev > /dev/null &&     apt-get -q clean &&     locale-gen en_US.UTF-8 &&     update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 &&     pip3 -q install -U setuptools &&     pip3 -q install -U     pip     pbr &&     useradd -ms /bin/bash admin
 ---> Using cache
 ---> ad085e82d1f0
Step 5/8 : ENV LC_ALL en_US.UTF-8 LANG en_US.UTF-8
 ---> Using cache
 ---> cdcc16959df5
Step 6/8 : COPY assets /assets/
 ---> a8cb1f45932b
Removing intermediate container a0bc7755fc5d
Step 7/8 : RUN cd /assets &&     git clone $git_repo tessia-engine &&     cd tessia-engine/cli &&     pip3 -q install -U -r requirements.txt &&     ./setup.py -q install &&     apt-get -yq purge --auto-remove     build-essential     python3-dev > /dev/null &&     mv /assets/entrypoint /entrypoint &&     rm -rf /assets
 ---> Running in a42b48592002
Cloning into 'tessia-engine'...
done.
warning: no files found matching 'AUTHORS'
warning: no files found matching 'ChangeLog'
warning: no previously-included files found matching '.gitignore'
warning: no previously-included files found matching '.gitreview'
warning: no previously-included files matching '*.pyc' found anywhere in distribution
 ---> d3de3b0f6681
Removing intermediate container a42b48592002
Step 8/8 : ENTRYPOINT /entrypoint
 ---> Running in a26ddd1fed01
 ---> 976c9ef383ec
Removing intermediate container a26ddd1fed01
Successfully built 976c9ef383ec
Successfully tagged tessia-cli:latest
```

Start the container with a shell as the admin user:

```
[user@domain tessia-cli]$ docker run -ti --rm --user admin --entrypoint=/bin/bash tessia-cli:latest
admin@1c0e1d70c70e:/$ tessia
Usage: tessia [OPTIONS] COMMAND [ARGS]...

  Tessia command line client

Options:
  --version   Show the version and exit.
  -h, --help  Show this message and exit.

Commands:
  autotemplate  manage the autoinstallation templates
  conf          manage the client's configuration
  job           commands related to scheduler jobs
  net           manage addresses and network related resources
  perm          manage users, projects and roles
  repo          manage package repositories
  storage       manage volumes and storage related resources
  system        manage systems and related resources

admin@1c0e1d70c70e:/$
```

If you see a help text like the one above, your client is installed successfully.

At this point the installation process is complete. In order to start using the client you need to enter the hostname of the API server and generate an authentication token for
secure communication. The server's hostname and credentials are dependent on the environment you are using so if you were following another tutorial you can go back to check
for related information.

