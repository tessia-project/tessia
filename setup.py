#!/usr/bin/python3
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
from setuptools import setup

import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

# do not generate AUTHORS file
os.environ['SKIP_GENERATE_AUTHORS'] = '1'
# do not generate ChangeLog file
os.environ['SKIP_WRITE_GIT_CHANGELOG'] = '1'
# do not include everything in tarball
#os.environ['SKIP_GIT_SDIST'] = '1'

# entry point to setup actions
setup(
    setup_requires=['pbr>=1.8.0', 'setuptools>=17.1.1'],
    pbr=True,
)
