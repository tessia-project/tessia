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

# Local installation with pip

The client requires python >= 3.6, once you have it installed follow these steps:

```
# as the root user install the python packaging tools
$ apt-get install python3-pip
$ pip3 install -U pip setuptools
# we recommend to remove pip from distro to avoid conflicts
$ apt-get -y remove python3-pip && hash -r

# switch to target user (skip this step for a global installation)
$ su - _target_user

# clone the repo and switch to the `cli` subfolder
$ git clone https://gitlab.com/tessia-project/tessia.git
$ cd tessia/cli

# pip-install is a wrapper to 'pip install' to allow pip to work with
# packages in subdirectories that use git for project versioning
$ ./pip-install --user . # skip --user for a global installation
```

That's all. To start using the client, type:

```
$ tess
Usage: tess [OPTIONS] COMMAND [ARGS]...

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

```

If you see a help text like the one above, your client was installed successfully.

**Note:** Some users might see an error regarding ASCII encoding when trying to execute the client for the first time.
In case you see such error, you can solve the problem by setting your environment to use UTF-8 with:
```
$ export LANG=C.UTF-8
```

You might want to make it permanent by adding it to your ```.bashrc``` file.

At this point the installation process is complete. In order to start using the client you need to enter the hostname of the API server and generate an authentication token for
secure communication. See the section [Configuration](#configuration) for an example of how to do it.

# Build and run a docker container

Use this method if you don't want to deal with distro/python dependencies as everything is included in the docker image.

```
$ apt-get install docker.io python3-pip
$ git clone https://gitlab.com/tessia-project/tessia.git
$ cd tessia && pip3 install -r tools/ci/requirements.txt
$ tools/ci/orc build --image=tessia-cli
```

Start the container with a shell to the admin user:

```
$ docker run -ti --rm --user admin --entrypoint=/bin/bash tessia-cli:_tag_from_built_image
(container)$ tess
Usage: tess [OPTIONS] COMMAND [ARGS]...

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

```

If you see a help text like the one above, your client is installed successfully.

At this point the installation process is complete. In order to start using the client you need to enter the hostname of the API server and generate an authentication token for
secure communication. See the section [Configuration] for an example of how to do it.

# Configuration

If the server is running SSL with a self-signed certificate you need to provide the client with a trusted certificate so that it knows the connection is safe.
If you are in a trusted environment you can use the command below to connect to the server URL and add the offered certificate to the client configuration:
```
$ openssl s_client -showcerts -connect _your_server_hostname_without_https:5000 < /dev/null 2>/dev/null | sed -ne '/-BEGIN/{:1;$!{/-END/!{N;b1};h}};${x;p}' > $HOME/.tessia-cli/ca.crt
```

Now set the server URL and test it:

```
# set the server url in client config
$ tess conf set-server https://_your_server_hostname:5000

# test the connection, on the first time the client will request your user
# and password in order to generate an authentication token
$ tess conf show
```
