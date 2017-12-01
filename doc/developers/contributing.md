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
# How to contribute (development process)

Contributions are welcome! Here's a step-by-step description of how you can submit your patches:

## Step 1 - create the branch

- Create your branch (i.e. `git checkout -b mybranch master`). Follow this pattern for the branch name:
    - feature/description (for new features)
    - bug/description (for bug fixes)
    - doc/description (when only documentation is updated)
    - test/description (when only tests are updated)

## Step 2 - write the changes

Do your work, create/change the necessary files and commit them. Some guidelines:

- Remember to follow our project's [Coding guidelines](coding_guidelines.md).
- If you are changing code or tests you must learn [How to setup a development environment](dev_env.md).
- Changes should be accompanied by tests. For changing/writing tests, see some tips at [Integration and unit tests](developers/tests.md).
- If you are changing documentation, have a look at [Working with documentation](developers/documentation.md).
- Avoid submitting patches with whitespace errors. Use a text editor which visually shows trailing whitespaces or use git before committing your code by
running `git diff --check`, which identifies possible whitespace errors and lists them for you.
- Make each commit a self contained logical changeset - this means a commit should not depend on a next commit to work or to make sense. Also avoid to
create too big commits that are hard to review.
- The format of the commit message is also important, see the section [Commit messages format](#commit-messages-format) to learn how they should look like.

It's a good idea to push your branch often in order to have a backup (and in certain cases to allow others to follow your work too).
Regarding rebase: since the branch is not "published" yet (no merge/pull request) it is in fact a good idea to rebase from master or rebase to squash multiple commits in order to
maintain the branch commit history "clean".

When ready, do the final rebases/squashes and make the commit messages meaningful and the commits concise. This is the last chance to do so, as once the merge/pull request is submitted
the branch is available for review or checkout by others and no more rebasing should occur.
Don't forget to run the tests and lint (for coding guidelines), learn more about them at [Integration and unit tests](tests.md).

## Step 3 - create the merge/pull request

If your request is related to an open issue, it's a good idea to add the expression `(closes #{issue_number})` as in `Add support to distro X (closes #51)` to the request.

## Step 4 - code review

During the review process you might be asked to do logic adjustments, add missing tests, etc., do it by adding new commits without rebasing the branch.

# Commit messages format

Messages should start with a single line containing a summary of the changes (max 70 chars), followed by one or more paragraphs or bullets with detailed explanation about the motivation
of the change. A good approach to decide what to write in the detailed explanation is to describe how the change affects the previous behavior/implementation.
Use also the imperative present tense - that means instead of writing "I added tests..." or "Adding tests for.." you should write "Add tests for...".
See the chapter [Contributing to a Project](http://git-scm.com/book/en/v2/Distributed-Git-Contributing-to-a-Project) of the online git book for references.

Finally, your commit message must contain a sign-off including a reference to the
[DCO 1.1](https://gitlab.com/tessia-project/tessia/blob/master/DCO1.1.txt) (Developer Certificate of Origin) used in the project in order to confirm you
followed the rules described in the document.

Here's a commit message template summarizing the guidelines above:

```
Short (max 70 characters) summary of changes

More detailed explanatory text, if necessary.  Wrap it to about 72
characters or so. The blank line separating the summary from the body
is mandatory.
Further paragraphs might come after a breakline.

- Bullet points with hyphens are okay too

DCO 1.1 Signed-off-by: John Doe <jdoe@email.com>
```

## Set a commit message template in git

In order to make your life easier, you can add a commit template to the git configuration. Here's how to do it:

Create a file `~/.git/.commit-message-template` with the template text:

```
<short summary>

<detailed multi-line description>

DCO 1.1 Signed-off-by: John Doe <jdoe@email.com>
```

Set git to use this file:

```
$ git config commit.template ~/.commit-message-template
```

Now whenever you commit something the template will come up automatically and you will just need to fill the `<short summary>` and `<detailed multi-line description>` sections.
