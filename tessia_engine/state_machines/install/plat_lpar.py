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
Module to deal with operations on LPARs
"""

#
# IMPORTS
#
from tessia_baselib.common.ssh.client import SshClient
from tessia_engine.state_machines.install.plat_base import PlatBase

import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class PlatLpar(PlatBase):
    """
    Handling for KVM guests
    """
    def __init__(self, hyp_profile, guest_profile, os_entry, gw_iface):
        super().__init__(hyp_profile, guest_profile, os_entry, gw_iface)
    # __init__()

    def _get_start_params(self, kargs):
        """
        Return the start parameters specific to LPAR

        Args:
            kargs (str): kernel command line args for os' installer

        Returns:
            dict: in format expected by tessia_baselibs' parameters option
        """
        # repository related information
        repo = self._os.repository_rel
        kernel_uri = os.path.join(repo.url, repo.kernel)
        initrd_uri = os.path.join(repo.url, repo.initrd)

        params = {
            "boot_params": {
                "boot_method": "network",
                "kernel_url": kernel_uri,
                "initrd_url": initrd_uri,
                "cmdline": kargs,
                "mac": self._gw_iface['mac'],
                "ip": self._gw_iface['ip'],
                "gateway": self._gw_iface['gateway'],
                "device": self._gw_iface['attributes']['devicenr'],
            }
        }

        return params
    # _get_start_params()

    def reboot(self, system_profile):
        """
        Restart the guest after installation is finished.

        Args:
            system_profile (SystemProfile): db's entry
        """
        # perform a soft reboot until reboot via hypervisor gets fixed in hmc
        hostname = system_profile.system_rel.hostname
        user = system_profile.credentials['username']
        password = system_profile.credentials['password']

        ssh_client = SshClient()
        ssh_client.login(hostname, user, password, None)
        shell = ssh_client.open_shell()
        try:
            shell.run('reboot', timeout=10)
        except TimeoutError:
            pass
    # reboot()
# PlatKvm
