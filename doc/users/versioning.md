<!--
Copyright 2017, 2021 IBM Corp.

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

The project uses a PEP440 compliant versioning scheme in the form `major.minor.micro`.

This is how the version is determined for a given commit:

- if commit matches a release tag: `{release_tag}`
- if commit matches a release tag and there are local changes: `{release_tag}.dev0+g{commit_id}.dirty`
- if commit is after a release tag: `{release_tag}.post{commit_qty}.dev0+g{commit_id}`
- if commit is after a release tag and there are local changes: `{release_tag}.post{commit_qty}.dev0+g{commit_id}.dirty`
- if there's no release tag: `0.post{commit_qty}.dev0+g{commit_id}`
- if there's no release tag and there are local changes: `0.post{commit_qty}.dev0+g{commit_id}.dirty`
- if git is not available to determine version (i.e. no `.git` directory): `0+unknown`

Note that `{commit_qty}` is the number of commits since the tagged commit.

Some examples:

- commit matching release tag 2.0.4: `2.0.4`
- two commits after the release tag: `2.0.4.post2.dev0+b38ff82d`
- two commits after the release tag with local changes: `2.0.4.post2.dev0+b38ff82d.dirty`
