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
# Table of contents

- [Rationale](#rationale)
- [File organization](#file-organization)
    - [Use spaces instead of tabulations for indentation](#use-spaces-instead-of-tabulations-for-indentation)
    - [File sections](#file-sections)
    - [Do not mix classes and functions in the same file](#do-not-mix-classes-and-functions-in-the-same-file)
    - [Function and class end markers](#function-and-class-end-markers)
    - [Break lines at column 79](#break-lines-at-column-79)
    - [How to break long statements](#how-to-break-long-statements)
    - [Refactor methods and functions that have more than 200 lines](#refactor-methods-and-functions-that-have-more-than-200-lines)
    - [Sort methods and functions by name](#sort-methods-and-functions-by-name)
    - [Sort imports by name and type](#sort-imports-by-name-and-type)
    - [Never import using a wildcard](#never-import-using-a-wildcard)
    - [Avoid instance creation during module loading](#avoid-instance-creation-during-module-loading)
- [Naming conventions](#naming-conventions)
    - [Class names](#class-names)
    - [Other names](#other-names)
    - [Non-public names](#non-public-names)
    - [Constants and global variables](#constants-and-global-variables)
- [Code documentation](#code-documentation)
    - [Docstrings](#docstrings)
    - [Write a comment for each logical block of code](#write-a-comment-for-each-logical-block-of-code)
    - [Ensure there is a comment at least every 5 lines](#ensure-there-is-a-comment-at-least-every-5-lines)
    - [Standardize branching comments](#standardize-branching-comments)
- [Branching](#branching)
    - [Do not use 'else' after an 'if' that always returns](#do-not-use-else-after-an-if-that-always-returns)
    - [If an 'else' always returns make it be the 'if' by inverting the condition](#if-an-else-always-returns-make-it-be-the-if-by-inverting-the-condition)
- [Exception handling](#exception-handling)
- [Unit Tests](#unit-tests)
    - [Do not turn off pylint verification in your tests](#do-not-turn-off-pylint-verification-in-your-tests)
    - [Group patching and mocking under setUp](#group-patching-and-mocking-under-setup)
    - [Add a comment to each action of the testcase](#add-a-comment-to-each-action-of-the-testcase)
- [TODO markers](#todo-markers)
- [Misc guidelines](#misc-guidelines)

# Rationale

This document defines the project's coding guidelines so that we can spend less time trying to understand our code and avoid bugs that are more likely introduced in code that is not well understood.

# File organization

## Use spaces instead of tabulations for indentation

- Use 4 spaces for each indentation block.
- Don't mix indent levels. i.e. always use 4 spaces, regardless of how nested the block is (**Tip** - On Vim use: `:set expandtab`).
- **Rationale I:** mixing up spaces and tabs might confuse other developers and even the python interpreter.
- **Rationale II:** tabs have variable size and are user-configurable, spaces aren't.

## File sections

- Every file must start with a copyright and license header (before the module docstring).
    - Other secondary information can be placed here. Comments explaining the function of the module should only go in the docstring.
- After the header comment, include the module docstring.
- Next, ensure the file has the sections: "imports", "constants and definitions" and "code".
- Separate each section with a blank line.
- Put imports only in the section `IMPORTS`.
- Define globals and constants only in the section `CONSTANTS AND DEFINITIONS`.
- Do not define globals and constants in class-only files, use static constants and variables inside the class.
- Define classes or functions only in the section `CODE`.
- **Rationale:** improve code organization.

### Noncompliant example

```python
BUFFER_SIZE = 4096

import os
from package_b.module_b import object_b
import sys

from module_a import object_a

TEMPLATES_DIR = '/opt/templates'

def do_something():
...
```
### Compliant example

```python
"""
This module does this and that.

Some more detailed info about the module here.
"""

#
# IMPORTS
#
from module_a import object_a
from package_b.module_b import object_b

import os
import sys

#
# CONSTANTS AND DEFINITIONS
#
BUFFER_SIZE = 4096
TEMPLATES_DIR = '/opt/templates'

#
# CODE
#


def do_something():
...
```

## Do not mix classes and functions in the same file

- Define a single class or single library of functions in a file.
- Do not define more than one class in the same file.
    - Acceptable exceptions include internal classes for private use in the module (this must be documented and the class name must be prefixed with a single underscore), or inner classes.
- **Rationale:** improve code organization and modularization.

## Function and class end markers

- Function and class end markers are not mandatory.
- Be consistent on each file, either use them throughout a given file or not at all.
- If you do use them, follow these rules:
    - Use a single-line comment aligned with the start of the function or class definition.
    - For functions, write the function name with no def and with a pair of parentheses.
    - For classes, write the class name.

```python
class MyClass():
    def foo(self, bar):
        ...
    # foo()
# MyClass
```

## Break lines at column 79

- **Rationale I:** the bigger a line is, the harder it is to follow and read it.
- **Rationale II:** ensure the code can be easily read in a terminal.
- **Rationale III:** allow two files to be read side by side on larger screens.

## How to break long statements

- If you wrap an expression in parentheses, python lets you break it in lines. Use this instead of breaking lines with \\ whenever possible.
    - Some long statements that are not expressions cannot be broken with parentheses, in this case use \\.
- Break expressions in a statement using hanging indents or vertically align the broken parts.
    - Unless you are using hanging indents, don't leave a single closing parenthesis or bracket in a line, as shown in the examples below.
    - If you leave a single closing parenthesis or bracket in a line, either leave it on the first column or align it with the first
      non-whitespace character of the previous line.
- **Rationale I:** Straight alignment makes multiline expressions easier to read.
- **Rationale II:** Less error prone when adding/removing entries to data structures (lists, dicts, tuples).

### Noncompliant example

```python
result = my_long_module_name.my_long_function_name(parameter_a,
    parameter_b,
    parameter_c)

# list definition
list_a = [element_a,
    element_b,
    element_c]

# alignment is correct, but
# non-hanging indent has a single closing bracket in a line
list_a = [element_a,
          element_b,
          element_c,
]

# tuple definition
tuple_a = (element_a,
element_b,
element_c)

# dict definition
dict_a = {
'key_a': 'value_a',
'key_b': 'value_b',
'key_c': 'value_c',}
```

### Compliant example

```python
# vertical alignment
result = my_long_module_name.my_long_function_name(parameter_a,
                                                   parameter_b,
                                                   parameter_c)

# hanging indent
result = my_long_module_name.my_long_function_name(
    parameter_a,
    parameter_b,
    parameter_c)

big_string = ("This is how you can break long long long long long long long"
              "string literals")

# list definition
list_a = [
    element_a,
    element_b,
    element_c]

list_a = [
    element_a,
    element_b,
    element_c,
]

list_a = [
    element_a,
    element_b,
    element_c,
    ]

list_a = [elementA,
          elementB,
          elementC]

# tuple definition
tuple_a = (
    element_a,
    element_b,
    element_c,
)

# dict definition
dict_a = {
    'key_a': 'value_a',
    'key_b': 'value_b',
    'key_c': 'value_c',
}
```

## Line break before binary operators

### Noncompliant example
```python
sum = (1 + 2 + 3 +
       4 + 5 +
       6 + 7)
```

### Compliant example
```python
sum = (1 + 2 + 3
       + 4 + 5
       + 6 + 7)
```

## Whitespace rules

- Don't leave trailing whitespace.
- Follow these next examples.

### Noncompliant example
```python
one=1
function_call( a,b,c )
function_call( karg = 1 )
list = [a,b,c]
dict = {'a' : 2, 'b' : 3}
```

### Compliant example
```python
one = 1
function_call(a, b, c)
function_call(karg=1)
list = [a, b, c]
dict = {'a': 2, 'b': 3}
```

## Refactor methods and functions that have more than 200 lines

- Design functions with clear separation of responsibilities.
- Avoid deep nesting inside a single function.
- **Rationale I:** the smaller a method is, the faster it is to understand what it does.
- **Rationale II:** the bigger a method is, more likely it will have a bug.

## Sort methods and functions by name

- **Rationale:** make it easier to find a method in a class or a function in a module.

### Noncompliant example

```python
class SomeClass(object):

    def method_b(self):
        ...
    # method_b

    def _private_b(self):
        ...
    # _private_b

    def method_a(self):
        ...
    # method_a

    def method_c(self):
        ...
    # method_c

    def _private_a(self):
        ...
    # _private_a

# SomeClass
```

### Compliant example

```python
class SomeClass(object):

    def _private_a(self):
        ...
    # _private_a

    def _private_b(self):
        ...
    # _private_b

    def method_a(self):
        ...
    # method_a

    def method_b(self):
        ...
    # method_b

    def method_c(self):
        ...
    # method_c

# SomeClass
```

## Sort imports by name and type

- Do not import more than one name in the same line, unless importing names from the same module with the `from module import X, Y` syntax
    - You don't need to sort the names alphabetically within this line, since there might be many of them.
- Group imports of the type `from module import X`.
- Group imports of the type `import module`.
- Sort the imports by module name inside a group.
- **Rationale:** make it easier to find an import in the list.

### Noncompliant example

```python
import module_c
from package_a.module_b import object_g
from module_a import object_a
import module_d, module_e
from module_b import object_d, object_e
from package_a.module_b import object_f
```

### Compliant example

```python
from module_a import object_a
from module_b import object_d, object_e
from package_a.module_b import object_f
from package_a.module_b import object_g

import module_c
import module_d
import module_e
```

## Never import using a wildcard

- Never use ```*``` in an import statement.
- **Rationale I:** avoid problems to find out where a name referenced in a file has been defined.
- **Rationale II:** avoid unwanted namespace clashes.

### Noncompliant example

```python
from module_a import *
from module_b import *

# can you tell where someVariable has been defined?
print(CONSTANT_A)

# can you tell where otherVariable has been defined?
print(CONSTANT_B)
```

### Compliant example

```python
from module_a import CONSTANT_A
from module_b import CONSTANT_B

# now you easily know that CONSTANT_A is defined in moduleA
print(CONSTANT_A)

# now you easily know that CONSTANT_B is defined in moduleB
print(CONSTANT_B)
```
## Avoid instance creation during module loading

- Creating objects or connections just once upon the first module loading might be convenient when a singleton-like approach is wanted, but is a problem when mocking during unit testing.
- As an alternative, you can use a delayed access approach with property decorators.

### Noncompliant example

```python
def connect():
    ...
    return session

db_session = connect()
```

### Compliant example
```python
class DbConnection(object):
    def __init__(self):
        ...
        self._conn = None
    ...

    @property
    def session(self):
        if self._conn is None:
            self._conn = self._connect()
        return self._conn
    ...
# DbConnection

# for unit tests db._conn can be set to None which forces a new connection to
# be created
db = DbConnection()
```

# Naming conventions

- SomeClass for classes.
- Use lowercase with underscores for any other names.
- See detailed explanation below.

## Class names

- Capitalize each word in the name: `SomeClass`.
- Don't use underscore to separate the parts of the name.
- Use a leading underscore when defining non-public classes.

### Noncompliant examples

```python
class someClass:
    ...

class Some_Class:
    ...

class SOME_CLASS:
    ...
```

### Compliant example

```python
class SomeClass:
    ...
```

## Other names

- Applies to any other name (attributes, function definitions, packages, modules, etc).
- Lowercase each part of the name, and separate them by underscore: `local_variable`.
- Use 'self' for the first argument of a method and 'cls' for the first argument of a static method.

### Noncompliant examples

```python
    localVariable = 123
    LocalVariable = 123
    LOCAL_VARIABLE = 123

    def someMethod(myself):
```

### Compliant examples

```python
    local_variable = 123
    some_other_variable = 'Error message'

    def some_method(self):
```

## Non-public names

- Prefix all non-public names with one underscore.
- **Rationale:** Indicate which names are implementation details and should not be directly used outside a class or module.

## Constants and global variables

- The names of constants and global variables are always uppercased.

### Noncompliant examples

```python
bufferSize = 4096
buffer_size = 4096
BufferSize = 4096
main_proc = some_module
mainProc = some_module
```

### Compliant example

```python
BUFFER_SIZE = 4096
MAIN_PROC = some_module
```

# Code documentation

## Docstrings

- Document all classes, methods, functions, and modules with docstrings.
- Docstrings should be writen following [Google Style](https://google.github.io/styleguide/pyguide.html#Comments) (for specifics on how to document arguments, return values, etc.)
    - Exception: you are not required to document public class attributes.
    - Remember to specify the types for arguments/return value/exceptions (see example below)
- You must also document non-public functions, methods and classes.
- It's ok to skip arguments/returns/raises/ sections if none applies (function without arguments, returns nothing or raises nothing).
- **Rationale:** ensure the classes, methods and functions have well-defined and documented roles and interfaces.

### Noncompliant example

```python
class Calculator(object):
    ...

    def add(self, param_a, param_b)
        ...

```

### Compliant example
```python
"""
Module summary.

More detailed information about the module here.
"""

#
# IMPORTS
#

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class Calculator(object):
    """
    Class summary.

    This calculator can do addition and multiplication,
    this is a longer description of this class.


    Attributes
        attribute_one: A cool integer
    """

    def __init__(self):
        self.attribute_one = "cool"

    def add(self, param_a, param_b=0.0):
        """
        Add two numbers.
        Returns the sum of paramA and paramB. If paramB is not
        passed, assume 0.0 as its value.

        Args:
            param_a (float): first float number to be added
            param_b (float): second float number to be added

        Returns:
            int: sum of param_a and param_b

        Raises:
            TypeError: if paramA or paramB is not a float
        """
        pass
```

## Write a comment for each logical block of code

- Any algorithm has well-defined steps and each step is implemented by one or more lines of code.
- A logical block is the group of lines that implement a step of the algorithm.
- Use a comment to describe what a logical block (algorithm step) does.
- Separate each logical block with a blank line.
- **Rationale:** clearly describe the algorithm implemented by the code, making it easier to understand.

### Noncompliant example

```python
    stream = open('/etc/resolv.conf', 'r')
    data = stream.data()
    stream.close()
    output = []
    for line in data.readlines():
        if len(line) > 0:
            output.append(line)
    stream = open('/etc/resolv.conf', 'w')
    stream.write('\n'.join(output))
    stream.close()
```

### Compliant example

```python
    # read the data from /etc/resolv.conf
    stream = open('/etc/resolv.conf', 'r')
    data = stream.data()
    stream.close()

    # get only the non-empty lines
    output = []
    for line in data.readlines():
        if len(line) > 0:
            output.append(line)

    # write the chosen lines to the file
    stream = open('/etc/resolv.conf', 'w')
    stream.write('\n'.join(output))
    stream.close()
```

## Ensure there is a comment at least every 5 lines

- Every logical block (algorithm step) should have a comment.
- If a logical block has more than 5 lines of code, it can likely be split into smaller ones.
- **Rationale:** more than 5 lines without a comment start to make code harder to understand than it should be.

## Standardize branching comments

- Always comment if, elif and else like: # condition: action
- **Rationale:** make it *immediately clear* the meaning of the condition being checked and what action is taken on it.

### Noncompliant example

```python
    if not os.stat(dir)[0] & 16384 or os.stat(dir)[6] < MIN:
        ... line one ...
        ... line two ...
        ... line tree ...

    elif os.stat(dir)[6] % 2 != 0:
        ... line one ...
        ... line two ...
        ... line tree ...
        ... line four ...
        ... line five ...
        ... line six ...
        ... line seven ...

    else:
        ... line one ...
        ... line two ...

```

### Compliant example

```python
    # not a directory or no space enough available: cleanup and abort
    if not os.stat(dir)[0] & 16384 or os.stat(dir)[6] < MIN:
        ... line one ...
        ... line two ...
        ... line tree ...

    # size is not a multiple of 2: run the code in special mode
    elif os.stat(dir)[6] % 2 != 0:
        ... line one ...
        ... line two ...
        ... line tree ...
        ... line four ...
        ... line five ...
        ... line six ...
        ... line seven ...

    # directory with space enough: run the code
    else:
        ... line one ...
        ... line two ...
```

# Branching

## Do not use 'else' after an 'if' that always returns

- **Rationale:** linear code is easier to follow and understand than nested code.

### Noncompliant example

```python
    # some condition: do something
    if condition:
        ... do something ...
        return

    # or: do other thing
    else:
        ... first line ...
        ... second line ...
        ... third line ...

        # other condition: run my nested if
        if other < 10:
            ... fourth line ...
            ... fitth line ...
            ... sixth line ...

        # run a few more lines
        ... seventh line ...
        ... eighth line ...
```

### Compliant example

```python
    # some condition: do something
    if condition:
        ... do something ...
        return False

    # or: do other thing
    ... first line ...
    ... second line ...
    ... third line ...

    # other condition: run my (no longer) nested if
    if other < 10:
        ... fourth line ...
        ... fitfth line ...
        ... sixth line ...

    # run a few more lines
    ... seventh line ...
    ... eighth line ...
```

## If an 'else' always returns make it be the 'if' by inverting the condition

- In case the *if* will always return too, then the case is covered [in this guideline](#do-not-use-else-after-an-if-that-always-returns).
- **Rationale:** linear code is easier to follow and understand than nested code.

### Noncompliant example

```python
    # condition is ok: run many lines
    if condition:
        ... first line ...
        ... second line ...

        # other condition: run my nested if
        if other < 10:
            ... third line ...
            ... fifth line ...
            ... sixth line ...
            ... seventh line ...
            ... eighth line ...

        # run a few more lines
        ... ninth line ...
        ... tenth line ...
        ... eleventh line ...

    # error: stop here
    else:
        return False
```

### Compliant example

```python
    # error: stop here
    if not condition:
        return False

    # condition is ok: run many lines
    ... first line ...
    ... second line ...

    # other condition: run my (no longer) nested if
    if other < 10:
        ... third line ...
        ... fifth line ...
        ... sixth line ...
        ... seventh line ...
        ... eighth line ...

    # run a few more lines
    ... ninth line ...
    ... tenth line ...
    ... eleventh line ...
```

# Exception handling

- Define exception classes in a separate file in the package where they are used.
- Derive custom exceptions from Exception, not BaseException.
- Remember that ```except:``` is the same as ```except BaseException:```. Consider using ```except Exception:``` instead of plain ```except:``` when catching program errors. ```BaseException``` also includes, for instance, ```SystemExit``` and ```KeyboardInterrupt``` that generally should not be supressed.
   - You might need to do some cleanup (e.g. closing files). In these cases you can also catch ```BaseException```, but remember to re-raise it. However, prefer using context managers (```with``` keyword) or ```try...finally``` instead.
- If you need to substitute an exception by raising another exception inside of an ```except``` block, use the construct ```raise X from Y```. This way, the ```__cause__``` attribute in X will be set to Y, and the original exception will be known.

# Unit tests

## Do not turn off pylint verification in your tests

- **Rationale:** avoid creating code not compliant with guidelines.
- Although for unit tests some special behaviors apply (like accessing protected variables), you should not turn off pylint verification completely as it will skip other rules that should otherwise be enforced (i.e. variable naming, line too long).
- Instead, you can skip pylint verification in a local basis (i.e. add the `pylint disable` directive in front of the statement) or if it applies to many cases you can use the statement in a broader scope (method, class or even module) but only for the rule in question.
- If the exception is so common that also applies to other tests/modules consider adding the directive to the pylintrc file.

### Noncompliant examples

```python
# pylint:skip-file
"""
Test for module foo
"""
...
class TestModuleFoo(TestCase):
    ...
```

```python
...
#
# CODE
#
# pylint: disable=all
class TestMyModule(TestCase):
...
```

### Compliant example

```python
#
# CODE
#
class TestMyModule(TestCase):
    ...
    def test_attribute_foo(self):
        ...
        self.assertIs(
            self.object_bar.attribute_foo, None) # pylint: disable=no-member
        )
    # test_attribute_foo()
    ...
# TestMyModule
```

## Group patching and mocking under setUp

- **Rationale:** avoid code duplication.
- It's very common to use the same patches/mocks in different testcase methods in the same unit test which leads to duplicated code. Try to group the patching/mocking in the setUp method and when necessary set the specific mock behavior in the testcase method.
- When doing patching in the setUp do not forget to stop the patching after the testcase method finishes by calling addCleanup and providing the patcher.stop method.

### Noncompliant example

```python
    @mock.patch("module_foo.object_foo", autospec=True)
    @mock.patch("module_x.module_bar.object_bar", autospec=True)
    @mock.patch("module_y.module_z.object_y", autospec=True)
    def test_success(self, mock_object_y, mock_object_bar, mock_object_foo):
        ...
        mock_object_foo.return_value = 5
        mock_object_bar.side_effect = ['success', 'success']
        mock_object_y.return_value = sentinel.ret_object_y
        ...
        # behavior verification
        mock_object_foo.assert_called_with()
        ...
    ...

    @mock.patch("module_foo.object_foo", autospec=True)
    @mock.patch("module_x.module_bar.object_bar", autospec=True)
    @mock.patch("module_y.module_z.object_y", autospec=True)
    def test_fail(self, mock_object_y, mock_object_bar, mock_object_foo):
        ...
        mock_object_foo.return_value = 5
        mock_object_bar.side_effect = ['success', 'failed']
        mock_object_y.return_value = sentinel.ret_object_y
        ...
        # behavior verification
        mock_object_foo.assert_called_with()
        ...
```

### Compliant example

```python
    def setUp(self):
        """
        Prepare necessary objects before executing each testcase
        """
        patcher = patch("module_foo.object_foo", autospec=True)
        self._mock_object_foo = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_object_foo.return_value = 5

        patcher = patch("module_x.module_bar.object_bar", autospec=True)
        self._mock_object_bar = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_object_bar.side_effect = ['success', 'success']

        patcher = patch("module_y.module_z.object_y", autospec=True)
        self._mock_object_y = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_object_y.return_value = sentinel.ret_object_y

    # setUp()

    def test_success(self):
        ...
        # behavior verification
        self._mock_object_foo.assert_called_with()
        ...

    def test_fail(self):
        ...
        self._mock_object_bar.side_effect = ['success', 'failed']
        ...
        # behavior verification
        self._mock_object_foo.assert_called_with()
        ...
```
## Add a comment to each action of the testcase

- **Rationale:** make test code easier to understand and maintain.
- Like for normal code it's important to add comments explaining the purpose of a logical block in a testcase so that it's immediate clear what the test is doing.

# TODO markers

- **Rationale:** make sure we can easily search for any TODOs left.
- Only use the marker TODO when marking code sections for improvement.

# Misc guidelines

- Compare to None using 'x is None' or 'x is not None', don't use 'x == None'.
- We require no single choice for using either single or double quotes to delimit string literals, you are free to choose.
