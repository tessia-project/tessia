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

We make use of the [tox tool](https://tox.readthedocs.io/en/latest/index.html) to create virtualenvs for our project. For testing, one can run tox specifying the `test` virtualenv and all the unit tests will be executed in the correct environment:

`$ tox -e test`

Easy right? :-) Just make sure to have tox (`pip3 install tox`) and the python3.4 runtime installed on your system.

During development you might want to use your own environment to run the tests because it's quicker than calling tox. It's okay, as long as you remember to test using tox before pushing your patch.
To execute the tests directly, use the helper script:

`$ tools/run_tests.py`

If you don't want to run the full set of tests but only a specific module (the one you are developing for example), just specify it to tox or to the helper script.

Example for using tox:

`$ tox -e test tests/unit/common/logger.py`

Example for executing directly:

`$ tools/run_tests.py tests/unit/common/logger.py`

## How to create tests

The tests are created on top of python's standard library [unittest](https://docs.python.org/3/library/unittest.html). We also make extensive use of the mock library [unittest.mock](https://docs.python.org/3/library/unittest.mock.html) in order to lessen the effort of creating tests, as creating stubs might take a considerable amount of time.

By using mocking we are also able to write tests that validate the code *behavior*, instead of its *state*. This is a more thorough method of verification as it allows to validate the actions taken by the code being verified.

For example, in a given test you instantiate an object and call some of its methods to perform a given workflow. After that you would normally verify the values of some variables to validate the object's state. But in addition (or in place of, depending on the case) we can make use of the mocks to verify in which order, with which arguments, and how many times each of the mocks were called by the object to validate whether it behaved as expected.

A very nice article on this approach is [Mocks Aren't Stubs](http://martinfowler.com/articles/mocksArentStubs.html). In a nutshell, when creating tests keep in mind to use the mocks to assert the code behavior instead of focusing only on the return values.
