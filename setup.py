#!/usr/bin/env python3
# Copyright 2016, 2017 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Entry point to setuptools, used for installing and packaging
"""

#
# IMPORTS
#
from datetime import datetime
from setuptools import setup

import os
import subprocess

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
def _run(cmd):
    """
    Simple wrapper to run shell commands

    Args:
        cmd (str): description

    Returns:
        str: stdout+stderr

    Raises:
        RuntimeError: in case command's exit code is not 0
    """
    result = subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True)
    if result.returncode != 0:
        raise RuntimeError(
            "command '{}' failed: {}".format(cmd, result.stdout))

    return result.stdout.strip()
# _run()

def gen_version():
    """
    Release version is created from the commiter date of the HEAD of the master
    branch in the following format:
    {YEAR}.{MONTH}{DAY}.{HOUR}{MINUTE}
    In case the current HEAD is not master, the fork point commit from master
    will be used and a suffix 1.dev{HEAD_SHA} is added
    to denote it's a development version.

    Returns:
        str: the calculated version

    Raises:
        RuntimeError: if one of the git commands fail
    """
    # determine if it's a dev build by checking if the current HEAD is the
    # same as the master branch
    head_sha = _run('git show -s --oneline --no-abbrev-commit').split()[0]
    # make sure branch master exists; it might not exist yet when the repo
    # was cloned from a different HEAD as it is the case when creating the
    # docker image
    _run('git branch master origin/master || true')
    fork_point_sha = _run('git merge-base --fork-point master HEAD')
    dev_build = bool(head_sha != fork_point_sha)

    # determine date of reference commit
    try:
        commit_time = float(_run(
            "git show -s --pretty='%ct' {}".format(fork_point_sha)))
    except (RuntimeError, ValueError) as exc:
        raise RuntimeError('failed to determine commit date of {}: {}'.format(
            fork_point_sha, str(exc)))
    date_obj = datetime.utcfromtimestamp(commit_time)

    # build version string, remove leading zeroes
    version = '{}.{}.{}'.format(
        date_obj.strftime('%y'), date_obj.strftime('%m%d').lstrip('0'),
        date_obj.strftime('%H%M').lstrip('0')
    )
    # dev build: add dev version string
    if dev_build:
        # this scheme allows setuptools to recognize the dev version as newer
        # than the official version for upgrades in devel environment.
        version += '+dev{}'.format(head_sha[:7])

    return version
# gen_version()

if __name__ == '__main__':
    # do not generate AUTHORS file
    os.environ['SKIP_GENERATE_AUTHORS'] = '1'
    # do not generate ChangeLog file
    os.environ['SKIP_WRITE_GIT_CHANGELOG'] = '1'
    # do not include everything in tarball
    #os.environ['SKIP_GIT_SDIST'] = '1'
    # use date based versioning scheme
    os.environ['PBR_VERSION'] = gen_version()

    # entry point to setup actions
    setup(
        setup_requires=['pbr>=1.8.0', 'setuptools>=17.1.1'],
        pbr=True,
    )
