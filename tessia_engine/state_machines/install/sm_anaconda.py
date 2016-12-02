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
Machine for auto installation of Anaconda based operating systems
"""

#
# IMPORTS
#
from tessia_baselib.common.ssh.client import SshClient
from tessia_engine.state_machines.install.sm_base import SmBase
from time import sleep

import crypt

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class SmAnaconda(SmBase):
    """
    State machine for Anaconda installer
    """
    def __init__(self, os_entry, profile_entry, template_entry):
        """
        Constructor
        """
        super().__init__(os_entry, profile_entry, template_entry)
    # __init__()

    def collect_info(self):
        """
        See SmBase for docstring.
        """
        # collect repos, volumes, ifaces
        super().collect_info()

        # add our specific bits
        self._info["sha512rootpwd"] = crypt.crypt(
            self._profile.credentials["password"])
        self._info['hostname'] = self._system.hostname
    # collect_info()

    def _get_kargs(self):
        """
        Return the cmdline used for the os installer

        Returns:
            str: kernel cmdline string
        """
        repo = self._os.repository_rel

        repo_url = repo.url
        hostname = self._profile.system_rel.hostname
        ip_addr = self._gw_iface['ip']
        gateway_ip = self._gw_iface['gateway']
        iface_osname = self._gw_iface['osname']
        nameserver = self._gw_iface['dns_1']

        cmdline = repo.cmdline.format(
            repo=repo_url, ip=ip_addr, gateway=gateway_ip,
            hostname=hostname, iface_name=iface_osname,
            nameserver=nameserver, autofile=self._autofile_url)

        return cmdline
    # _get_kargs()

    def wait_install(self):
        """
        Waits for the installation, this method periodically checks the
        /tmp/anaconda.log file in the system and looks for a string that
        indicates that the process has finished. There is a timeout of 10
        minutes.
        """
        timeout_trials = [5, 10, 20, 40]

        ssh_client = SshClient()
        hostname = self._profile.system_rel.hostname
        user = self._profile.credentials['username']
        password = self._profile.credentials['password']
        for timeout in timeout_trials:
            try:
                ssh_client.login(hostname, user, password)
            except ConnectionError:
                print("warning: connection not available yet, "
                      "retrying in {} seconds.".format(timeout))
                sleep(timeout)

        shell = ssh_client.open_shell()
        timeout_installation = 600
        frequency_check = 10
        termination_string = "Thread Done: AnaConfigurationThread"
        initial_line = 1
        cmd_read_line = "tail -n +{} /tmp/anaconda.log"
        elapsed_time = 0
        # Performs successive calls to tail to extract the end of the file
        # from a previous start point.
        while elapsed_time < timeout_installation:
            ret, out = shell.run(cmd_read_line.format(initial_line))
            if ret != 0:
                print("Error while reading the installation log.")
                return False
            lines = out.split("\n")
            if len(lines) > 1 or lines[0] != "":
                initial_line += len(lines)
                print(out)
            if out.find(termination_string) != -1:
                return True
            sleep(frequency_check)
            elapsed_time += frequency_check
    # wait_install()

# SmAnaconda
