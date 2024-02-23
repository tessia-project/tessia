<!--
Copyright 2024, 2024 IBM Corp.

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
# Tela machine

This pages describes how to use the tela based machine for automatic task execution. Tela is an open source framework for running tests.
If you are unfamiliar with it, we recommend to visit the [Tela project homepage](https://github.com/ibm-s390-linux/tela).

In a nutshell, what this machine does is to integrate the systems managed by tessia with tela based test case executions using a Makefile.

# How it works

Here's a step by step description of how the machine works:

- User submits a job providing the necessary parameters, as the following example:

```yaml
# Note: optional parameters are marked with ("optional") in the below section

source: git://myhost.example.com/sample-testcase.git

# these are the tests to execute, refer to telas TESTS variable ("optional")
tests: memory_stress.sh disk-stress.sh

# environment variables to be passed to the test case ("optional")
env:
  TC_CPU_TOOLS_REMOTE_TEST_POLARIZATION_SLEEP: "10"
  TC_RUN_CLEANUP: true

# the target systems as known by tessia
systems:
  # system name in tessia, at least one
  - name: lpar15
  # multiple systems can be used
  - name: kvm50

# run a pre-execution script that is part of the repository ("optional")
# preexec_script: prepare.sh                   (short form)
preexec_script:
  path: prepare.sh
  args: ['--apply-token']
  env:
    TOKEN: ${other secret}

# run a post-execution script that is part of the repository ("optional")
# postexec_script: report.sh                   (short form)
postexec_script:
  path: report.sh
  args: ['--apply-token']
  env:
    TOKEN: ${other secret}

# secrets section to conceal sensitive values ("optional")
secrets:
  # a corresponding ${hidden parameter} entry will be replaced with its value
  hidden parameter: some token or other string
  other secret: some other string to use in pre-execution stage
```

- Job is started by the scheduler: a new process is spawned and the machine execution starts
- Machine downloads the specified repository from the specified source url
- The machine activates the involved systems, if not activated yet
- The machine executed the tela based test case by invoking the `make check` command
- The job finishes once tela finishes its execution

# How to use it

In this section we will see how to execute a test case on a target system.

Assuming we have a system named 'lpar15' previously installed with RHEL, we create a parameter file called `testcase.yaml` with the following content:
```yaml
source: https://github.com/testcase-repo/sample-testcase.git

systems:
  - name: lpar15
```

With our parameter file ready, we submit the job:

```
$ tess job submit --type=tela --parmfile=testcase.yaml

Request #2 submitted, waiting for scheduler to process it (Ctrl+C to stop waiting) ...
processing job  [####################################]  100%
Request accepted; job id is #2
```

It is possible to define a particular git revision (both a branch and a commit). Format of entry for such case:
```yaml
source: https://github.com/testcase-repo/sample-testcase.git@branch_name:commit_name
... 
```

There are several options for shortened entries:
```yaml
source: https://github.com/testcase-repo/sample-testcase.git@branch_name
... 
```
In this case `tessia` will take `HEAD` commit by default.

And we can skip `master` branch name as well:
```yaml
source: https://github.com/testcase-repo/sample-testcase.git@:commit_name
...
```

## How to pass secrets

Tessia stores all parameters in job requests and jobs, so they can be easily evaluated and reproduced.
This, however, is not ideal in a situation when parameters contain sensitive information, such as access tokens or keys.
Tessia provides a way to pass sensitive information without registering it in the database through `secrets` session in the parmfile.

The following example uses `secrets` section to supply a GitHub Personal Access Token to access a private repository:

```yaml
source: https://oauth2:${github_token}@github.com/private-repository/example.git

systems:
  - name: lpar15

secrets:
  github_token: <sample-oauth2-token>
```

Tessia removes secrets section from the parmfile before adding it into database, but the state machine receives complete information. Only one-line string values are supported in secrets.

Without `secrets` section tessia will automatically detect authorization information in the source URL, and use the same mechanism to pass authentication data.
