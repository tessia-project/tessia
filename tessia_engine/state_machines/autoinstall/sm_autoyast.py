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
from tessia_engine.state_machines.autoinstall.sm_base import SmBase
from time import sleep
from time import time

import crypt
import jinja2
import logging


#
# CONSTANTS AND DEFINITIONS
#

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

    def _fetch_lines_until_end(self, shell, offset, logfile_path):
        """
        Auxiliar function to read lines from a file and log them in chunks
        until the last line.
        """
        cmd_read_line = "tail -n +{offset} {file_path} | head -n 100"
        while True:
            ret, out = shell.run(cmd_read_line.format(
                offset=offset, file_path=logfile_path))
            out = out.rstrip('\n')
            # something went wrong: stop to prevent an infinite loop
            if ret == 1:
                break
            # reached end of file: stop
            elif not out:
                break

            offset += len(out.split('\n'))
            self._logger.info(out)

        return offset
    # _fetch_lines_until_end()

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

    def check_installation(self):
        """
        Make sure that the installation was successfully completed.
        """
        # autoyast performs the installation in two stages so we need to make
        # sure the second stage has finished before we perform the actual check
        ssh_client, shell = self._get_ssh_conn()

        try:
            ret, _ = shell.run('systemctl status YaST2-Second-Stage')
        except Exception:
            ret = 1
        if ret == 0:
            self._logger.info('Waiting for AutoYast stage 2 to finish')
            while True:
                sleep(0.5)
                try:
                    shell.run('true', timeout=5)
                # connection lost - so system already rebooted to the final
                # state
                except Exception:
                    break

        self._logger.info('AutoYast stage 2 finished')
        shell.close()
        ssh_client.logoff()

        super().check_installation()
    # check_installation()

    def collect_info(self):
        """
        See SmBase for docstring.
        """
        # collect repos, volumes, ifaces
        super().collect_info()
        self._logger.info(
            'auto-generated password for VNC is %s',
            self._info['credentials']['vncpasswd'])

        self._info["hostname"] = self._system.hostname
        self._info["autofile"] = self._autofile_url
        self._info["gw_iface"] = self._gw_iface
        self._info["sha512rootpwd"] = crypt.crypt(
            self._profile.credentials["passwd"])
    # collect_info()

    def target_reboot(self):
        """
        With AutoYast this stage is a nop since the installer automatically
        kexecs into the installed system.
        """
        # kvm guest installation: kexec does not work, perform normal reboot
        if self._system.type == 'KVM':
            self._logger.info("Rebooting into installed system")
            super().target_reboot()
            return

        # for other system types it's possible to let sles perform a kexec
        # which is faster than reboot
        self._logger.info("Kexec'ing into installed system")
        ssh_client, shell = self._get_ssh_conn()
        # Kill shell so AutoYast can kexec to installed system
        kill_cmd = (
            "kill -9 $(ps --no-header -o pid --ppid=`pgrep 'inst_setup'`)")
        try:
            shell.run(kill_cmd, timeout=1)
        except TimeoutError:
            pass
        shell.close()
        ssh_client.logoff()

        # wait a while before moving to next stage to be sure no connection is
        # made still to installer environment.
        sleep(5)
    # target_reboot()

    def wait_install(self):
        """
        Waits for the installation end. This method periodically checks if
        the YaST process is still running while also extracts installation
        logs. There is a timeout of 10 minutes.
        """
        ssh_client, shell = self._get_ssh_conn()

        # Under SLES, we use the cmdline parameter 'start_shell' that
        # starts a shell before and after the autoyast.
        # This is required to control when the installer will reboot.
        kill_cmd = (
            "kill -9 $(ps --no-header -o pid --ppid=`pgrep 'inst_setup'`)")

        # Kill shell so installation can start
        ret, _ = shell.run(kill_cmd)
        if ret != 0:
            self._logger.error(
                "Error while killing shell before installation start")
            raise RuntimeError("Command Error: ret={}".format(ret))

        logfile_path = '/var/log/YaST2/y2log'
        frequency_check = 10

        # wait for log file to be available, it takes a while
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

        # performs successive calls to extract the installation log
        # and check installation stage
        line_offset = 1
        timeout_installation = time() + 600
        success = False
        while time() <= timeout_installation:
            line_offset = self._fetch_lines_until_end(
                shell, line_offset, logfile_path)

            # installation finished: consume last lines from log and finish
            # process
            ret, _ = shell.run("pgrep '^yast2'")
            if ret != 0:
                self._fetch_lines_until_end(shell, line_offset, logfile_path)
                success = True
                break

            sleep(frequency_check)

        shell.close()
        ssh_client.logoff()

        if not success:
            raise TimeoutError('Installation Timeout: The installation '
                               'process is taking too long')

        self._logger.info("AutoYast stage 1 finished")
    # wait_install()
# SmAutoyast
