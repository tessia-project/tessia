<!--
Copyright 2016, 2017, 2018 IBM Corp.

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
# Continuous integration

The entry point for the CI execution is the *Orchestrator* (`tools/ci/orc`) which is responsible for parsing the command line arguments and start building the docker images.

It's possible to list the available images too:

```console
$ tools/ci/orc list-images

List of available images (Name - Description)

tessia-server -> Rest like API and job scheduler
tessia-cli -> Command line client

$ tools/ci/orc build --image=tessia-server
INFO: [init] going to perform a test build
INFO: [init] no config url set: local build mode
INFO: [init] using builder localhost
INFO: [init] deploying to zone localhost using controller local
INFO: [init] detected git repo name is tessia
INFO: [init] detected tag for images is ppinatti_ci_env-d462699
INFO: new state: image-build
INFO: [image-build] creating bundle of git repo
INFO: [image-build] sending git bundle to builder
INFO: [image-build] preparing context dir at /tmp/tmp.Z590UIFSOp/tessia
INFO: [image-build] downloading tessia-baselib to context dir
INFO: [image-build] build start at /tmp/tmp.Z590UIFSOp/tessia
INFO: [image-build] cleaning up work directory
INFO: new state: lint-check
INFO: [lint-check] executing tools/run_pylint.py on tessia-server
INFO: new state: unittest-run
INFO: [unittest-run] executing tools/run_tests.py on tessia-server
...
```

