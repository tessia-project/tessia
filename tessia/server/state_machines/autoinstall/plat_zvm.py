# Copyright 2018 IBM Corp.
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
Module to deal with operations on zVM guests
"""

#
# IMPORTS
#
from tessia.baselib.common.ssh.client import SshClient
from tessia.baselib.hypervisors import Hypervisor
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from urllib.parse import urljoin

import logging

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class PlatZvm(PlatBase):
    """
    Handling of zVM guests
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor, validate values provided.
        """
        super().__init__(*args, **kwargs)
        # create our own logger so that the right module name is in output
        self._logger = logging.getLogger(__name__)
    # __init__()

    def _create_hyp(self):
        """
        Create an instance of baselib's hypervisor.

        Returns:
            HypervisorZvm: class instance

        Raises:
            ValueError: in case profile has no zVM password specified
        """
        try:
            host_zvm = self._guest_prof.credentials['host_zvm']
        except KeyError:
            raise ValueError('zVM password not available in profile')
        params = {}
        if 'byuser' in host_zvm:
            params['byuser'] = host_zvm['byuser']
        hyp = Hypervisor(
            self._hyp_type, self._guest_prof.system_rel.name,
            self._hyp_system.hostname, self._guest_prof.system_rel.name,
            host_zvm['passwd'], params)
        return hyp
    # _create_hyp()

    @staticmethod
    def _zvm_jsonify_iface(iface_entry):
        """
        Format a network interface object to a json format expected by baselib.

        Args:
            iface_entry (SystemIface): db entry

        Returns:
            dict: iface information as expected by baselib
        """
        # use only the base address
        ccw_base = []
        for channel in iface_entry.attributes['ccwgroup'].split(','):
            ccw_base.append(channel.split('.')[-1])
        result = {
            'id': ','.join(ccw_base),
            'type': iface_entry.type.lower(),
        }
        return result
    # _zvm_jsonify_iface()

    @staticmethod
    def _zvm_jsonify_vol(vol_entry):
        """
        Format a volume object to a json format expected by baselib.

        Args:
            vol_entry (StorageVolume): db entry

        Returns:
            dict: volume information as expected by baselib
        """
        result = {'type': vol_entry.type_rel.name.lower()}
        if result['type'] != 'fcp':
            result['devno'] = vol_entry.volume_id.split('.')[-1]
        else:
            result['devno'] = (
                vol_entry.specs['adapters'][0]['devno'].split('.')[-1])
            result['wwpn'] = vol_entry.specs['adapters'][0]['wwpns'][0]
            result['lun'] = vol_entry.volume_id
        return result
    # _zvm_jsonify_vol()

    def boot(self, kargs):
        """
        Perform a network boot operation to start the installation process

        Args:
            kargs (str): kernel command line args for os' installer
        """
        # basic information
        cpu = self._guest_prof.cpu
        memory = self._guest_prof.memory
        guest_name = self._guest_prof.system_rel.name

        # prepare entries in the format expected by baselib
        svols = []
        for svol in self._guest_prof.storage_volumes_rel:
            svols.append(self._zvm_jsonify_vol(svol))
        ifaces = []
        for iface in self._guest_prof.system_ifaces_rel:
            ifaces.append(self._zvm_jsonify_iface(iface))

        # repository related information
        repo = self._repo
        kernel_uri = urljoin(repo.url + '/', repo.kernel.strip('/'))
        initrd_uri = urljoin(repo.url + '/', repo.initrd.strip('/'))

        # parameters argument, see baselib schema for details
        params = {
            'ifaces': ifaces,
            'storage_volumes': svols,
            'boot_method': 'network',
            'netboot': {
                "kernel_uri": kernel_uri,
                "initrd_uri": initrd_uri,
                "cmdline": kargs,
            }
        }
        self._hyp_obj.start(guest_name, cpu, memory, params)
        # clear the underlying s3270 process
        self._hyp_obj.logoff()
    # boot()

    def get_vol_devpath(self, vol_obj):
        """
        Given a volume entry, return the correspondent device path on operating
        system.

        Args:
            vol_obj (StorageVolume): db entry

        Returns:
            str: device path

        Raises:
            RuntimeError: in case the volume type is unknown
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
        # perform a soft reboot
        self._logger.info('rebooting the system now')

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
# PlatZvm