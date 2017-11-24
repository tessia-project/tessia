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
from setuptools import find_packages, setup

import os
import re
import subprocess
import sys

#
# CONSTANTS AND DEFINITIONS
#
MY_DIR = os.path.dirname(os.path.abspath(__file__))
# shared with pip-install to allow 'pip install' to work
VERSION_FILE = '{}/VERSION'.format(MY_DIR)

# metadata information
AUTHOR = 'IBM'
CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: Apache Software License',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Topic :: System :: Hardware :: Mainframes',
    'Topic :: System :: Installation/Setup',
    'Topic :: System :: Systems Administration',
]
DESCRIPTION = 'tessia command line client'
LICENSE = 'Apache 2.0'
with open('README.md', 'r') as desc_fd:
    LONG_DESCRIPTION = desc_fd.read()
LONG_DESC_TYPE = 'text/markdown'
KEYWORDS = 'client tessia'
NAME = 'tessia-cli'
URL = 'https://gitlab.com/tessia-project'

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

def _find_data_files(dir_name, pkg_data=True):
    """
    List all (pkg or non pkg) data files

    Args:
        dir_name (str): directory to perform search
        pkg_data (bool): whether the files are in the package

    Returns:
        list: data files
    """
    data_files = []
    for entry in os.walk(dir_name):
        # cache dir or normal python package: skip it
        if entry[0].split('/')[-1] == '__pycache__' or (
                pkg_data and '__init__.py' in entry[2]):
            continue

        for filename in entry[2]:
            # (non pkg) data file: use complete path
            if not pkg_data:
                data_files.append(os.path.join(entry[0], filename))
                continue

            data_files.append(
                os.path.join(entry[0].split('/', 1)[1], filename))

    return data_files

# _find_data_files()

def _find_requirements():
    """
    List all installation requirements

    Returns:
        list: installation requirements
    """
    with open('requirements.txt', 'r') as req_fd:
        lines = req_fd.readlines()
    req_list = []
    for line in lines:
        # comment or empty line: skip it
        if not line.strip() or re.match('^ *#', line):
            continue

        # url format: need to extract requirement name
        if '://' in line:
            egg_index = line.find('#egg=')
            # no egg specifier present: requirement cannot be converted to
            # setuptools format
            if egg_index == -1:
                print('warning: excluding requirement {}'.format(line),
                      file=sys.stderr)
                continue
            line = line[egg_index+5:]
        req_list.append(line)

    return req_list
# _find_requirements()

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
    if not os.path.exists('{}/../.git'.format(MY_DIR)):
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r') as file_fd:
                version = file_fd.read()
            return version
        return '0.0.0+unknown'

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
    # entry point to setup actions
    setup(
        # metadata information
        author=AUTHOR,
        classifiers=CLASSIFIERS,
        description=DESCRIPTION,
        keywords=KEYWORDS,
        license=LICENSE,
        long_description=LONG_DESCRIPTION,
        long_description_content_type=LONG_DESC_TYPE,
        name=NAME,
        # installation information
        entry_points={
            'console_scripts': [
                'tess = tessia.cli.main:main'
            ]
        },
        install_requires=_find_requirements(),
        package_data={'': _find_data_files('tessia')},
        packages=find_packages(exclude=['tests', 'tests.*']),
        setup_requires=['setuptools>=30.3.0'],
        url=URL,
        version=gen_version(),
        zip_safe=False,
    )
