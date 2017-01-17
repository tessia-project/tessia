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
Machine for auto installation of Anaconda based operating systems.
"""

#
# IMPORTS
#
from tessia_baselib.common.ssh.client import SshClient
from tessia_engine.state_machines.install.sm_base import SmBase
from time import sleep

import crypt
import jinja2
import logging

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
        self._logger = logging.getLogger(__name__)
    # __init__()

    @staticmethod
    def _add_systemd_osname(iface):
        """
        Determine and add a key to the iface dict representing the kernel
        device name used by the installer for the given network interface

        Args:
            iface (dict): network interface information dict

        Returns:
            None
        """
        devicenr = iface['attributes']["devicenr"].split(",")
        # The control read device number is used to create a predictable
        # device name for OSA network interfaces (for details see
        # https://www.freedesktop.org/wiki/Software/systemd/
        # PredictableNetworkInterfaceNames/)
        iface["systemd_osname"] = (
            "enccw0.0.{}".format(devicenr[0].lstrip("0x"))
        )
    # _add_systemd_osname()

    def collect_info(self):
        """
        See SmBase for docstring.
        """
        # collect repos, volumes, ifaces
        super().collect_info()

        # add our specific bits
        self._info["credentials"] = self._profile.credentials
        self._info["sha512rootpwd"] = crypt.crypt(
            self._profile.credentials["password"])
        self._info['hostname'] = self._system.hostname

        for iface in self._info["ifaces"]:
            if iface["type"] == "OSA":
                self._add_systemd_osname(iface)
    # collect_info()

    def _get_kargs(self):
        """
        Return the cmdline used for the os installer

        Returns:
            str: kernel cmdline string
        """
        hostname = self._profile.system_rel.hostname

        template_cmdline = jinja2.Template(self._os.cmdline)

        cmdline = template_cmdline.render(
            repo=self._repo.url,
            gw_iface=self._gw_iface,
            hostname=hostname,
            autofile=self._autofile_url,
            config=self._info)

        return cmdline
    # _get_kargs()

    def _get_ssh_client(self):
        """
        Auxiliary method to get a ssh connection to the target system
        being installed.
        """
        timeout_trials = [5, 10, 20, 40]

        ssh_client = SshClient()
        hostname = self._profile.system_rel.hostname
        user = self._profile.credentials['username']
        password = self._profile.credentials['password']

        for timeout in timeout_trials:
            try:
                ssh_client.login(hostname, user=user, passwd=password)
                return ssh_client
            except (ConnectionError, ConnectionResetError):
                self._logger.warning("connection not available yet, "
                                     "retrying in %d seconds.", timeout)
                sleep(timeout)

        raise ConnectionError("Error while connecting to the target system")
    # _get_ssh_client()

    def check_installation(self):
        """
        Makes sure that the installation was successfully completed.
        """
        ssh_client = self._get_ssh_client()
        shell = ssh_client.open_shell()

        ret = shell.run("echo 1")
        if ret != 0:
            raise RuntimeError("Unable to connect to the system.")

        shell.close()
        ssh_client.logoff()
    # check_installation()

    def wait_install(self):
        """
        Waits for the installation. This method periodically checks the
        /tmp/anaconda.log file in the system and looks for a string that
        indicates that the process has finished. There is a timeout of 10
        minutes.
        """
        ssh_client = self._get_ssh_client()
        shell = ssh_client.open_shell()

        cmd_read_line = "tail -n +{} /tmp/anaconda.log"
        termination_string = "Thread Done: AnaConfigurationThread"
        initial_line = 1

        timeout_installation = 600
        frequency_check = 10
        elapsed_time = 0

        # Performs successive calls to tail to extract the end of the file
        # from a previous start point.
        success = False
        while elapsed_time < timeout_installation:
            ret, out = shell.run(cmd_read_line.format(initial_line))
            if ret != 0:
                self._logger.error("Error while reading the installation log.")
                return success
            lines = out.split("\n")

            if len(lines) > 1 or lines[0] != "":
                initial_line += len(lines)
                self._logger.info(out)

            if out.find(termination_string) != -1:
                success = True
                break

            sleep(frequency_check)
            elapsed_time += frequency_check

        shell.close()
        ssh_client.logoff()
        return success
    # wait_install()
# SmAnaconda
