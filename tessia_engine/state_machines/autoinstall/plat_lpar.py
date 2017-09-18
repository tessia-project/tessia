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
from copy import deepcopy
from tessia_baselib.common.ssh.client import SshClient
from tessia_engine.state_machines.autoinstall.plat_base import PlatBase
from urllib.parse import urljoin

import logging

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class PlatLpar(PlatBase):
    """
    Handling for HMC's LPARs
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # create our own logger so that the right module name is in output
        self._logger = logging.getLogger(__name__)
    # __init__()

    def boot(self, kargs):
        """
        Perform a boot operation so that the installation process can start.

        Args:
            kargs (str): kernel command line args for os' installer
        """
        # basic information
        cpu = self._guest_prof.cpu
        memory = self._guest_prof.memory
        guest_name = self._guest_prof.system_rel.name

        # repository related information
        repo = self._repo
        kernel_uri = urljoin(repo.url + '/', repo.kernel.strip('/'))
        initrd_uri = urljoin(repo.url + '/', repo.initrd.strip('/'))

        # parameters argument, see tessia_baselib schema for details
        options = deepcopy(self._gw_iface['attributes'])
        options.pop('ccwgroup')
        params = {
            "cpc_name": self._hyp_system.name,
            "boot_params": {
                "boot_method": "network",
                "kernel_url": kernel_uri,
                "initrd_url": initrd_uri,
                "cmdline": kargs,
                "mac": self._gw_iface['mac_addr'],
                "ip": self._gw_iface['ip'],
                "mask": self._gw_iface["mask"],
                "gateway": self._gw_iface['gateway'],
                "device": self._gw_iface['attributes']
                          ['ccwgroup'].split(",")[0].split('.')[-1],
                "options": options
            }
        }

        self._hyp_obj.start(guest_name, cpu, memory, params)
    # boot()

    def get_vol_devpath(self, vol_obj):
        """
        Given a volume entry, return the correspondent device path on operating
        system.
        """
        if vol_obj.type == 'DASD':
            vol_id = vol_obj.volume_id
            if vol_id.find('.') < 0:
                vol_id = '0.0.' + vol_id
            return '/dev/disk/by-path/ccw-{}'.format(vol_id)

        elif vol_obj.type == 'FCP':
            if vol_obj.specs['multipath']:
                prefix = '/dev/disk/by-id/dm-uuid-mpath-{}'
            else:
                prefix = '/dev/disk/by-id/scsi-{}'
            return prefix.format(vol_obj.specs['wwid'])

        raise RuntimeError(
            "Unknown volume type'{}'".format(vol_obj.type))

    # get_vol_devpath()

    def reboot(self, system_profile):
        """
        Restart the guest after installation is finished.

        Args:
            system_profile (SystemProfile): db's entry
        """
        # perform a soft reboot until reboot via hypervisor gets fixed in hmc
        self._logger.info('Rebooting the system now!')

        hostname = system_profile.system_rel.hostname
        user = system_profile.credentials['user']
        password = system_profile.credentials['passwd']

        ssh_client = SshClient()
        ssh_client.login(hostname, user=user, passwd=password,
                         timeout=10)
        shell = ssh_client.open_shell()
        try:
            shell.run('nohup reboot -f; nohup killall sshd', timeout=1)
        except TimeoutError:
            pass
        shell.close()
        ssh_client.logoff()
    # reboot()
# PlatLpar
