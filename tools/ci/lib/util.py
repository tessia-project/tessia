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
Miscellaneous auxiliary utilities
"""

#
# IMPORTS
#
import os
import time
import subprocess

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class Shell(object):
    """
    Simple wrapper for executing local commands in a shell environment.
    """
    def __init__(self, verbose=False):
        """
        Constructor, sets verbosity (if True means to print all command strings
        and their output)

        Args:
            verbose (bool): if True all commands and output will be printed to
                            stdout
        """
        self._verbose = verbose
    # __init__()

    def run(self, cmd, error_msg=None, stdout=None, env=None):
        """
        Execute a local command in a shell environment.

        Args:
            cmd (str): command to execute
            error_msg (str): if not None then raise an exception with that msg
                             in case the command returns exit code != 0
            stdout (bool): if True will print the output consumed to stdout
            env (dict): run using this map of environment variables

        Returns:
            tuple: (int_exit_code, str_output)

        Raises:
            RuntimeError: if error_msg is not None and exit code != 0
        """
        if self._verbose:
            print('$ ' + cmd)
        # print stdout if verbose was set and stdout was not explicitly disabled
        # or if stdout was explicitly enabled
        print_stdout = bool((self._verbose and stdout is not False) or stdout)
        proc = subprocess.Popen(
            ['bash', '-c', cmd], stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, universal_newlines=True, env=env)
        # read from pipe in an non-blocking way to avoid hanging in ssh related
        # commands (i.e. git clone) due to stderr left open by ssh
        # controlpersist background process
        # (https://bugzilla.mindrot.org/show_bug.cgi?id=1988)
        os.set_blocking(proc.stdout.fileno(), False)
        output = ''
        while True:
            output_buffer = proc.stdout.readline()
            if not output_buffer:
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
                continue
            if print_stdout:
                print(output_buffer, end='', flush=True)
            output += output_buffer

        if proc.returncode != 0 and error_msg is not None:
            raise RuntimeError('{}\ncmd: {}\noutput: {}\n'.format(
                error_msg, cmd, output))

        return proc.returncode, output
    # run()
# Shell

def build_image_map():
    """
    Parse the set of images available for building.
    """
    image_map = {}

    my_dir = os.path.dirname(os.path.abspath(__file__))
    docker_dir = os.path.abspath('{}/../docker'.format(my_dir))
    for entry in os.listdir(docker_dir):
        # fetch image description
        try:
            with open('{}/{}/description'.format(
                docker_dir, entry)) as file_fd:
                desc = file_fd.read()
        # description not accessible: not an image dir, skip it
        except IOError:
            continue
        image_map[entry] = desc.strip()

    return image_map
# build_image_map()
