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
Package containing the machines used to execute jobs
"""

#
# IMPORTS
#
from importlib.machinery import SourceFileLoader
import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class _MachineManager(object):
    _singleton = False

    def __init__(self):
        """
        Constructor, defines internal variables.
        """
        # current directory of this module
        self._my_dir = os.path.dirname(os.path.abspath(__file__))

        # list of machine names
        self._names = None
        # map of machine classes keyed by name
        self._classes = None
    # __init__()

    def __new__(cls, *args, **kwargs):
        """
        Modules should not try to instantiate this class.

        Args:
            None

        Returns:
            _MachineManager: object instance

        Raises:
            NotImplementedError: as the class should not be instantiated
        """
        if cls._singleton:
            raise NotImplementedError('Class should not be instantiated')
        cls._singleton = True

        return super().__new__(cls, *args, **kwargs)
    # __new__()

    def _load_classes(self):
        """
        Create a dict of machine classes keyed by name.
        """
        # already loaded: nothing to do
        if self._classes is not None:
            return

        # make sure names are loaded
        self._load_names()

        # create the dict by loading each machine module
        self._classes = {}
        for machine_name in self._names:
            package_path = '{}/{}/__init__.py'.format(
                self._my_dir, machine_name)

            # syntax error could occur here
            package = SourceFileLoader(
                machine_name, package_path).load_module()

            self._classes[machine_name] = package.MACHINE
    # _load_classes()

    def _load_names(self):
        """
        Load the list of machine names. We consider the python package name
        (directory name) as the machine name to be externalized to
        api/scheduler.
        """
        # already loaded: nothing to do
        if self._names is not None:
            return
        self._names = []

        for sub_dir in os.listdir(self._my_dir):
            # not a valid package: skip it
            if sub_dir.startswith('_'):
                continue

            base_path = '{}/{}'.format(self._my_dir, sub_dir)
            # not a package: skip it
            if (not os.path.isdir(base_path) or
                    not os.path.exists('{}/__init__.py'.format(base_path))):
                continue

            self._names.append(sub_dir)
    # _load_names()

    @property
    def classes(self):
        """
        Return the dict containing the machine names and classes
        """
        self._load_classes()
        return self._classes

    @property
    def names(self):
        """
        Return the list containing the machine names
        """
        self._load_names()
        return self._names
# _MachineManager

MACHINES = _MachineManager()
