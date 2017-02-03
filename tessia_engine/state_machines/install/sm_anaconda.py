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
from tessia_engine.state_machines.install.sm_base import SmBase
from time import time
from time import sleep

import crypt
import jinja2
import logging
import re

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
        ccwgroup = iface['attributes']["ccwgroup"].split(",")
        # The control read device number is used to create a predictable
        # device name for OSA network interfaces (for details see
        # https://www.freedesktop.org/wiki/Software/systemd/
        # PredictableNetworkInterfaceNames/)
        iface["systemd_osname"] = (
            "enccw{}".format(ccwgroup[0])
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

    def wait_install(self):
        """
        Waits for the installation. This method periodically checks the
        /tmp/anaconda.log file in the system and looks for a string that
        indicates that the process has finished. There is a timeout of 10
        minutes.
        """
        ssh_client, shell = self._get_ssh_conn()

        cmd_read_line = "tail -n +{} /tmp/anaconda.log"
        termination_string = "Thread Done: AnaConfigurationThread"
        # re to match errors with partitioning scheme
        part_error_regex = re.compile(
            r'^.* ERR anaconda: storage configuration failed: *(.*)$',
            re.MULTILINE
        )
        line_offset = 1

        timeout_installation = time() + 600
        frequency_check = 10

        # Performs consecutive calls to tail to extract the end of the file
        # from a previous start point.
        success = False
        while time() <= timeout_installation:
            ret, out = shell.run(cmd_read_line.format(line_offset))
            if ret != 0:
                raise RuntimeError("Error while reading the installation log.")

            out = out.rstrip('\n')
            if len(out) == 0:
                continue

            line_offset += len(out.split('\n'))
            self._logger.info(out)

            if out.find(termination_string) != -1:
                success = True
                break

            match = part_error_regex.search(out)
            if match is not None:
                raise RuntimeError(
                    'Anaconda storage configuration failed: ' + match.group(1))

            sleep(frequency_check)

        shell.close()
        ssh_client.logoff()

        if not success:
            raise TimeoutError('Installation Timeout: The installation'
                               ' process is taking too long')

        return success
    # wait_install()
# SmAnaconda
