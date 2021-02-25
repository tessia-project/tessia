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
Machine for auto installation of debian based operating systems.
"""

#
# IMPORTS
#
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from tessia.server.state_machines.autoinstall.sm_base import SmBase
from time import time
from time import sleep
from urllib.parse import urlparse

import logging

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class SmDebianInstaller(SmBase):
    """
    State machine for DebianInstaller installer
    """
    # the type of linux distribution supported
    DISTRO_TYPE = 'debian'

    def __init__(self, model: AutoinstallMachineModel,
                 platform: PlatBase, *args, **kwargs):
        """
        Constructor
        """
        super().__init__(model, platform, *args, **kwargs)
        self._logger = logging.getLogger(__name__)
    # __init__()

    @staticmethod
    def _add_systemd_osname(iface):
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
        iface["systemd_osname"] = (
            "enc{}".format(ccwgroup[0].lstrip('.0'))
        )
    # _add_systemd_osname()

    def _read_logfile(self, shell, logfile_path):
        """
        Read the Ubuntu installation log file and presents it in the
        state machine log.

        Args:
            shell (SshShell): an open ssh shell.
            logfile_path (str): Path to the log file.

        Returns:
            bool: True if the termination string can be found in the log file
                  , False otherwise.
        """
        cmd_read_line = "tail -n +{} " + logfile_path + " | head -n 100"
        termination_string = (
            "Running /usr/lib/finish-install.d/20final-message")

        # Maximum time to wait for the installation process.
        max_wait_install = 3600
        timeout_installation = time() + max_wait_install
        line_offset = 1
        success = False
        frequency_check = 10
        # Performs consecutive calls to tail to extract the end of the file
        # from a previous start point. It is important to notice that the
        # Debian Installer does not provide concise error messages so that
        # is not possible to look for error in the installation process.
        while time() <= timeout_installation:
            _, out = shell.run(cmd_read_line.format(line_offset))

            out = out.rstrip('\n')
            if not out:
                sleep(frequency_check)
                continue

            line_offset += len(out.split('\n'))
            self._logger.info(out)

            if out.find(termination_string) != -1:
                success = True
                break

        return success
    # _read_logfile()

    @staticmethod
    def _wait_install_logfile(shell, logfile_path):
        """
        Waits for the installation log file to be created.

        Args:
            shell (SshShell): an open ssh shell.
            logfile_path (str): Path to the log file.

        Raises:
            TimeoutError: In case the log file is not created in 120s.
        """
        frequency_check = 10
        max_wait_log_file = 120
        # wait for log file to be available
        timeout_logfile = time() + max_wait_log_file
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
    # _wait_install_log_file()

    @staticmethod
    def _convert_fs(fs_name):
        """
        Convert the filesystem name to a name valid for parted.

        Args:
            fs_name (str): filesystem name

        Returns:
            str: the filesystem name adapted for parted
        """
        # adapt fs name for parted
        if fs_name in ('ext2', 'ext3', 'ext4'):
            fs_name = 'ext2'
        elif fs_name == 'swap':
            fs_name = 'linux-swap'

        return fs_name
    # _convert_fs()

    def collect_info(self):
        """
        See SmBase for docstring.
        """
        # collect repos, volumes, ifaces
        super().collect_info()

        # Gather the device numbers of the disks and the paths
        # (denov, wwpn, lun).
        for svol in self._info["svols"]:
            try:
                svol["part_table"]["type"]
            except (TypeError, KeyError):
                continue

            part_table = svol['part_table']

            if part_table["type"] == "msdos":
                part_table["table"].sort(
                    key=lambda x: 0 if x['type'] == 'primary' else 1
                )
                # This will accumulate the size until now
                size = 0
                for i in range(len(part_table["table"])):
                    part = part_table["table"][i]
                    if part['type'] == 'logical':
                        part_table["table"].insert(
                            i, {
                                'type': 'extended',
                                "size": (svol['size'] - size),
                                'fs': "",
                                'mo': None,
                                'mp': None
                            })
                        break
                    size += part['size']

            ref_size = 1
            part_index = 1

            for part in part_table["table"]:
                part['start'] = ref_size
                # In case the partition table is not msdos
                part.setdefault('type', '')
                # There is only primary/extended/logical partitions for msdos
                # msdos part table.
                if part_table['type'] != 'msdos':
                    part['type'] = ''
                part['end'] = ref_size + part['size']
                part['parted_fs'] = self._convert_fs(part['fs'])
                part['device'] = (svol['system_attributes']['device']
                                  + '-part{}'.format(part_index))
                # multipath partitions follow a different rule to name the
                # devices
                if (svol['type'] == 'FCP' and svol['specs']['multipath']
                        and self._info['system_type'] != 'KVM'):
                    part['device'] = (
                        "/dev/disk/by-id/dm-uuid-part{}-mpath-{}".format(
                            part_index, svol['specs']['wwid']))

                if part['type'] == 'extended':
                    ref_size += 1
                    part_index = 5
                else:
                    ref_size += part['size']
                    part_index += 1

            if svol['is_root']:
                self._info['root_disk'] = svol

        # Gather the device numbers of the OSA interfaces.
        for iface in self._info["ifaces"] + [self._info['gw_iface']]:
            if iface["type"] == "OSA":
                self._add_systemd_osname(iface)

        # It is easier to get the following information here than in the
        # template.
        for repo in self._info['repos']:
            parsed_result = urlparse(repo['url'])
            repo['debian_protocol'] = parsed_result.scheme
            repo['debian_netloc'] = parsed_result.netloc
            repo['debian_path'] = parsed_result.path
            # install repository url: no parsing needed
            if repo['os']:
                continue
            try:
                root_path, comps = repo['url'].split('/dists/', 1)
            except ValueError:
                raise ValueError(
                    "Repository URL <{}>  is in invalid format, no '/dists/' "
                    "component found".format(repo['url']))
            repo['apt_url'] = '{} {}'.format(
                root_path, comps.replace('/', ' ')).rstrip()
    # collect_info()

    def wait_install(self):
        """
        Waits for the installation. This method periodically checks the
        /tmp/anaconda.log file in the system and looks for a string that
        indicates that the process has finished. There is a timeout of 10
        minutes.
        """
        ssh_client, shell = self._get_ssh_conn()

        logfile_path = '/var/log/syslog'

        self._wait_install_logfile(shell, logfile_path)
        success = self._read_logfile(shell, logfile_path)

        shell.close()
        ssh_client.logoff()

        if not success:
            raise TimeoutError('Installation Timeout: The installation'
                               ' process is taking too long')

        return success
    # wait_install()
# SmDebianInstaller
