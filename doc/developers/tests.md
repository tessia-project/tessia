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
# Integration and unit tests

All testing in the project is automated by creating unit tests and integration tests. This page explains how to run and how to develop them.

- [Integration (cmdline client) tests](#integration-cmdline-client-tests)
    - [Rationale](#rationale)
    - [How to run all client tests at once](#how-to-run-all-client-tests-at-once)
    - [How to run client tests individually](#how-to-run-client-tests-manually)
    - [How to create client tests](#how-to-create-client-tests)
- [Unit tests](#unit-tests)
    - [How to run unit tests](#how-to-run-unit-tests)
    - [How to create unit tests](#how-to-create-unit-tests)
- [Linting](#linting)
    - [How to execute the lint validator](#how-to-execute-the-lint-validator)

# Integration (cmdline client) tests

## Rationale

Integration tests are done via the command line client. We decided at the moment not to create unit tests (i.e. using mocks) for the client as we do for the server side
for the following reasons:

- we would still need to create integration tests to verify if all pieces are fitting together
- we are constrainted in team resources to create both type of tests (unit tests and integration tests)
- the client is the natural entry point for integration tests as it allows the whole solution to be tested
- by creating integration tests we are testing the whole solution while focusing on real use cases and covering testing of each unit by checking the code coverage level

The integration tests cover all the components of the solution (API, scheduler, client) running together.

## How to run all client tests at once

Pre-requisite: to go forward with this section, you must have the docker images already built. Learn how in [How to setup a development environment](dev_env.md).

Executing all client tests is pretty straightforward, all you have to do is to use the `orc` tool in development mode while specifiying the `clitests` parameter:

```console
[user@myhost tessia-engine]$ tools/ci/orc devmode --tag=17.713.740 --baselibfile=/home/user/files/tessia_baselib.yaml --clitests
INFO: [init] using builder localhost
$ hostname --fqdn
normandy
INFO: [init] tag for images is 17.713.740
INFO: [devmode] starting services

(output suppressed...)

INFO: [devmode] clitests requested
$ docker exec --user admin tessia_cli_1 bash -c '/home/admin/cli/tests/runner erase && /home/admin/cli/tests/runner list --terse'
systems_actions
INFO: [clitest] starting test systems_actions
$ docker exec --user admin tessia_cli_1 /home/admin/cli/tests/runner exec --cov-erase=no --cov-report=no --api-url=https://myhost:5000 --name=systems_actions
[init] testcases to execute: systems_actions
[init] waiting for API server to come up (30 secs)
[exec] python3 -m coverage run -a --source=tessia_cli -m wrapper /home/admin/cli/tests/static_testcases/systems_actions.yaml https://myhost:5000
[cmd] conf set-server https://myhost:5000
[output] Server successfully configured.

(output suppressed...)

Stopping tessia_db_1 ... done

Stopping tessia_engine_1 ... done

Removing tessia_db_1 ... done

Removing tessia_cli_1 ... doneone
Going to remove tessia_db_1, tessia_cli_1, tessia_engine_1
tessia_db-data
tessia_engine-etc
tessia_engine-jobs
tessia_cli_net
tessia_db_net
INFO: done
[user@myhost tessia-engine]$
```

## How to run client tests individually

Pre-requisite: to go forward with this section, you must have the docker images already built. Learn how in [How to setup a development environment](dev_env.md).

Starts the containers in development mode, open a shell to the tessia-cli container and enter the bind mounted cli directory:

```console
[user@myhost tessia-engine]$ tools/ci/orc devmode --tag=17.713.740-devd40c703 --baselibfile=/home/user/files/tessia_baselib.yaml
INFO: [init] using builder localhost
$ hostname --fqdn
myhost
INFO: [init] tag for images is 17.713.740-devd40c703
INFO: [devmode] starting services

(output suppressed...)

INFO: [devmode] you can now work, press Ctrl+C when done

# in a different shell ...
[user@myhost ~]$ docker exec -u admin -ti tessia_cli_1 /bin/bash
admin@tessia-cli:/$ cd /home/admin/cli
admin@tessia-cli:~/cli$
```

Now have a look at the test runner utility `tests/runner`. Its usage is pretty straightforward, here's an example of how to list the available tests and run them:

```console
admin@tessia-cli:~/cli$ tests/runner list

     Testcase    |                     Description                      
-----------------+------------------------------------------------------
 systems_actions | Exercise creation and deletion of cpc/lpar/kvm guest 

admin@tessia-cli:~/cli$ tests/runner exec --name=systems_actions
[init] testcases to execute: systems_actions
[init] warning: --api-url not specified, defaulting to https://myhost:5000 from config file.
[init] waiting for API server to come up (30 secs)
/usr/local/lib/python3.5/dist-packages/urllib3/connectionpool.py:852: InsecureRequestWarning: Unverified HTTPS request is being made. Adding certificate verification is strongly advised. See:
 https://urllib3.readthedocs.io/en/latest/advanced-usage.html#ssl-warnings
  InsecureRequestWarning)
[exec] python3 -m coverage run -a --source=tessia_cli -m wrapper /home/admin/cli/tests/static_testcases/systems_actions.yaml https://myhost:5000
[cmd] conf set-server https://myhost:5000
[output] Server successfully configured.

[cmd] conf key-gen
[output] Login: admin
Password: 
Key successfully created and added to client configuration.

[run] testcase '/home/admin/cli/tests/static_testcases/systems_actions.yaml'
[exec-task] 'base_add'
[cmd] perm project-add --name='GEO_1 labadmins' --desc='GEO_1 lab admins'
[output] Item added successfully.

[cmd] perm user-add --login=lab_admin@example.com --name='ADMIN_LAB' --title='Title of lab admin'
[output] User added successfully.

[cmd] perm role-grant --login=lab_admin@example.com --name='ADMIN_LAB' --project='GEO_1 labadmins'
[output] User role added successfully.

(lots of output ...)

[cleanup] testcase '/home/admin/cli/tests/static_testcases/systems_actions.yaml'
[end] testcase '/home/admin/cli/tests/static_testcases/systems_actions.yaml'
finished testcase 'systems_actions'
Name                                                                        Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------------------------------------
/usr/local/lib/python3.5/dist-packages/tessia_cli/__init__.py                    0      0   100%
/usr/local/lib/python3.5/dist-packages/tessia_cli/client.py                     34      4    88%   89, 94, 99-100
/usr/local/lib/python3.5/dist-packages/tessia_cli/cmds/__init__.py              75     28    63%   71-107, 122, 125, 137, 149, 162-165
/usr/local/lib/python3.5/dist-packages/tessia_cli/cmds/autotemplate.py          54     20    63%   35, 49-56, 65-69, 87-93, 106-113, 124-130
/usr/local/lib/python3.5/dist-packages/tessia_cli/cmds/conf.py                  89     43    52%   56-61, 82-97, 105-114, 124-162, 179-201, 207
/usr/local/lib/python3.5/dist-packages/tessia_cli/cmds/job/__init__.py           8      1    88%   27
/usr/local/lib/python3.5/dist-packages/tessia_cli/cmds/job/job.py               82     46    44%   57-74, 85-87, 96-131, 149-161, 176-200

(many lines ...)

--------------------------------------------------------------------------------------------------------------
TOTAL                                                                        1965    806    59%
admin@tessia-cli:~/cli$
```

**Note**: after a test is executed, the database will be in a 'dirty' state which might cause a second run or a run of another test to fail. To restore the database
to a pristine state, run the cleaner script from within the tessia-engine container:

```console
# stop the api and scheduler services, call tessia-dbmanage to re-initialize the database, start the services again
[user@myhost ~]$ docker exec -ti tessia_engine_1 /root/tessia-engine/tools/cleanup_db
info: detected supervisorctl, assuming docker container mode
tessia-api: stopped
tessia-scheduler: stopped
tessia-api: started
tessia-scheduler: started
[user@myhost ~]$
```

After that, your database is 'clean' and you can run more tests manually as previously described.

## How to create client tests

The testcases are located in the folder `cli/tests/static_testcases`. Since the nature of the client tests mostly consists of execution of commands and parsing/validation
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

# Unit tests

Every module must have a corresponding unit test to validate it works. The tests are located under the folder `tests/unit` and follow the pattern `tests/unit/%{module_location}/%{module_name}.py`.

For example, for a module located at `tessia_engine/common/logger.py` the corresponding unit test is `tests/unit/common/logger.py`. That helps keeping things organized and makes it easier to determine which test(s) validate a given module/package/functionality.

## How to run unit tests

Pre-requisite: to go forward with this section, you must have the docker images already built. Learn how in [How to setup a development environment](dev_env.md).
An alternative method is to use a virtualenv created via [tox](https://tox.readthedocs.io/en/latest/index.html) as explained 
[here](dev_env.md#server-side-dev-environment-via-virtualenv-deprecated) but this method is deprecated in favour of the container approach.

First step is to start the containers in devmode using the orc tool:

```console
[user@myhost tessia-engine]$ tools/ci/orc devmode --tag=17.713.740
INFO: [init] using builder localhost
$ hostname --fqdn
normandy
INFO: [init] tag for images is 17.713.740
INFO: [devmode] starting services

(output suppressed...)

INFO: [devmode] you can now work, press Ctrl+C when done
```

Then in a different shell (or by sending the current process to background), execute the helper script according to which tests you want do execute:

```console
# to run all unit tests at once, use the following:
[user@myhost tessia-engine]$ docker exec tessia_engine_1 /root/tessia-engine/tools/run_tests.py
...............................................................................................................................................................................................
..................................................................................................................................................................................
----------------------------------------------------------------------
Ran 369 tests in 46.109s

OK
Name                                                     Stmts   Miss  Cover   Missing
--------------------------------------------------------------------------------------
tessia_engine/__init__.py                                     0      0   100%
tessia_engine/api/__init__.py                                 0      0   100%
tessia_engine/api/app.py                                     88      8    91%   64, 129, 151-157, 173
tessia_engine/api/cmd.py                                     16     16     0%   3-56
tessia_engine/api/exceptions.py                             163     93    43%   47, 92-100, 116-187, 238-240, 246, 253-255, 267-335, 422-427
tessia_engine/api/manager.py                                 74     31    58%   44-67, 74-76, 100, 143-147, 158, 182-184, 206-208, 210-212
tessia_engine/api/resources/__init__.py                      25      0   100%
(output suppressed...)
tessia_engine/state_machines/echo/__init__.py                 3      0   100%
tessia_engine/state_machines/echo/machine.py                 75      0   100%
--------------------------------------------------------------------------------------
TOTAL                                                     4697    720    85%
python3 -m coverage erase && python3 -m coverage run -a --source=tessia_engine -m unittest discover tests/unit -p '*.py' && python3 -m coverage report -m
[user@myhost tessia-engine]$

# if you don't want to run the full set of tests but only a specific module (the one you are developing for example), just specify its path in the script call:
[user@myhost tessia-engine]$ docker exec tessia_engine_1 /root/tessia-engine/tools/run_tests.py tests/unit/api/resources/storage_volumes.py
/usr/local/lib/python3.5/dist-packages/werkzeug/local.py:347: DeprecationWarning: json is deprecated.  Use get_json() instead.
  return getattr(self._get_current_object(), name)
.......................
----------------------------------------------------------------------
Ran 23 tests in 4.721s

OK
Name                                            Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------------
tessia_engine/api/resources/storage_volumes.py     105      0   100%
python3 -m coverage erase && python3 -m coverage run -a --include=tessia_engine/api/resources/storage_volumes.py -m unittest tests/unit/api/resources/storage_volumes.py && python3 -m coverage report -m
[user@myhost tessia-engine]$
```

The script will execute the unit test and provide a code coverage report so that you can verify whether the unit test is covering all the possible flows.

## How to create unit tests

The tests are created on top of python's standard library [unittest](https://docs.python.org/3/library/unittest.html). We also make extensive use of the mock library [unittest.mock](https://docs.python.org/3/library/unittest.mock.html) in order to lessen the effort of creating tests, as creating stubs might take a considerable amount of time.

By using mocking we are also able to write tests that validate the code *behavior*, instead of its *state*. This is a more thorough method of verification as it allows to validate the actions taken by the code being verified.

For example, in a given test you instantiate an object and call some of its methods to perform a given workflow. After that you would normally verify the values of some variables to validate the object's state. But in addition (or in place of, depending on the case) we can make use of the mocks to verify in which order, with which arguments, and how many times each of the mocks were called by the object to validate whether it behaved as expected.

A very nice article on this approach is [Mocks Aren't Stubs](http://martinfowler.com/articles/mocksArentStubs.html). In a nutshell, when creating tests keep in mind to use the mocks to assert the code behavior instead of focusing only on the return values.

### Creating API tests

Due to the fact that we use the [potion library](http://potion.readthedocs.io) to create the different Rest-API entry points it's very difficult to create meaningful tests for each
of them by using only mocks as a lot of things happen 'under the hood' in the combination potion+flask+sqlalchemy. Instead for those tests we run an in-memory sqlite database in conjunction
with a flask test object to have a real http api server and database running (if you are interested in the gory details, see 
`tests/unit/api/resources/secure_resource.py:setUpClass` for the flask setup and `tests/unit/db/model.py:DbUnit` for the db setup).

As a result, any unit test for an API entry point should inherit its class from the `TestSecureResource` class in order to have the proper setup. That class also provides many convenience
methods for easily performing requests and asserting them which allows optimal code re-use among all the entry points (since they share many common actions). Below you can find a
step-by-step explanation on how to create a new unit test module for an API entry point.

#### Step 1: class definition

- as mentioned earlier the class should inherit from `TestSecureResource`
- `RESOURCE_URL`: define the url to the corresponding entry point (this can be found in its potion class definition)
- `RESOURCE_MODEL`: associated sqlalchemy model class
- `RESOURCE_API`: the potion class for that API entry point
- `def _entry_gen`: generator (static method) that returns a dictionary containing fields and values for a new db entry of that resource. Some of the convenience methods inherited
from `TestSecureResource` use this generator to create instances automatically so that the developer don't need to repeat the same instance creation code everywhere.

Example:
```python
from tests.unit.api.resources.secure_resource import TestSecureResource
from tessia_engine.api.resources.storage_server_types import \
        StorageServerTypeResource
from tessia_engine.db import models

class TestStorageServerType(TestSecureResource):
    """
    Validates the StorageServerType resource
    """
    # entry point for resource in api
    RESOURCE_URL = '/storage-server-types'
    # model associated with this resource
    RESOURCE_MODEL = models.StorageServerType
    # api object associated with the resource
    RESOURCE_API = StorageServerTypeResource

    @staticmethod
    def _entry_gen():
        """
        Generator for producing new entries for database insertion.
        """
        index = 0
        while True:
            data = {
                'name': 'Storage server type {}'.format(index),
                'desc': ('- Description of storage server type {} with some '
                         '*markdown*'.format(index))
            }
            index += 1
            yield data
    # _entry_gen()

# TestStorageServerType
```

#### Step 2: create methods for the different testcases

Here is where we start to 'fill' the class with the different test scenarios. Many tests are very similar among the entry points (like create, delete, and so on) so you can use already
existing tests as a base for this new module. By looking at the other unit tests and the docstrings in the class `TestSecureResource` itself you'll notice many 'pre-made' convenience _test_*
methods that can be used that allow you to only type the specific bits of your entry point.

Examples speak better than words, so let's see some of them.

Testing a create fail scenario by only specifying the logins that are not allowed:
```python
    ...
    def test_add_all_fields_no_role(self):
        """
        Exercise the scenario where a user without an appropriate role tries to
        create an item and fails.
        """
        # all non admin users are not permitted to create items here
        logins = [
            'user_restricted@domain.com',
            'user_user@domain.com',
            'user_privileged@domain.com',
            'user_project_admin@domain.com',
            'user_hw_admin@domain.com'
        ]
        self._test_add_all_fields_no_role(logins)
    # test_add_all_fields_no_role()
```

Test a update fail scenario by specifying only the fields that are not allowed:
```python
    def test_add_update_wrong_field(self):
        """
        Test if api correctly reports error when invalid values are used for
        a field during creation and update.
        """
        # specify a field with wrong type
        wrong_data = [
            ('name', 5),
            ('name', True),
            ('name', None),
            ('desc', False),
            ('desc', 5),
            ('desc', None),
        ]
        self._test_add_update_wrong_field(
            'user_admin@domain.com', wrong_data)
    # test_add_update_wrong_field()
```

By basing yourself on an existing test you will have already a good headstart and from there you can check the coverage level report and add more tests until 100% is reached.

But keep in mind that this is just one of the metrics for evaluating code coverage. Additional test cases might be needed to cover all possible scenarios (i.e. using invalid values in order to force parse errors) so it is important to use different approaches to achieve meaningful unit testing.

If you find yourself in a situation where none of the pre-existing _test_* methods fit your needs you still can make use of some useful functions to make your life easier.
They are:

```
- _create_many_entries
- _do_request
- _request_and_assert
- _assert_created
- _assert_deleted
- _assert_listed_or_read
- _assert_updated
```

Remember to read their docstrings and look at existing unit tests that use them in order to learn how they can be used.

# Linting

## Rationale

Linting is the process of validating whether the codebase follows the pre-determined project code guidelines.
The current guidelines can be found [here](coding_guidelines.md).

## How to execute the lint validator
Pre-requisite: to go forward with this section, you must have the docker images already built. Learn how in [How to setup a development environment](dev_env.md).
An alternative method is to use a virtualenv created via [tox](https://tox.readthedocs.io/en/latest/index.html) as explained 
[here](dev_env.md#server-side-dev-environment-via-virtualenv-deprecated) but this method is deprecated in favour of the container approach.

Similar to how the unit tests are executed, there is a helper script to execute the pylint validator.
The first step is to start the containers in devmode using the orc tool:

```console
[user@myhost tessia-engine]$ tools/ci/orc devmode --tag=17.713.740
INFO: [init] using builder localhost
$ hostname --fqdn
normandy
INFO: [init] tag for images is 17.713.740
INFO: [devmode] starting services

(output suppressed...)

INFO: [devmode] you can now work, press Ctrl+C when done
```

Then in a different shell (or by sending the current process to background), execute the helper script `run_pylint.py`:

```console
[user@myhost tessia-engine]$ docker exec tessia_engine_1 /root/tessia-engine/tools/run_pylint.py

------------------------------------
Your code has been rated at 10.00/10

[user@myhost tessia-engine]$
```

**Note**: In the CI process the lint verification is done as part of the unit tests step.
