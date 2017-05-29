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
# How to get a server-side dev environment

In order to get an environment where you can run the API and scheduler services you'll need a database and a python virtualenv.

## Database installation

The database installation commands should be executed as the root user.

### Fedora
```console
# install postgres server
[root@host ~]# dnf install postgresql-server

# initialize db and start service
[root@host ~]# postgresql-setup --initdb

# allow user to connect
[root@host ~]# sed -i '1 s,\(^.*$\),local\tall\tengine\tmd5\n\1,' /var/lib/pgsql/data/pg_hba.conf

# start/restart the service
[root@host ~]# systemctl restart postgresql

# create a user, a database and appropriate permissions
[root@host ~]# runuser -u postgres -- createuser engine
[root@host ~]# runuser -u postgres -- createdb -E UTF8 --lc-collate=en_US.utf8 --lc-ctype=en_US.utf8 engine
[root@host ~]# runuser -u postgres -- psql engine -c 'ALTER DATABASE engine OWNER TO engine'
[root@host ~]# runuser -u postgres -- psql engine -c "ALTER ROLE engine WITH PASSWORD 'pass4engine';"

```
### RHEL 7
```console
# install postgres server
[root@host ~]# yum install postgresql-server

# initialize db and start service
[root@host ~]# postgresql-setup initd

# allow user to connect
[root@host ~]# sed -i '1 s,\(^.*$\),local\tall\tengine\tmd5\n\1,' /var/lib/pgsql/data/pg_hba.conf

# start/restart the service
[root@host ~]# systemctl restart postgresql

# create a user, a database and appropriate permissions
[root@host ~]# runuser -u postgres -- createuser engine
[root@host ~]# runuser -u postgres -- createdb engine
[root@host ~]# runuser -u postgres -- psql engine -c 'ALTER DATABASE engine OWNER TO engine'
[root@host ~]# runuser -u postgres -- psql engine -c "ALTER ROLE engine WITH PASSWORD 'pass4engine';"
```

### Ubuntu 16
```console
# install postgres server
[root@host ~]# apt-get install postgresql

# allow user to connect
[root@host ~]# sed -i '1 s,\(^.*$\),local\tall\tengine\tmd5\n\1,' /etc/postgresql/9.5/main/pg_hba.conf

# start/restart the service
[root@host ~]# systemctl restart postgresql

# create a user, a database and appropriate permissions
[root@host ~]# runuser -u postgres -- createuser engine
[root@host ~]# runuser -u postgres -- createdb engine
[root@host ~]# runuser -u postgres -- psql engine -c 'ALTER DATABASE engine OWNER TO engine'
[root@host ~]# runuser -u postgres -- psql engine -c "ALTER ROLE engine WITH PASSWORD 'pass4engine';"
```

## Virtualenv installation

```console
# install tox (virtualenv manager)
[user@host ~]$ sudo pip3 install -U tox

# hint: if you don't want to install tox as root in your environment, you can install it locally
# with pip3 install --user -U tox

# clone the repository
[user@host ~]$ git clone git@gitlab.com:tessia/tessia-engine.git

# enter the repo dir and create the virtualenv
[user@host ~]$ cd tessia-engine && tox -e devenv

# activate your virtualenv
[user@host tessia-engine]$ source .tox/devenv/bin/activate

# edit the engine config file to point to your development database
(devenv) [user@host tessia-engine]$ sed -i 's,^  url:.*$,  url: postgresql://engine:pass4engine@/engine,g' .tox/devenv/etc/tessia/engine.yaml

# make sure your database is clean
(devenv) [user@host tessia-engine]$ tessia-dbmanage reset

# initialize the database (this will also create the basic types needed by the application)
(devenv) [user@host tessia-engine]$ tessia-dbmanage init

# the next step is optional (not needed and takes a lot of time): if you want to populate your
# database with some random data you can follow the two commands below

# 1- generate some random entries with the helper script:
(devenv) [user@host tessia-engine]$ tools/db/gen_random_data.py > /tmp/data.json
# 2- then feed the database with the generated file:
(devenv) [user@host tessia-engine]$ tessia-dbmanage feed /tmp/data.json

# replace the default ldap based authentication by the 'free' authenticator which allows any
# password, convenient for development purposes
sed -i 's,^  login_method:.*$,  login_method: free,g' .tox/devenv/etc/tessia/engine.yaml

# if you don't want to use the free authenticator, the initial token of the admin user
# can be retrieved and stored in your local client file. With that you have the initial access
# to start creating users, resources, etc.:
(devenv) [user@host tessia-engine]$ test -d ~/.tessia-cli || mkdir ~/.tessia-cli
(devenv) [user@host tessia-engine]$ tessia-dbmanage get-token > ~/.tessia-cli/auth.key

# to manage the two daemon services (api and scheduler) use the helper tools/control_daemons
# to see the status of the daemons:
(devenv) [user@host tessia-engine]$ tools/control_daemons status
tessia-api: dead
tessia-scheduler: dead

# and to start them
(devenv) [user@host tessia-engine]$ tools/control_daemons start
tessia-api: running (pid 11189)
tessia-scheduler: running (pid 11187)

```
