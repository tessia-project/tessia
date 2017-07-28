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
# Ansible machine

This pages describes how to use the ansible based machine for automatic task execution. Ansible is a well known open source tool to automate IT infrastructure management.
If you are unfamiliar with it, we recommend to read their [documentation](http://docs.ansible.com/ansible/latest/index.html).

In a nutshell, what this machine does is integrate the systems managed by tessia with ansible playbooks by means of an [inventory file](http://docs.ansible.com/ansible/latest/intro_inventory.html)
 (see detailed explanation below).

Example of use cases where the use of this machine can be useful:

- Configuration management: software installation and configuration automated by an ansible repository
- Testcase execution: testers can create their ATCs (automated testcases) by using ansible playbooks, thus benefiting from its huge [module library](http://docs.ansible.com/ansible/latest/list_of_all_modules.html)
- Performance measurement: playbooks can be used to automatically deploy certain workloads for subsequent performance measurement.

# How it works

Here's a step by step description of how the machine works:

- User submits a job providing the necessary parameters, as the following example:
```yaml
# the source could also be http:// or tarball files (i.e. url ending with .tgz)
source: git://myhost.example.com/atc_do_something.git

# this is the ansible playbook to execute, it has to be present in the repository
playbook: memory_stress.yaml

# a mapping between tessia systems and the ansible groups they belong to
systems:
  # system name in tessia
  - name: lpar15
    # optional activation profile, if not specified default is used
    profile: smt_active
    # ansible groups, the names must match those on the playbook
    groups:
      - superbench-servers
      - postgres-servers
  # multiple systems can be used
  - name: kvm50
    groups:
      - superbench-workers
```
- Job is started by the scheduler: a new process is spawned and the machine execution starts
- Machine downloads the ansible repository from the specified source url
- The machine dynamically creates an inventory file in the downloaded repository folder. For the parameter file above, the inventory file would look like this:
```
[superbench-servers]
lpar15 ansible_host=lpar15.domain.com ansible_user=username ansible_ssh_pass=mypass

[postgres-servers]
lpar15 ansible_host=lpar15.domain.com ansible_user=username ansible_ssh_pass=mypass

[superbench-workers]
kvm50 ansible_host=kvm50.domain.com ansible_user=someuser ansible_ssh_pass=somepass
```
- The machine activates the involved systems, if not activated yet.
- The machine runs the ansible-playbook executable for the given playbook and inventory files.
- The job finishes once ansible finishes its execution.

# How to use it

In this section we will see how to deploy a LAMP stack easily by using one of the example playbooks available in the ansible community [here](https://github.com/ansible/ansible-examples).

Assuming we have a system named 'lpar15' previously installed with RHEL7, we then create a parameter file called `lamp.yaml` with the following content:
```yaml
source: https://github.com/ansible/ansible-examples.git
playbook: lamp_simple_rhel7/site.yml
systems:
  - name: cpc3lp52
    groups:
      - webservers
      - dbservers
```

In this example we are going to run the web server and database server on the same system, but it's possible to deploy each server on a separate system by assigning them to the
groups accordingly.

With our parameter file ready, we submit the job:

```
user@tessia-cli:~/$ tessia job submit --type=ansible --parmfile=lamp.yaml

Request #2 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #2
```

Let's see the output of it:
```
user@tessia-cli:~/$ tessia job output --id=2
2017-07-28 12:44:06,338|INFO|machine.py(569)|new stage: download-source
2017-07-28 12:44:06,339|INFO|machine.py(229)|cloning git repo from https://github.com/ansible/ansible-examples.git
2017-07-28 12:44:18,790|INFO|machine.py(471)|validating repository content
2017-07-28 12:44:18,790|INFO|machine.py(572)|new stage: create-inventory
2017-07-28 12:44:18,790|INFO|machine.py(389)|creating inventory file
2017-07-28 12:44:18,809|INFO|machine.py(575)|new stage: activate-systems
2017-07-28 12:44:18,810|INFO|machine.py(378)|no systems tagged for installation
2017-07-28 12:44:18,810|INFO|machine.py(382)|system lpar15 activated
2017-07-28 12:44:18,810|INFO|machine.py(578)|new stage: execute-playbook
2017-07-28 12:44:18,810|INFO|machine.py(490)|executing: 'ansible-playbook -i tessia-hosts lamp_simple_rhel7/site.yml'

PLAY [apply common configuration to all nodes] *********************************

TASK [Gathering Facts] *********************************************************
TASK [Gathering Facts] *********************************************************
ok: [lpar15]

TASK [common : Install ntp] ****************************************************
changed: [lpar15]

TASK [common : Install common dependencies] ************************************
changed: [lpar15] => (item=['libselinux-python', 'libsemanage-python', 'firewalld'])

TASK [common : Configure ntp file] *********************************************

(suppressed output...)

TASK [db : Install MariaDB package] ********************************************
changed: [lpar15] => (item=['mariadb-server', 'MySQL-python'])

TASK [db : Configure SELinux to start mysql on any port] ***********************
changed: [lpar15]

TASK [db : Create Mysql configuration file] ************************************
changed: [lpar15]

TASK [db : Create MariaDB log file] ********************************************
changed: [lpar15]

TASK [db : Create MariaDB PID directory] ***************************************
changed: [lpar15]

TASK [db : Start MariaDB Service] **********************************************
changed: [lpar15]

TASK [db : Start firewalld] ****************************************************
ok: [lpar15]

TASK [db : insert firewalld rule] **********************************************
changed: [lpar15]

TASK [db : Create Application Database] ****************************************
changed: [lpar15]

TASK [db : Create Application DB User] *****************************************
changed: [lpar15]

RUNNING HANDLER [db : restart mariadb] *****************************************
changed: [lpar15]

PLAY RECAP *********************************************************************
lpar15                   : ok=27   changed=23   unreachable=0    failed=0   

2017-07-28 12:50:16,018|INFO|machine.py(581)|new stage: cleanup
2017-07-28 12:50:16,040|INFO|machine.py(584)|machine finished successfully
```

Looks good, let's have a look if it really worked:

```
user@tessia-cli:~$ wget -q http://lpar15/index.php -O -
<html>
 <head>
  <title>Ansible Application</title>
 </head>
 <body>
 </br>
  <a href=http://192.168.1.222/index.html>Homepage</a>
 </br>
Hello, World! I am a web server configured using Ansible and I am : lpar15</BR>List of Databases: </BR>information_schema
foodb
mysql
performance_schema
test
</body>
</html>

```

Works as expected :)
