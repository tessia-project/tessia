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
Functions to help working with SELinux enabled distros
"""

#
# IMPORTS
#

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

def is_selinux_enforced():
    """
    Check if SELinux is enforced using the sys-fs.

    Returns:
        bool: Returns True if SELinux is enforced
    """
    try:
        with open('/sys/fs/selinux/enforce', 'r') as file_fd:
            if file_fd.read().strip() == "1":
                return True
    except FileNotFoundError:
        pass
    return False
