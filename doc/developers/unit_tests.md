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
# Unit tests

Every module must have a corresponding unit test to validate that it works. The tests are located under the folder `tests/unit` and follow the pattern `tests/unit/%{module_location}/%{module_name}.py`.

For example, for a module located at `tessia_engine/common/logger.py` the corresponding unit test is `tests/unit/common/logger.py`. That helps keeping things organized and makes it easier to determine which test(s) validate a given module/package/functionality.

## How to run tests

We use the [tox tool](https://tox.readthedocs.io/en/latest/index.html) to create virtualenvs for our project.
Make sure you have a working virtualenv by following the instructions [here](dev_env.md#virtualenv-installation).

Confirm that you have your virtualenv activated and you can execute the tests by using the helper script:

`$ tools/run_tests.py`

If you don't want to run the full set of tests but only a specific module (the one you are developing for example), just specify its path in the script call:

`$ tools/run_tests.py tests/unit/common/logger.py`

The script will execute the unit test and provide a code coverage report so that you can verify whether the unit test is covering all the possible flows.

## How to create tests

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
