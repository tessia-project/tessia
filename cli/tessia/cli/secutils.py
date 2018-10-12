# Copyright 2018 IBM Corp.
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
Miscellaneous utility functions that can be used by other modules to improve
security.
"""

#
# IMPORTS
#
import os
import stat

#
# CONSTANTS AND DEFINITIONS
#
DEFAULT_DIR_MODE = 0o700
DEFAULT_UMASK = 0o077

#
# CODE
#

def is_file_private(path):
    """
    Function to verify if file or directory is only accessible by the owner.

    Args:
        path (str): Path of the directory or file

    Returns:
        bool: Returns True if access rights are only set for the owner of the
        file otherwise False is returned.
    """
    return not bool(os.stat(path).st_mode
                    & (stat.S_IRWXG | stat.S_IRWXO))
# is_file_private()

def makedirs_private(name, exist_ok=False):
    """
    Recursive directory creation function which makes sure only the
    creator has access to it.

    Args:
        name (str): Path of the directories
        exist_ok (bool): Won't raise exception if directory exists and has
                  proper access rights

    Raises:
        PermissionError: if created directory exists and has wrong
                         permissions
    """
    old_mask = os.umask(DEFAULT_UMASK)
    try:
        os.makedirs(name, DEFAULT_DIR_MODE, exist_ok)
        if exist_ok and not is_file_private(name):
            raise PermissionError(
                "{} could be accessible for others!".format(name)
            )
    finally:
        os.umask(old_mask)
# mkdirs_private()

def open_private_file(file_path, *args, **kwargs):
    """
    Function to open a file which verifies that the file opened or created
    is only readable for the owner of the file.

    Args:
        file_path (str): Path and filename
        args (list): Used to forward arguments to os.open()
        kwargs (dict): Used to forward arguments to os.open()

    Raises:
        PermissionError: if opened or created file has wrong permissions

    Returns:
        int: Return the file descriptor for the newly opened file. Also see
        os.open() documentation.
    """
    old_mask = os.umask(DEFAULT_UMASK)
    try:
        fd_file = open(file_path, *args, **kwargs)
        if not is_file_private(file_path):
            raise PermissionError(
                "{} could be accessible for others!\n"
                "Change permissions to allow owner access only!"
                .format(file_path)
            )
    finally:
        os.umask(old_mask)
    return fd_file
# open_private_file()
