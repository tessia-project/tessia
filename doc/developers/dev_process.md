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
# Development process

## Initial considerations

If you are coming from a gerrit background and are used to fast-forward only merges, a few words of clarification first.

While the *review unit* in gerrit is a single commit, in gitlab it is a set of commits represented by a **merge request** (which is exactly what the name suggests: a request to merge your topic branch to the master branch).

The merge could be done in a fast-forward way forcing a linear history, but we don't want that. Using the fast-forward only approach means:

- A rebase has to be done before the branch is merged, which means rewriting the commit history. If some other developer checked out this branch to base their own topic branch they will simply lose the reference and will have to recreate their branch and commits. We don't want that.
- Since rebase rewrites history, we are altering the true story about the development of the feature in the branch. Imagine that during development the branch worked fine and after the merge a problem was detected. If the problem was caused by the merge it can be easily spotted at the merge commit, but if a rebase was done the code merge is hidden in the commits of the rewritten history and more difficult to find.

Because of the above reasons we are not enforcing fast-forward only but rather adopting the `--no-ff` flag to any merge to the master branch. This is already gitlab's default behavior.

That does not mean you should never rebase. While your branch is still **yours** (you only pushed it without a merge request) you can (and actually should) rebase to make the history clearer and more organized after you finish the implementation. More on that on next section.

If you are interested in going deeper with the rebase vs merge topic, take a look at the [References](#references) section at the end of page.

## Step-by-step process to submit a merge request

- Start by creating your branch with the usual `git checkout -b mybranch base_branch`
- To make sure your patches are always respecting the project coding guidelines (they can be found [here](coding_guidelines.md)), install the pre-commit git hook which runs the pylint tool automatically on each commit. That can be done in two easy steps:
    - run the script to install the hook: `./tools/apply-git-hooks.sh`
    - install tox (a tool to create virtualenvs): `pip3 install tox`
- Do your work, create/change your files and commit them. At this point the branch is still **yours** and you can mess around as much as you like (i.e. rebasing or creating small commits as you do more work)
- Make sure to create/update corresponding unit tests to validate the changes you made (patches without tests won't be accepted). And don't forget to run them. See the section [Unit tests](tests.md#unit-tests) for details.
- Update documentation to reflect the changes. More details on the page [Working with documentation](documentation.md)
- Remember to push your branch often in order to have a backup (and allow others to follow your work too). Since the branch is not "published" yet by a merge request it is fine to do force pushes (as a result of your rebases).
- When you consider your branch ready, do the final rebases to make the commit messages meaningful and the commits concise.
- Finally, create the merge request. See [Gitlab documentation](http://doc.gitlab.com/ce/gitlab-basics/add-merge-request.html) for details. If your request is related to an open issue, remember to add the expression `(closes #{issue_number})` as in `Add support to distro X (closes #51)`. That enables gitlab to automatically close the issue once the merge requested is accepted.

## After the merge request

Once you submit a merge request no more rebasing should occur. The branch is now considered **public**: others might checkout from it and the peer review comments must stay coherent (which would not happen if rebases happened during review, as it implies a force push invalidating previous history). So it's very important **before submitting a merge request** to make sure the code works, the commit history is concise and the commit messages are well written because after this point corrections will only be possible with a new commit and we don't want to have our history full of 'fixed typo' commits right? ;-)

## References

- [in favour of rebase](http://blog.izs.me/post/37650663670/git-rebase)
- [in favour of merge](http://paul.stadig.name/2010/12/thou-shalt-not-lie-git-rebase-ammend.html)
