# Copyright 2021 IBM Corp.
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
SSH stub

This class provides an SSH client and sessino stub to replace
baselib interaction in unit tests.
"""

# pylint: disable=unused-argument  # stubs may receive extra arguments

#
# IMPORTS
#


#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


class SshShell:
    """
    This class encapsulates the reading from and writing to a file
    object/socket and performing expect work to provide a shell object
    which represents an interactive shell session.
    """

    def __init__(self, responses: dict = None):
        """
        Initialize stub shell with optional responses
        Responses may contain part of command to match

        Args:
            responses: { "query": "response" }, where
                query is a substring of command to match,
                response is a string to return or a tuple
                    (retcode, string)
        """
        self._responses = responses if responses else {}

    def close(self):
        """
        Close the socket. No more operations are possible.
        """

    def run(self, cmd, timeout=120, ignore_ret=False):
        """
        Execute a command and wait timeout seconds for the output. This method
        is the entry point to be consumed by users.
        """
        for query, response in self._responses.items():
            # match a response by a substring
            if query in cmd:
                if isinstance(response, tuple):
                    retcode, _ = response
                    # use retcode < 0 to trigger an exception
                    if retcode < 0:
                        raise RuntimeError(response)
                    return response
                return 0, response

        return 0, cmd


class SshClient:
    """
    This class provides a client for SSH communication and encapsulates the
    implementation details of the underlying library used.
    """

    def __init__(self):
        """
        Constructor. Initializes object variables and logging
        """

    def change_file_permissions(self, file_path, file_perms):
        """
        Change permissions of a file in the target system.
        Always succeeds.
        """

    def login(self, host_name, port=22, user=None, passwd=None,
              private_key_str=None, timeout=60):
        """
        Establishes a connection to the target system.
        Always succeeds.
        """

    def logoff(self):
        """
        Close connection to target system.
        Always succeeds.
        """

    def open_file(self, file_path, mode):
        """
        Open a file on the target system.
        Currently not implemented
        """
        raise NotImplementedError

    def open_shell(self, chroot_dir=None, shell_path=None):
        """
        Open an interactive shell and return an expect-like object. Optionally
        accepts a directory to perform chroot.

        Always succeeds, returns an SshShell stub
        """
        return SshShell()

    def path_exists(self, check_path):
        """
        Verifies if a given path exists on system (it does)
        """
        return True

    def pull_file(self, source_file_path, target_url, write_mode='wb'):
        """
        Retrieve a file from this ssh host through sftp and copy it to the
        target url.
        Always succeeds, nothing is copied.
        """

    def push_file(self, source_url, target_file_path, write_mode='wb'):
        """
        Retrieve a file from source_url and copy it to a file on this
        ssh host.
        Always succeeds, nothing is copied.
        """
