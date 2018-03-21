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
# Server installation

The easiest and recommended way to get a server running is by using docker containers.
In the source repository there's a deploy tool available named `orc` (for orchestrator) to automatically build the images and deploy the containers for you.

It's also possible to install and deploy manually without docker, although this method involves more steps.
Both methods are described in the following sections.

# Docker method

You will need docker 1.12.0+ and docker-compose 1.9.0+ installed on your system.

```
# install pip for python3
$ apt-get install python3-pip

# clone repo and install the deploy tool requirements
$ git clone https://gitlab.com/tessia-project/tessia.git
$ cd tessia && pip3 install -r tools/ci/requirements.txt
```

Now use the deploy tool `orc` to build the images and deploy the service.

```
# build the docker images
$ tools/ci/orc build

# start the containers (it's done via docker-compose)
$ tools/ci/orc run

# see the 3 containers running - server, database, and client
$ docker-compose ps

# use the admin user available in the client container to test the service:
$ docker exec -ti --user admin tessia_cli_1 tess conf show
```

The server container runs the API and job scheduler while the client contains the command line client.

From this point you can manage the service with the usual `docker-compose` commands. If you want to manage it from a different folder, simply copy the generated files
`.env` and `.docker-compose.yaml` to the desired folder.

**IMPORTANT**: In order to be able to install LPARs, one more step is needed.
Refer to the section [Deployment of the auxiliar live-image](#deployment-of-the-auxiliar-live-image) for details.

The `admin` user in the client container is the entry point for creating additional users, resources, etc. Note that you need to adjust the server authentication
configuration before newly created users are able to login. See the [Server Configuration](server_conf.md) page to learn how to set proper authentication and other
configuration details.

The tool is ready for use. To learn how to install your first system, visit [Getting started](getting_started.md).

If you have special requirements and want to handle the docker build/run process yourself, have a look at the folder `tools/ci/docker`. There you can find:

- folder `tessia-cli`: contains the Dockerfile and assets to build an environment for the command line client.
- folder `tessia-server`: contains the Dockerfile and assets to build a server environment (REST-like API and job scheduler).
- file `docker-compose.yaml`: can be used to orchestrate the services via `docker-compose`.

Consider using these files directly if you want to make customizations, otherwise we recommend to use the above method which does all the heavy lifting for you.

# Manual method

The first step is to have a postgres database available, see the next section how to quickly get one.

## Database installation

### Fedora

```
# install postgres server
[root@host ~]# dnf install postgresql-server

# initialize db and start service
[root@host ~]# postgresql-setup --initdb

# allow user to connect
[root@host ~]# sed -i '1 s,\(^.*$\),local\tall\ttessia\tmd5\n\1,' /var/lib/pgsql/data/pg_hba.conf

# start/restart the service
[root@host ~]# systemctl restart postgresql

# create a user, a database and appropriate permissions
[root@host ~]# runuser -u postgres -- createuser tessia
[root@host ~]# runuser -u postgres -- createdb -E UTF8 --lc-collate=en_US.utf8 --lc-ctype=en_US.utf8 tessia
[root@host ~]# runuser -u postgres -- psql tessia -c 'ALTER DATABASE tessia OWNER TO tessia'
[root@host ~]# runuser -u postgres -- psql tessia -c "ALTER ROLE tessia WITH PASSWORD 'pass4tessia';"

```
### RHEL 7

```
# install postgres server
[root@host ~]# yum install postgresql-server

# initialize db and start service
[root@host ~]# postgresql-setup initd

# allow user to connect
[root@host ~]# sed -i '1 s,\(^.*$\),local\tall\ttessia\tmd5\n\1,' /var/lib/pgsql/data/pg_hba.conf

# start/restart the service
[root@host ~]# systemctl restart postgresql

# create a user, a database and appropriate permissions
[root@host ~]# runuser -u postgres -- createuser tessia
[root@host ~]# runuser -u postgres -- createdb tessia
[root@host ~]# runuser -u postgres -- psql tessia -c 'ALTER DATABASE tessia OWNER TO tessia'
[root@host ~]# runuser -u postgres -- psql tessia -c "ALTER ROLE tessia WITH PASSWORD 'pass4tessia';"
```

### Ubuntu 16.04

```
# install postgres server
[root@host ~]# apt-get install postgresql

# allow user to connect
[root@host ~]# sed -i '1 s,\(^.*$\),local\tall\ttessia\tmd5\n\1,' /etc/postgresql/9.5/main/pg_hba.conf

# start/restart the service
[root@host ~]# systemctl restart postgresql

# create a user, a database and appropriate permissions
[root@host ~]# runuser -u postgres -- createuser tessia
[root@host ~]# runuser -u postgres -- createdb tessia
[root@host ~]# runuser -u postgres -- psql tessia -c 'ALTER DATABASE tessia OWNER TO tessia'
[root@host ~]# runuser -u postgres -- psql tessia -c "ALTER ROLE tessia WITH PASSWORD 'pass4tessia';"
```

## Tool installation

Once the database is available, it's time to install the tool itself.

The following instructions are known to work on Ubuntu 16.04, you might need to adjust for different distributions.

Begin by installing the necessary dependencies:

```
$ apt-get install --no-install-recommends \
    iputils-ping \
    python3-pip \
    git \
    build-essential \
    libssl-dev \
    libffi-dev python3-dev \
    libpq-dev \
    libpq5 \
    s3270
$ pip3 install -U pip==9.0.1 setuptools
```

Install the application files:

```
# create a user to run the application
$ useradd -m tessia && su - tessia

# clone the repo and install
$ git clone https://gitlab.com/tessia-project/tessia.git
$ cd tessia && pip3 install --user -U -r requirements.txt .

# we are going to use uwsgi as our web server
$ pip3 install --user -U uwsgi

# create the necessary folders and configuration files,
# in this tutorial we are going to place the files in the user's home folder
# but you are free to place it anywhere.
$ install -m 700 -d $HOME/etc && install -m 600 etc/* $HOME/etc
$ export TESSIA_CFG=$HOME/etc/server.yaml
$ echo "export TESSIA_CFG=$HOME/etc/server.yaml" >> $HOME/.profile

# folder for jobs' output, autofiles created by install machine, and logs
$ install -m 750 -d $HOME/var $HOME/var/jobs $HOME/var/www $HOME/var/log
```

## Configuration

For easier manipulation of yaml files we are going to use in this tutorial the helper command `yamlman`
available in the source repository:

```
$ test -d $HOME/bin || mkdir $HOME/bin
$ cp tools/ci/docker/tessia-server/assets/yamlman $HOME/bin
```

Note that using this helper is optional, you can edit the files directly with any text editor. Configuration settings:

```
# URL provided to the distros' installers to locate the autofile (kickstart, etc.) during
# installation time, if hostname is not reachable an ip address can be used instead.
$ yamlman update $HOME/etc/server.yaml auto_install.url http://$HOSTNAME/static

# folder where the generated autofiles (kickstart, etc.) will be served
$ yamlman update $HOME/etc/server.yaml auto_install.dir $HOME/var/www
$ yamlman update $HOME/etc/uwsgi.yaml uwsgi.static-map /static=$HOME/var/www

# env variable with location of config file
$ yamlman update $HOME/etc/uwsgi.yaml uwsgi.env TESSIA_CFG=$HOME/etc/server.yaml

# folder containing the output of jobs
$ yamlman update $HOME/etc/server.yaml scheduler.jobs_dir $HOME/var/jobs

# log files
$ yamlman update $HOME/etc/server.yaml log.handlers.file_api.filename $HOME/var/log/api.log
$ yamlman update $HOME/etc/server.yaml log.handlers.file_common.filename $HOME/var/log/common.log

# database location and credentials in sqlalchemy format
$ yamlman update $HOME/etc/server.yaml db.url "postgresql://tessia:pass4tessia@/tessia"
```

It's recommended to enable SSL for the REST-like API, if you don't have a certificate you can quickly
generate a self-signed one with:

```
$ export SSL_CONFIG="
[req]
prompt=no
distinguished_name=req_dn
[req_dn]
CN=$HOSTNAME
OU=TESSIA
[v3_ca]
subjectAltName=DNS:$HOSTNAME
"
$ openssl req -new -nodes -x509 -newkey rsa:4098 -keyout $HOME/etc/ssl.key -out $HOME/etc/ssl.crt -days 3650 -reqexts v3_ca -extensions v3_ca -config <(printf "$SSL_CONFIG")
$ unset SSL_CONFIG

# set appropriate permissions
$ chmod 600 $HOME/etc/ssl.crt $HOME/etc/ssl.key

# point the web server to the certificate and its key files
$ yamlman update $HOME/etc/uwsgi.yaml uwsgi.https 0.0.0.0:5000,$HOME/etc/ssl.crt,$HOME/etc/ssl.key
```

You also need to configure the authentication mechanism before starting the service, this is very dependent on
how your environment looks like. See the [section auth](server_conf.md#section-auth) of the [Server Configuration](server_conf.md) page for details.

The database must be initialized, do so with:

```
# assures db is clean and initializes it (create the basic entries needed by the application)
$ tess-dbmanage reset -y && tess-dbmanage init
```

At this point we are ready to start the services. In this tutorial we use supervisord to manage
the uwsgi and scheduler services but you can also use systemd by creating yourself the service files.

```
# run commands as the root user
$ apt-get install supervisor
$ cat > /etc/supervisor/conf.d/tessia.conf <<EOF
[supervisord]
nodaemon=true
logfile_maxbytes=20MB
logfile_backups=3

[program:tessia-api]
command=/bin/bash -l -c "exec uwsgi --yaml /home/tessia/etc/uwsgi.yaml"
redirect_stderr=true
stdout_logfile=/home/tessia/var/log/uwsgi.log
stdout_logfile_maxbytes=20MB
stdout_logfile_backups=3
environment=HOME="/home/tessia",USER="tessia"

[program:tessia-scheduler]
command=/bin/bash -l -c "exec tess-scheduler"
redirect_stderr=true
stdout_logfile=/home/tessia/var/log/scheduler.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=3
user=tessia
environment=HOME="/home/tessia",USER="tessia"
EOF

$ supervisorctl update
$ sleep 2; supervisorctl status
```

The last command should report that both services are running.

In order to have initial access to the application you need to install the command line client and use the admin user's
authentication token which was generated during database initialization time.
Follow the [Client installation with pip](client_install.md#local-installation-with-pip) instructions but skip the step to generate an authentication token.
We are going to retrieve it from the server-side and inject it into the local tessia user's client configuration, as below:

```
$ su - tessia
$ test -d $HOME/.tessia-cli/auth.key || install -m 700 -d $HOME/.tessia-cli
$ tess-dbmanage get-token > $HOME/.tessia-cli/auth.key

# set safe permissions for the token file
$ chmod 600 $HOME/.tessia-cli/auth.key

# If you haven't done so yet, set the server's SSL trusted certificate and url in the client config
$ openssl s_client -showcerts -connect $HOSTNAME:5000 < /dev/null 2>/dev/null | sed -ne "/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p" > $HOME/.tessia-cli/ca.crt
$ tess conf set-server https://$HOSTNAME:5000

# verify that everything works
$ tess conf show
```

If the last command reported server information, the service is correctly running and the token was successfully configured.
Make sure to keep the token secure as it provides admin access to the application.

**IMPORTANT**: In order to be able to install LPARs, one more step is needed.
Refer to the section [Deployment of the auxiliar live-image](#deployment-of-the-auxiliar-live-image) for details.

The tool is now ready for use. To learn how to install your first system, visit [Getting started](getting_started.md).

# Deployment of the auxiliar live-image

The HMC in classic mode does not expose a method in its API to perform network boot of the LPARs.
For this reason, tessia makes use of an auxiliar live-image installed on a pre-allocated disk in order to enable this functionality.
Perform these steps to deploy the live-image:

- Follow the instructions at [Live image to enable HMC netboot](https://gitlab.com/tessia-project/tessia-baselib/blob/master/doc/users/live_image.md)
- Enter the image's root password in the server's configuration file as explained in [Section auto_install](server_conf.md#section-auto_install).
- Keep note of the disk used as you will associate it to the CPC in the tool configuration later as explained [here](getting_started.md#hypervisor-cpc).
