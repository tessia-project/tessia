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
from setuptools import find_packages, setup

import os
import re
import subprocess
import sys

#
# CONSTANTS AND DEFINITIONS
#
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
DESCRIPTION = (
    'tessia - Task Execution Supporter and System Installation Assistant')
LICENSE = 'Apache 2.0'
with open('README.md', 'r') as desc_fd:
    LONG_DESCRIPTION = desc_fd.read()
LONG_DESC_TYPE = 'text/markdown'
KEYWORDS = 'automation ibmz installation guest hypervisor'
NAME = 'tessia'
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
    Return a PEP440 compliant version, possible values:
    Tagged commit:
        {tag}
    Tagged commit with local changes:
        {tag}.dev0+g{commit_id}.dirty
    Post tagged commit:
        {tag}.post{commit_qty}.dev0+g{commit_id}
    Post tagged commit with local changes:
        {tag}.post{commit_qty}.dev0+g{commit_id}.dirty
    No tag found:
        0.post{commit_qty}.dev0+g{commit_id}
    No tag found with local changes:
        0.post{commit_qty}.dev0+g{commit_id}.dirty
    No git available, parse errors:
        0+unknown

    Returns:
        str: the calculated version
    """
    unknown_version = '0+unknown'

    try:
        version_fields = _run(
            'git describe --long --tags --dirty --always').strip().split('-')
    except RuntimeError:
        return unknown_version

    fields_qty = len(version_fields)
    # unexpected output: return unknown version
    if fields_qty == 0:
        return unknown_version

    # collect the values that compose the version
    fields_map = {
        'dirty': '',
        'tag': '0',
        'commit_qty': '',
        'commit_id': ''
    }

    # local changes exist: mark it in the version
    if version_fields[-1] == 'dirty':
        fields_map['dirty'] = '.dirty'
        version_fields.pop(-1)
        fields_qty -= 1

    # tagged or post tagged commit
    if fields_qty >= 3:
        # processing fields backwards allows to correctly handle tags
        # containing hyphens
        fields_map['commit_id'] = version_fields[-1]
        fields_map['commit_qty'] = version_fields[-2]
        fields_map['tag'] = '-'.join(version_fields[:-2])
    # no tag found
    elif fields_qty == 1:
        fields_map['commit_id'] = 'g{}'.format(version_fields[0])
        try:
            fields_map['commit_qty'] = _run(
                'git rev-list --count HEAD').strip()
        except RuntimeError:
            return unknown_version
    # unexpected output
    else:
        return unknown_version

    # commit matches the tag: skip additional fields
    if fields_map['commit_qty'] == '0':
        if fields_map['dirty']:
            final_version = '{tag}.dev0+{commit_id}{dirty}'
        else:
            final_version = '{tag}'
    else:
        final_version = '{tag}.post{commit_qty}.dev0+{commit_id}{dirty}'

    return final_version.format(**fields_map)
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
        data_files=[('etc/tessia', _find_data_files('etc', False))],
        entry_points={
            'console_scripts': [
                'tess-dbmanage = tessia.server.db.cmd:main',
                'tess-api = tessia.server.api.cmd:main',
                'tess-scheduler = tessia.server.scheduler.cmd:main',
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
