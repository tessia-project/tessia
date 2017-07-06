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
# Versioning scheme

The project uses a date based versioning scheme, similar to the proposal from [Calendar Versioning](calver.org).
The advantages of using such scheme are:

- meaningful versions: from the version number one can tell when it was released and have a good idea of how newer is a version compared to 
another, as opposed to the traditional arbitrary versions where each project has their own semantics.
    - Example: v1.0 vs v1.1 and 17.04 vs 18.01
- auto generation: no need for the project maintainer to manually manage tags in the repository.

## Generation steps

A release version is generated according to the following steps:

- if current HEAD is the master branch, then:
    - extract the commiter's date of the master's branch HEAD, as in the command `git show -s --pretty='%ct' HEAD`
    - create release version in the format: `{YEAR}.{MONTH}{DAY}.{HOUR}{MINUTE}`
- if current HEAD is not the master branch:
    - find the point where this branch forked from master by using the merge-base command `git merge-base --fork-point master HEAD`
    - extract the commiter's date of the fork point commit (the commit where master and the current branch diverged)
    - create release version in the same format as for master: `{YEAR}.{MONTH}{DAY}.{HOUR}{MINUTE}`
    - add a suffix `+dev{HEAD_SHA}` to denote it's a local development version according to the PEP 440 [1]

For implementation details, see the setup.py file of the project's root directory.

The year is the last two digits and the months/days/hours/minutes are always without a leading zero (i.e. 24th July is 724 and not 0724).

Pay attention to the fact that the date used is the committer's date, not the author's date (commonly the latter is displayed when `git log` is executed).
We use the committer's date to make sure a commit date is always unique, which might not be the case for the author's date when two developers create a patch at
the same time but in separate branches. From the git manual [2]:
> You may be wondering what the difference is between author and committer. The author is the person who originally wrote the work, whereas the
> committer is the person who last applied the work. So, if you send in a patch to a project and one of the core members applies the patch, both
> of you get credit – you as the author, and the core member as the committer.

[1] https://www.python.org/dev/peps/pep-0440/#local-version-identifiers

[2] https://git-scm.com/book/en/v2/Git-Basics-Viewing-the-Commit-History

