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
Machine for auto installation of Autoyast based operating systems
"""

#
# IMPORTS
#
from tessia_engine.state_machines.install.sm_base import SmBase

import jinja2
import logging
from time import sleep


#
# CONSTANTS AND DEFINITIONS
#

INSTALLATION_TIMEOUT = 600
CHECK_INSTALLATION_FREQ = 10
LOGFILE_PATH = "/var/log/YaST2/y2log"

#
# CODE
#
class SmAutoyast(SmBase):
    """
    State machine for Autoyast installer
    """
    def __init__(self, os_entry, profile_entry, template_entry):
        """
        Constructor
        """
        super().__init__(os_entry, profile_entry, template_entry)
        self._logger = logging.getLogger(__name__)
    # __init__()

    def collect_info(self):
        """
        See SmBase for docstring.
        """
        # collect repos, volumes, ifaces
        super().collect_info()

        self._info["hostname"] = self._system.hostname
        self._info["autofile"] = self._autofile_url
        self._info["gw_iface"] = self._gw_iface

    # collect_info()

    def _get_kargs(self):
        """
        Return the cmdline used for the os installer

        Returns:
            str: kernel cmdline string
        """
        template_cmdline = jinja2.Template(self._os.cmdline)

        cmdline = template_cmdline.render(
            config=self._info
        )

        return cmdline
    # _get_kargs()

    def wait_install(self):
        """
        Waits for the installation end. This method periodically checks if
        the YaST process is still running while also extracts installation
        logs. There is a timeout of 10 minutes.
        """
        initial_line = 1
        elapsed_time = 0
        cmd_read_line = "tail -n +{} " + LOGFILE_PATH

        ssh_client, shell = self._get_ssh_conn()
        # Under SLES, we use the cmdline parameter 'start_shell' that
        # starts a shell before and after the autoyast.
        # This is required to control when the installer will reboot.

        # Kill shell so installation can start
        ret, _ = shell.run(
            "kill -9 $(ps --no-header -o pid --ppid=`pgrep 'inst_setup'`)"
        )
        if ret != 0:
            self._logger.error(
                "Error while killing shell before installation start")
            raise RuntimeError("Command Error: ret={}".format(ret))

        # performs successive calls to extract the installation log
        # and check installation stage
        while elapsed_time < INSTALLATION_TIMEOUT:
            ret, out = shell.run(cmd_read_line.format(initial_line))
            if ret != 0:
                self._logger.error(
                    "Error while reading the installation log:"
                    "ret=%s,out=%s", ret, out
                )
            lines = out.split("\n")

            # extract installation information
            if len(lines) > 1 or lines[0] != "":
                initial_line += len(lines)
                self._logger.info(out)

            # check if installation finished by querying for its process
            ret, out = shell.run("pgrep '^yast2'")
            if out == '':
                break

            sleep(CHECK_INSTALLATION_FREQ)
            elapsed_time += CHECK_INSTALLATION_FREQ
        else:
            raise TimeoutError('Installation Timeout: The installation'
                               ' process is taking too long')

        shell.close()
        ssh_client.logoff()
    # wait_install()
# SmAutoyast
