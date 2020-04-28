<!--
Copyright 2017, 2018 IBM Corp.

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
# How to setup a development environment

In order to perform testing during development you'll need a environment that look the same as the production one.
The best and simplest way is the docker approach, where your environment is deployed via docker containers by using the `orc` tool.
There's also the python virtualenv approach which demands more manual steps, this method is currently deprecated in favour of the container based approach.

- [Complete dev environment via docker containers](#complete-dev-environment-via-docker-containers)
- [Complete dev environment with remote docker host](#complete-dev-environment-with-remote-docker-host)
- [Server-side dev environment via virtualenv (deprecated)](#server-side-dev-environment-via-virtualenv-deprecated)
- [Client-side dev environment via virtualenv (deprecated)](#client-side-dev-environment-via-virtualenv-deprecated)

## Complete dev environment via docker containers

First and foremost, make sure you have the following software installed:

- docker
- docker-compose
- git v2.7 (git remote get-url)

Then, build the project's containers with the `orc` tool:

```
# the build command will prepare a context dir and trigger the docker build process:
[user@myhost tessia]$ tools/ci/orc build
```

And the corresponding output:

```
building images tessia-cli, tessia-server
INFO: [init] using builder localhost
$ hostname --fqdn
myhost
$ cd /home/user/work/git/tessia && python3 -c 'from setup import gen_version; print(gen_version())'
17.713.740+devd40c703
INFO: [init] tag for images is 17.713.740-devd40c703
INFO: new stage: build
$ mktemp -p /tmp -d
/tmp/tmp.UiFhfNktQn
$ cd /home/user/work/git/tessia && git remote get-url origin
git@gitlab.com:tessia/tessia.git
INFO: [build] detected git repo name is tessia
INFO: [build] creating mirror of git repo
$ cd /tmp/tessia-build-m78bhj_0 && git clone --mirror /home/user/work/git/tessia tessia.git
Klone in Bare-Repository 'tessia.git' ...
Fertig.
INFO: [build] sending git mirror to myhost
INFO: [build] preparing context dir at /tmp/tmp.UiFhfNktQn/tessia-cli
$ cp -r /tmp/tmp.UiFhfNktQn/tessia.git /tmp/tmp.UiFhfNktQn/tessia-cli/assets/tessia.git
INFO: [build] build start at /tmp/tmp.UiFhfNktQn/tessia-cli
$ docker build --force-rm --label com.tessia.version=17.713.740-devd40c703 -t tessia-cli:17.713.740-devd40c703  /tmp/tmp.UiFhfNktQn/tessia-cli
Sending build context to Docker daemon  6.873MB

Step 1/9 : FROM ubuntu:18.04
 ---> d355ed3537e9
Step 2/9 : ARG git_repo=/assets/tessia.git
 ---> Using cache
 ---> 322ccdc8004c

(lots of output suppressed...)

Step 13/13 : LABEL com.tessia.version '17.713.740-devd40c703'
 ---> Running in 09e5f31a85c6
 ---> 2ec8da956542
Removing intermediate container 09e5f31a85c6
Successfully built 2ec8da956542
Successfully tagged tessia-server:17.713.740-devd40c703
INFO: [build] cleaning up work directory
$ rm -rf /tmp/tmp.UiFhfNktQn
INFO: done

[user@myhost tessia]$
```

You can check the available images now directly in docker:

```
[user@myhost tessia]$ docker images
REPOSITORY          TAG                     IMAGE ID            CREATED              SIZE
tessia-server       17.713.740-devd40c703   2ec8da956542        About a minute ago   637MB
tessia-cli          17.713.740-devd40c703   c5db457007e2        2 minutes ago        505MB
ubuntu              latest                  d355ed3537e9        3 weeks ago          119MB
[user@myhost tessia]$
```

You can now start the containers by using the `run` command. Before you do so, we need to discuss about two parameters:

- `--img-passwd-file`: tessia-baselib is the underlying library used for communication with the hypervisors and guests.
When it comes to LPAR network boot support the baselib performs the operation by IPLing a pre-deployed Linux live-image from an
auxiliar disk. This parameter specifies the path to a file containing the root password of the live-image which is injected in
the tessia-server configuration inside the container so that LPARs can be IPLed for installation.
- `--install-server-hostname`: it's very likely that your workstation does not have a resolvable hostname reachable by the
test systems so that they can fetch the auto files (i.e. kickstart) via HTTP during installation. To overcome this you can
use this parameter to specify an IP address or an alternate hostname that the test systems can reach from the network.
Failure to use an adequate hostname will cause systems installations to fail.

Now that we have the parameters clarified, here's how you start your development environment:

```
[user@myhost tessia]$ tools/ci/orc run --devmode --img-passwd-file=/home/user/files/.liveimg-passwd.txt
```

You should see a message informing it's ready:

```
INFO: [init] using builder localhost
$ hostname --fqdn
myhost
INFO: [init] tag for images is 17.713.740-devd40c703
INFO: [run] starting services

(output suppressed...)

$ docker-compose ps
     Name                    Command              State                     Ports
----------------------------------------------------------------------------------------------------
tessia_cli_1      /entrypoint                     Up
tessia_db_1       docker-entrypoint.sh postgres   Up      5432/tcp
tessia_server_1   /entrypoint                     Up      0.0.0.0:5000->5000/tcp, 0.0.0.0:80->80/tcp
INFO: done
[user@myhost tessia]$
```

At this point the containers and the tessia services are running.
Thanks to `--devmode`, your local git repository is bind mounted inside the containers, so any changes you do locally will be reflected in the running container. For example:

```
# add new code to the api authentication module:
[user@myhost tessia]$ vi tessia/server/api/views/auth.py # do some work

# restart the api service in the container to reflect the change
[user@myhost tessia]$ docker exec tessia_server_1 supervisorctl restart tessia-api
tessia-api: stopped
tessia-api: started

# confirm that the service is really running
[user@myhost tessia]$ docker exec tessia_server_1 supervisorctl status
tessia-api                        RUNNING   pid 74, uptime 0:00:05
tessia-scheduler                  RUNNING   pid 27, uptime 0:11:10

# you can also open a shell to the container and type your commands there
# WARNING: if you have multiple shells opened be extra careful not to mistake the container
# shell by a host shell and type destructive commands on your own system ;)
[user@myhost tessia]$ docker exec -ti tessia_server_1 /bin/bash
root@myhost:/# supervisorctl status
tessia-api                        RUNNING   pid 74, uptime 0:01:45
tessia-scheduler                  RUNNING   pid 27, uptime 0:12:50
root@myhost:/# exit
exit
[user@myhost tessia]$
```

You can also open a shell to the `admin` user in the cli container and use the command line client from there:

```
# the cli container has a pre-configured user called 'admin' ready for usage:
[user@myhost tessia]$ docker exec -u admin -ti tessia_cli_1 /bin/bash
admin@tessia-cli:/$ tess conf show

Authentication key in use : bf4efb5a469e491ca47be21efa940875
Key owner login           : admin
Client API version        : 20160916
Server address            : https://myhost:5000
Server API version        : 20160916

admin@tessia-cli:/$ 
```

When you are done you can use docker's own command `docker-compose stop` to stop all containers. If you want to cleanup everything (images, containers, volumes, networks) after
the services were stopped, type `tools/ci/orc cleanup`.

## Complete dev environment with remote docker host

In case you prefer to have a Docker environment on a remote host, it is possible to do so with some more configuration.

Enable remote connections on docker host by adding a `tcp://` port in docker service unit `/lib/systemd/system/docker.service`
```ini
[Service]
...
ExecStart=/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock -H tcp://dockerhost:2375
```

On your local machine export a DOCKER_HOST environment variable:
```
echo export DOCKER_HOST=tcp://dockerhost:2375 >> .bashrc
```

*Note*: this opens an unsecured docker service. To achieve additional protection with client/server certificates please follow [Docker documentation](https://docs.docker.com/engine/security/https/).

If necessary, add docker host user ('tessia' in the example below) to the docker group:
```
sudo usermod -aG docker tessia
```

Tessia build process requires source to be available, so it has to be remote mounted or rsync-ed to docker host. You can use the following script to continuously sync changes from project directory. In this example, local tessia source is at `C:\Projects\tessia\tessia` and is mounted into WSL under `/c/Projects/tessia/tessia`:
```bash
while inotifywait -r -e modify,create,delete /c/Projects/tessia/tessia; do 
   rsync -rltvz /c/Projects/tessia/tessia tessia@dockerhost:/c/Projects/tessia/
   date +'Last updated: %F %R'
done
```

`tools/ci/orc` provides an additional flag, `--builder`, where you can specify dockerhost. With this flag you can continue as in the [previous step](#complete-dev-environment-with-remote-docker), e.g.:

 ```
$ tools/ci/orc run --devmode --tag 18.06.post221.dev0-commitg3df6a1c7.dirty --builder dockerhost
INFO: [init] tag for images is 18.06.post221.dev0-commitg3df6a1c7.dirty
...
     Name                    Command              State                     Ports                   
----------------------------------------------------------------------------------------------------
tessia_cli_1      /entrypoint                     Up                                                
tessia_db_1       docker-entrypoint.sh postgres   Up      5432/tcp                                  
tessia_server_1   /entrypoint                     Up      0.0.0.0:5000->5000/tcp, 0.0.0.0:80->80/tcp
INFO: done
 ```


## Server-side dev environment via virtualenv (deprecated)

You are going to need a postgres database, see the [Database Installation](../users/server_install.md#database-installation) section for instructions.

Steps for the virtualenv installation and tool setup:

```
# install tox (virtualenv manager)
[user@host ~]$ sudo pip3 install -U tox

# hint: if you don't want to install tox as root in your environment, you can install it locally
# with pip3 install --user -U tox

# clone the repository
[user@host ~]$ git clone https://gitlab.com/tessia-project/tessia.git

# enter the repo dir and create the virtualenv
[user@host ~]$ cd tessia && tox -e devenv

# activate your virtualenv
[user@host tessia]$ source .tox/devenv/bin/activate

# edit the server config file to point to your development database
(devenv) [user@host tessia]$ sed -i 's,^  url:.*$,  url: postgresql://tessia:pass4tessia@/tessia,g' .tox/devenv/etc/tessia/server.yaml

# make sure your database is clean
(devenv) [user@host tessia]$ tess-dbmanage reset

# initialize the database (this will also create the basic types needed by the application)
(devenv) [user@host tessia]$ tess-dbmanage init

# the next step is optional (not needed and takes a lot of time): if you want to populate your
# database with some random data you can follow the two commands below

# 1- generate some random entries with the helper script:
(devenv) [user@host tessia]$ tools/db/gen_random_data.py > /tmp/data.json
# 2- then feed the database with the generated file:
(devenv) [user@host tessia]$ tess-dbmanage feed /tmp/data.json

# replace the default ldap based authentication by the 'free' authenticator which allows any
# password, convenient for development purposes
sed -i 's,^  login_method:.*$,  login_method: free,g' .tox/devenv/etc/tessia/server.yaml

# if you don't want to use the free authenticator, the initial token of the admin user
# can be retrieved and stored in your local client file. With that you have the initial access
# to start creating users, resources, etc.:
(devenv) [user@host tessia]$ test -d ~/.tessia-cli || mkdir ~/.tessia-cli
(devenv) [user@host tessia]$ tess-dbmanage get-token > ~/.tessia-cli/auth.key

# to manage the two daemon services (api and scheduler) use the helper tools/control_daemons
# to see the status of the daemons:
(devenv) [user@host tessia]$ tools/control_daemons status
uwsgi: dead
tessia-scheduler: dead

# in order to start the daemons your local user must have sudo passwordless permission, as 
# the uwsgi service runs on the privileged http port 80.
# this is how you execute it:
(devenv) [user@host tessia]$ tools/control_daemons start
uwsgi: running (pid 11189)
tessia-scheduler: running (pid 11187)

```

Due to the fact that the library dependencies are different between server-side are client-side, you'll need a virtualenv for the cli as well. See the next section to learn how to do it.

## Client-side dev environment via virtualenv (deprecated)

The process is pretty straightforward, use tox to create a virtualenv and then activate it:

```
# enter the repo dir and create the virtualenv
# WARNING: remember to deactivate your server-side virtualenv first with 'deactivate'
[user@host ~]$ cd tessia/cli && tox -e devenv

# activate your client virtualenv
[user@host cli]$ source .tox/devenv/bin/activate

(devenv) [user@host cli]$
```
