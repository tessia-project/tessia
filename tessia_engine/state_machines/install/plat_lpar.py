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
from urllib.parse import urljoin

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
    def _get_start_params(self, kargs):
        """
        Return the start parameters specific to LPAR

        Args:
            kargs (str): kernel command line args for os' installer

        Returns:
            dict: in format expected by tessia_baselibs' parameters option
        """
        # repository related information
        repo = self._repo
        kernel_uri = urljoin(repo.url + '/', repo.kernel.strip('/'))
        initrd_uri = urljoin(repo.url + '/', repo.initrd.strip('/'))

        params = {
            "cpc_name": self._hyp_system.name.upper(),
            "boot_params": {
                "boot_method": "network",
                "kernel_url": kernel_uri,
                "initrd_url": initrd_uri,
                "cmdline": kargs,
                "mac": self._gw_iface['mac_addr'],
                "ip": self._gw_iface['ip'],
                "mask": self._gw_iface["mask"],
                "gateway": self._gw_iface['gateway'],
                "device": self._gw_iface['attributes']['devicenr'].split(
                    ",")[0].lstrip("0x"),
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
        ssh_client.login(hostname, user=user, passwd=password,
                         timeout=10)
        shell = ssh_client.open_shell()
        shell.run('nohup reboot &>/dev/null &', ignore_ret=True)
        shell.close()
        ssh_client.logoff()
    # reboot()
# PlatLpar
