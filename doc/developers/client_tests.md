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
# Integration tests / cmdline client tests

## Rationale

Testing of the command line client is done via integration tests. We decided at the moment not to create unit tests (i.e. using mocks) like we do for the server side for the following reasons:

- we would still need to create integration tests to verify if all pieces are fitting together
- we are constrainted in team resources to create both type of tests (unit tests and integration tests)
- the client is the natural entry point for integration tests as it allows the whole solution to be tested
- by creating integration tests we are testing the whole solution while focusing on real use cases and covering testing of each unit by checking the code coverage level

The integration tests cover all the components of the solution running together. That means you need the API and scheduler services running to be able to execute them.
See in the next section how to do that.

## How to run tests

A server-side development environment is necessary to run the integration/client tests.
For instructions on how to get it up and running, check [How to get a server-side dev environment](dev_env.md).

Due to the fact that the library dependencies are different between server-side are  client-side, you'll need a virtualenv for the cli as well. Use tox to create one and then activate it:

```console
# enter the repo dir and create the virtualenv
[user@host ~]$ cd tessia-engine/cli && tox -e devenv

# activate your client virtualenv
[user@host cli]$ source .tox/devenv/bin/activate

(devenv) [user@host cli]$
```

Now we have all the setup done and we are ready to execute some tests. Have a look at the test runner utility `tests/run`.
Its usage is pretty straightforward, here's an example of how to list the available tests and run them:

```console
(devenv) [user@host cli]$ tests/run list

     Testcase    |                     Description                      
-----------------+------------------------------------------------------
 systems_actions | Exercise creation and deletion of cpc/lpar/kvm guest 

(devenv) [user@host cli]$ tests/run exec --name=systems_actions --api-url=http://127.0.0.1:5000 --cleaner=../tools/cleanup_fixture
[init] testcases to execute: systems_actions
[pre-start] calling cleaner '/home/user/git/tessia-engine/tools/cleanup_fixture'
tessia-api: running (pid 14244)
tessia-scheduler: running (pid 14242)
[exec] python3 -m coverage run -a --source=../tessia_cli -m tests.wrapper systems_actions http://127.0.0.1:5000
[cmd] conf set-server http://127.0.0.1:5000
[output] Server successfully configured.

[cmd] conf key-gen
[output] Login: system
Password: 
Key successfully created and added to client configuration.

[run] testcase 'systems_actions'
[exec-task] 'base_add'
[cmd] perm project-add --name='GEO_1 labadmins' --desc='GEO_1 lab admins'
[output] Item added successfully.

[cmd] perm user-add --login=lab_admin@example.com --name='ADMIN_LAB' --title='Title of lab admin'
[output] User added successfully.

[cmd] perm role-grant --login=lab_admin@example.com --name='ADMIN_LAB' --project='GEO_1 labadmins'
[output] User role added successfully.

(lots of output ...)

[cleanup] testcase 'systems_actions'
[end] testcase 'systems_actions'
finished testcase 'systems_actions'
Name                                                                             Stmts   Miss  Cover   Missing
--------------------------------------------------------------------------------------------------------------
/home/user/work/git/tessia/tessia-engine/cli/tessia_cli/__init__.py                    0      0   100%
/home/user/work/git/tessia/tessia-engine/cli/tessia_cli/client.py                     31      4    87%   89, 96-100
/home/user/work/git/tessia/tessia-engine/cli/tessia_cli/cmds/__init__.py              67     26    61%   68-104, 126, 138, 151-154
/home/user/work/git/tessia/tessia-engine/cli/tessia_cli/cmds/autotemplate.py          54     20    63%   35, 49-56, 65-69, 87-93, 106-113, 124-130
/home/user/work/git/tessia/tessia-engine/cli/tessia_cli/cmds/conf.py                  78     34    56%   54-59, 80-95, 103-112, 122-160, 177-180, 185

(many lines ...)

--------------------------------------------------------------------------------------------------------------
TOTAL                                                                             1885    758    60%
(devenv) [user@host cli]$
```

Note the use of the `--cleaner` argument, this is the script to be executed between each testcase to clean up the test environment so that
things created by the previous test won't affect the next test.
When running the tests in your dev environment you can use the same cleaner `cleanup_fixture` used in the example above which stops the api and scheduler services,
then uses `tessia-dbmanage` to re-initialize the database and finally starts the services again.

## How to create tests

The testcases are located in the folder `tests/static_testcases`. Since the nature of the client tests mostly consists of execution of commands and parsing/validation
of the output we simplified the testcase creation by enabling the usage of yaml files. These files contain a list of commands and their corresponding expected
output. Here's an example of a basic test in such format with detailed explanations:

```yaml
# description of what the testcase does
description: This is an example testcase for education purposes
# the initial user to be set in client configuration, should be set to a user
# that exists in the initial database state
base_user: system
# a list with the order of the tasks to be executed, it's possible to reuse a
# task by specifying it more than once in the list
tasks_order:
  - base_conf
  - lpar_add
  - lpar_del
# section containing each of the tasks
tasks:
  # this is a task entry, it contains lists of statements. A statement can be a single
  # command string or it can specify multiple inputs and output expected, see below
  base_conf:
    # a simple command string, asks to show current configuration and does not validate
    # the output
    - conf show
    # these entries specify a command and an expected output (regexes are supported)
    - - perm project-add --name='GEO_1 labadmins' --desc='GEO_1 lab admins'
      - Item added successfully.
    - - perm user-add --login=lab_admin@example.com --name='ADMIN_LAB' --title='Title of lab admin'
      - User added successfully.
    - - perm role-grant --login=lab_admin@example.com --name='ADMIN_LAB' --project='GEO_1 labadmins'
      - User role added successfully.
    # an entry with multiple inputs, useful for when the client prompts for information (i.e.
    # when it's necessary to enter username and password)
    - - - conf key-gen
        - lab_admin@example.com
        - password
      - Key successfully created and added to client configuration.
  # another task, purpose is to create a lpar
  lpar_add:
    - - system add --name=cpc3 --type=cpc --hostname=hmcserver.example.com --model=zec12_h43 --project='GEO_1 labadmins' --desc='2 Books and 43 processors'
      - Item added successfully.
    - - system add --name=cpc3lp52 --hyp=cpc3 --type=LPAR --hostname=cpc3lp52.example.com --desc='Example lpar'
      - Item added successfully.
  # last task, delete the created lpar
  lpar_del:
    - - system del --name=cpc3lp52
      - Item successfully deleted.
    - - system del --name=cpc3
      - Item successfully deleted.
```

**Note**: when you create your yaml files, make sure to follow the convention and use an indentation of 2 spaces like the example above.
