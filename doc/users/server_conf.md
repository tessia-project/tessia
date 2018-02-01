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
# Server configuration

The server configuration is done through the yaml files `/etc/tessia/server.yaml` and `/etc/tessia/uwsgi.yaml`.
Below you can find detailed explanation of each file and their parameters.

# File server.yaml

This file is read by the REST-like API and the job scheduler services.

## Section `auth`

Configures the users' authentication subsystem.

`allow_user_auto_create`

- Type: boolean
- Default: false
- Description: whether to allow users to be automatically added to server's database when the login subsystem authenticates them.
If `true`, new users will be able to login but they still need to be assigned a role on a project. If `false`, new users can only
login after an admin user has registered them in the database.

`realm`

- Type: string
- Default: auth-realm
- Description: name of authentication realm to present in the header of http 401 authentication required responses

`login_method`

- Type: enum (ldap, free)
- Default: (must be specified)
- Description: which method to use for authenticating users. If `ldap`, a LDAP server is used according to the configuration defined in the
sub-section `auth.ldap`. If `free`, users can login with any password (useful for development/testing purposes).

### Section `auth.ldap`

Defines the configuration of the LDAP service for user authentication when `ldap` was set for the `login_method` parameter.

`host`

- Type: string
- Default: (must be specified)
- Description: hostname of the LDAP server.

`port`

- Type: string
- Default: 636
- Description: port where LDAP is running.

`ssl`

- Type: boolean
- Default: true
- Description: whether to use ssl for LDAP connection.

`username`

- Type: string
- Default: (none)
- Description: if you need an username to connect to the LDAP server, specify it here. Otherwise an anonymous connection will be attempted.

`password`

- Type: string
- Default: (none)
- Description: password for connection with the LDAP server when `username` was specified.
  
  
`timeout`

- Type: integer
- Default: 10
- Description: time to wait for LDAP operations to complete.
  

`user_base`

- Type: string
- Default: (must be specified)
- Description: the base used to perform user searches in the LDAP directory.

`user_filter`

- Type: string
- Default: (none)
- Description: LDAP filter to be added to the search string, example: `(objectclass=inetOrgPerson)`

`group_filter`

- Type: string
- Default: (none)
- Description: the filter used to perform group searches in the LDAP directory, example: `(&(cn=tessia-users)(objectclass=groupOfUniqueNames))`.
Skip it if you don't want to enable group based access.

`group_base`

- Type: string
- Default: (none, must be specified if `group_filter` was specified)
- Description: the base used to perform group searches in the LDAP directory.

`group_membership_attr`

- Type: string
- Default:
- Description: which attribute in the group entry is used to list its members. For example, if you enter `uniquemember` the tool will perform a LDAP search
for `uniquemember={user_dn}` (after having determined the user's DN).

#### Section `auth.ldap.user_attributes`

Defines the mapping between the attributes expected by the tool and their names in the LDAP directory.

`fullname`

- Type: string
- Default: cn
- Description: which attribute in the user's entry contains the full name.

`login`

- Type: string
- Default: mail
- Description: which attribute in the user's entry contains the login string. This attribute corresponds to what the user specifies when entering their username/password.

`title`

- Type: string
- Default: (none)
- Description: which attribute in the user's entry contains their job title, skip it if your LDAP does not provide this information.

## Section `auto_install`

Configuration of the autoinstall execution machine

`dir`

- Type: string
- Default: (must be specified)
- Description: directory path on the filesystem where the machine can place the autofiles (kickstart, autoinst, etc.) generated from the templates during installation time.
The path set here should be reflected in the `uwsgi.yaml` configuration so that the files can be served in the network to the target systems being installed.

`live_img_passwd`

- Type: string
- Default: (must be specified)
- Description: root password of the auxiliar live image used to netboot LPARs

`url`

- Type: string
- Default: (must be specified)
- Description: the URL configured in `uwsgi.yaml` to serve static content. This URL is passed by the machine to the distro installers so that they know from where to fetch
the autofile for the installation.

## Section `log`

Defines how logging should behave (whether to log to console or file, which log files to use, log rotation, etc.). This section follows the format defined by the python
`logging` module and passes the content of this section directly to the python method `logging.config.dictConfig`, which means you can refer to the official python
[documentation](https://docs.python.org/3/library/logging.config.html#logging-config-dictschema) to learn how to configure this section.

## Section `scheduler`

Defines parameters for the job scheduler daemon.

`jobs_dir`

- Type: string
- Default: (must be specified)
- Description: directory path on the filesystem where the output of the jobs will be saved.

# File uwsgi.yaml

This is a standard uwsgi file, see the uwsgi [documentation](http://uwsgi-docs.readthedocs.io/en/latest/Configuration.html) for details on how to configure it.
Two things about this file are worth mentioning:

- the application entry point for the API service is `tessia.server.api.cmd:APP`
- the serving of static files should match the directory defined in the section `auto_install.dir` of the `server.yaml` file.
