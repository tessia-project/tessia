<!--
Copyright 2016 IBM Corp.

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
# Working with documentation

The project's documentation uses the markdown format and mkdocs to build the html pages. Markdown is an easy-to-learn and well known format (same as used in Github).

Mkdocs has a simple usage and does not neeed a complex configuration like sphinx to be used. If you are interested you can find the details [here](http://www.mkdocs.org/).

As Gitlab has built-in support to parse markdown and display html while browsing files, all documentation can either be built in html by mkdocs or visualized directly on gitlab.
Keep that in mind when editing the files, as there might be slight differences between the markdown supported by each of them.

For explanation on the markdown syntax, see [Gitlab explanation](https://github.com/gitlabhq/gitlabhq/blob/master/doc/markdown/markdown.md).

While you are doing changes to the documentation files, it's easy to visualize the resulting html in real-time. The first possibility is to use gitlab web interface and its preview function. The second is to edit the files locally and use mkdocs and its option to run a simple html server which detects updates to the files and rebuilds them automatically. To start the server in a virtualenv (the recommended way), use tox:

`$ tox -e doc serve`

You should see a line like this: `[I 160615 16:31:32 server:281] Serving on http://127.0.0.1:8000`, you can now open the browser and point it to that address.

If you don't want to use tox, you can start the mkdocs server with:

`$ tools/mkdocs.py serve`

In this case, make sure you have mkdocs installed on your system.

Regardless of the option you choose (gitlab web interface or mkdocs locally), remember to visualize your changes with both options to make sure the markdown you used works on both.
For example, if you did your work using gitlab, then start mkdocs server and review the documentation locally with your browser. If you used mkdocs, you can push your branch and browse the files on gitlab before creating the merge request.

## Building

If you want to upload the documentation and need to build it, use the same mkdocs command but replace `serve` by `build`. By default the files will be stored under the folder `build/html` at the root of the repository.
You can specify a different location with the `-d` parameter. Examples:

- `$ tox -e doc build`
- `tools/mkdocs.py build -d /tmp/html`
