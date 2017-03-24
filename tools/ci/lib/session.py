# Copyright 2017 IBM Corp.
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
Module containing a class for executing commands
"""

#
# IMPORTS
#
from lib.util import Shell
import os
import paramiko
import shutil

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class Session(object):
    """
    Provide an abstracted interface to execute shell commands on a system.
    """
    def __init__(self, hostname, user, passwd, verbose):
        """
        Constructor, set internal variables according to hostname type (local
        vs remote)

        Args:
            hostname (str): target hostname
            user (str): username
            passwd (str): password
            verbose (bool): if True all commands and output will be printed to
                            stdout
        """
        self._hostname = hostname
        self._verbose = verbose
        if self._hostname == 'localhost':
            self._local_shell = Shell(self._verbose)
            self._ssh_client = None
        else:
            self._local_shell = None
            self._ssh_client = self._ssh_connect(hostname, user, passwd)
    # __init__()

    @staticmethod
    def _ssh_connect(host, user, passwd):
        """
        Open a ssh connection to the target host.

        Args:
            host (str): hostname
            user (str): username
            passwd (str): password

        Returns:
            paramiko.SSHClient: object instance
        """
        # create library object with policy to add unknown host keys
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # change default's paramiko channel name to our module structure, it
        # is easier for logging configuration
        ssh_client.set_log_channel(__name__ + '.paramiko')

        # try to connect and let possible exceptions go up
        ssh_client.connect(
            hostname=host,
            username=user,
            password=passwd,
            # disable usage of SSH agent
            allow_agent=False,
            # disable looking for keys in ~/.ssh
            look_for_keys=False
        )

        # store instance values
        return ssh_client
    # _ssh_connect()

    def _local_exec(self, cmd, stdout=False):
        """
        Execute a command locally and return exit status and output

        Args:
            cmd (str): command string to execute
            stdout (bool): whether to print the consumed output to stdout

        Returns:
            tuple: (int_exit_status, str_output)
        """
        return self._local_shell.run(cmd, stdout=stdout)
    # _local_exec()

    def _ssh_exec(self, cmd, stdout=False):
        """
        Execute a command via ssh and return exit status and output

        Args:
            cmd (str): command string to execute
            stdout (bool): whether to print the consumed output to stdout

        Returns:
            tuple: (int_exit_status, str_output)
        """
        if self._verbose:
            print('$ ' + cmd)
        channel = self._ssh_client.get_transport().open_session()
        channel.set_combine_stderr(True)
        channel.exec_command(cmd)
        output = ''
        while True:
            output_buffer = channel.recv(1024)
            output += output_buffer
            # no more data to read
            if len(output_buffer) == 0:
                break
            if self._verbose or stdout:
                print(output_buffer, end='')
        exit_status = channel.recv_exit_status()
        return exit_status, output
    # _ssh_exec()

    def run(self, cmd, stdout=False):
        """
        Execute a command and return exit code and output.

        Args:
            cmd (str): command string to execute
            stdout (bool): whether to print the consumed output to stdout

        Returns:
            tuple: (exit_code, str_stdout)
        """
        if self._hostname == 'localhost':
            return self._local_exec(cmd, stdout)
        return self._ssh_exec(cmd, stdout)
    # run()

    def send(self, local_path, dest_path):
        """
        Copy a local path to a destination path on the system.

        Args:
            local_path (str): source path
            dest_path (str): destination path
        """
        local_path = os.path.abspath(local_path)

        # file copy
        if os.path.isfile(local_path):
            if self._ssh_client is None:
                shutil.copy(local_path, dest_path)
                return

            sftp_client = self._ssh_client.open_sftp()
            sftp_client.put(local_path, dest_path)
            sftp_client.close()
            return

        # directory local copy
        if self._ssh_client is None:
            target_path = '{}/{}'.format(
                dest_path, os.path.basename(local_path))
            shutil.copytree(local_path, target_path)
            return

        # directory copy via ssh
        for dir_path, sub_dirs, sub_files in os.walk(local_path):
            for sub_dir in sub_dirs:
                target_dir = dir_path[len(local_path):] + '/' + sub_dir
                sftp_client.mkdir('{}/{}'.format(dest_path, target_dir))
            for sub_file in sub_files:
                src_file = '{}/{}'.format(dir_path, sub_file)
                target_dir = dir_path[len(local_path):]
                target_file = '{}/{}/{}'.format(
                    dest_path, target_dir, sub_file)
                sftp_client.put(src_file, target_file)
    # send()
# Session
