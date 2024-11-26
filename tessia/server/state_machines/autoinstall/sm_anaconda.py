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
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from tessia.server.state_machines.autoinstall.sm_base import SmBase
from time import sleep, time

import logging
import re

#
# CONSTANTS AND DEFINITIONS
#
FEDORA_ID = 'Fedora '
RHEL_ID = 'Red Hat Enterprise Linux'

# min memory required for newer anaconda versions
MIN_MIB_MEM = 1280

#
# CODE
#


class SmAnaconda(SmBase):
    """
    State machine for Anaconda installer
    """
    # the type of linux distribution supported
    DISTRO_TYPE = 'redhat'

    def __init__(self, model: AutoinstallMachineModel,
                 platform: PlatBase, *args, **kwargs):
        """
        Constructor
        """
        self._assert_minumum_requirements(model)

        super().__init__(model, platform, *args, **kwargs)
        self._logger = logging.getLogger(__name__)
    # __init__()

    def _add_systemd_osname(self, iface):
        """
        Determine and add a key to the iface dict representing the kernel
        device name used by the installer for the given network interface

        Args:
            iface (dict): network interface information dict
        """
        ccwgroup = iface['attributes']["ccwgroup"].split(",")
        # The control read device number is used to create a predictable
        # device name for OSA network interfaces (for details see
        # https://www.freedesktop.org/wiki/Software/systemd/
        # PredictableNetworkInterfaceNames/)
        if self._os.pretty_name.startswith(RHEL_ID) and self._os.major <= 7:
            iface["systemd_osname"] = "enccw{}".format(ccwgroup[0])
        # with systemd/udev >= 238 newer naming scheme is used
        else:
            iface["systemd_osname"] = "enc{}".format(
                ccwgroup[0].lstrip('.0'))
    # _add_systemd_osname()

    @classmethod
    def _assert_minumum_requirements(cls, model: AutoinstallMachineModel):
        """
        Assert that miminum requrements are satisfied

        Args:
            model: autoinstall machine model

        Raises:
            ValueError: minimum requirements are not met
        """
        os_entry = model.operating_system
        profile_entry = model.system_profile
        # make sure minimum ram is available
        no_ram = bool(
            profile_entry.memory < MIN_MIB_MEM and (
                os_entry.pretty_name.startswith(FEDORA_ID) or
                (os_entry.pretty_name.startswith(RHEL_ID) and
                 (os_entry.major == 7 and os_entry.minor >= 5) or
                 (os_entry.major > 7))
            )
        )
        if no_ram:
            raise ValueError(
                "Installations of '{}' require at least {}MiB of memory"
                .format(os_entry.pretty_name, MIN_MIB_MEM))
    # _assert_minumum_requirements()

    def fill_template_vars(self):
        """
        See SmBase for docstring.
        """
        # collect repos, volumes, ifaces
        super().fill_template_vars()

        for iface in self._info["ifaces"] + [self._info['gw_iface']]:
            if iface["type"] == "OSA":
                self._add_systemd_osname(iface)
    # fill_template_vars()

    def wait_install(self):
        """
        Waits for the installation. This method periodically checks the
        /tmp/anaconda.log file in the system and looks for a string that
        indicates that the process has finished. There is a timeout of 10
        minutes.
        """
        ssh_client, shell = self._get_ssh_conn()

        logfile_path = '/tmp/anaconda.log'
        frequency_check = 10

        # wait for log file to be available
        timeout_logfile = time() + 120
        cmd_logfile_exist = '[ -f "{}" ]'.format(logfile_path)
        ret = 1
        while time() < timeout_logfile:
            ret, _ = shell.run(cmd_logfile_exist)
            if ret == 0:
                break
            sleep(frequency_check)
        if ret != 0:
            raise TimeoutError(
                'Timed out while waiting for installation logfile')

        cmd_read_line = "tail -n +{} " + logfile_path + " | head -n 100"
        termination_string = "Thread Done: AnaConfigurationThread"
        termination_string_fedora_31 = "ui.gui.spokes.installation_progress:" \
                                       " The installation has finished."
        termination_string_rhel_10 = "ui.tui.spokes.installation_progress:" \
                                       " The installation has finished."
        # re to match errors with partitioning scheme
        part_error_regex = re.compile(
            r'^.* ERR anaconda: storage configuration failed: *(.*)$',
            re.MULTILINE
        )

        # Performs consecutive calls to tail to extract the end of the file
        # from a previous start point.
        max_wait_install = 3600
        timeout_installation = time() + max_wait_install
        line_offset = 1
        success = False
        while time() <= timeout_installation:
            ret, out = shell.run(cmd_read_line.format(line_offset))
            out = out.rstrip('\n')
            if not out:
                sleep(frequency_check)
                continue

            line_offset += len(out.split('\n'))
            self._logger.info(out)

            if out.find(termination_string) != -1 or \
                    out.find(termination_string_fedora_31) != -1 or \
                    out.find(termination_string_rhel_10) != -1:
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
