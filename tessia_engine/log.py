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
Module to provide custom logging classes for specific needs
"""

#
# IMPORTS
#
from logging.handlers import RotatingFileHandler

import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class CreateDirRotatingFileHandler(RotatingFileHandler):
    """
    Same as RotatingFileHandler but tries to create the directory for the
    target log file on initialization to avoid 'no such file or directory'.
    """

    def __init__(self, filename, *args, **kwargs):
        """
        Constructor, verifies if the directory for the target file exists and
        if not tries to create it.

        Args:
            filename (str): path where to create log file
            args (tuple): args to pass to parent class
            kwargs (tuple): keyword args to pass to parent class

        Raises:
            NotImplementedError as the class should not be instantiated
        """
        # virtual env active: place files there
        virtual_env = os.environ.get('VIRTUAL_ENV')
        if virtual_env is not None:
            filename = '{}/{}'.format(virtual_env, filename)

        os.makedirs(os.path.abspath(os.path.dirname(filename)), exist_ok=True)
        super().__init__(filename, *args, **kwargs)
    # __init__()
# CreateDirRotatingFileHandler
