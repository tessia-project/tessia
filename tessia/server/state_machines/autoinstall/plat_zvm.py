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
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from tessia.baselib.hypervisors.zvm import HypervisorZvm
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from urllib.parse import urljoin

import logging

#
# CONSTANTS AND DEFINITIONS
#

# VM file transfer uses its own packet size, by default it is rather small
# and slows down installation kernel transfer over high-latency connections.
# Not all VMs support values up to 32K, but tests have shown 8000 is well
# supported.
DEFAULT_TRANSFER_BUFFER_SIZE = 8000

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

    @classmethod
    def create_hypervisor(cls, model: AutoinstallMachineModel):
        """
        Create an instance of baselib's hypervisor.

        Returns:
            HypervisorZvm: class instance
        """
        params = {
            'transfer-buffer-size': DEFAULT_TRANSFER_BUFFER_SIZE
        }
        params['byuser'] = (
            model.system_profile.hypervisor.connection_parameters.get(
                'logon-by'))

        hyp = HypervisorZvm(
            model.system_profile.system_name,
            model.system_profile.hypervisor.zvm_address,
            model.system_profile.hypervisor.credentials['user'],
            model.system_profile.hypervisor.credentials['password'],
            params)
        return hyp
    # create_hypervisor()

    @staticmethod
    def _zvm_jsonify_iface(iface_entry):
        """
        Format a network interface object to a json format expected by baselib.

        Args:
            iface_entry (SystemIface): db entry

        Returns:
            dict: iface information as expected by baselib

        Raises:
            ValueError: in case interface type is not supported
        """
        # osa card: use only the base address
        if isinstance(iface_entry, AutoinstallMachineModel.OsaInterface):
            ccw_base = []
            for channel in iface_entry.ccwgroup.split(','):
                ccw_base.append(channel.split('.')[-1])
            return {
                'id': ','.join(ccw_base),
                'type': 'osa',
            }
        if isinstance(iface_entry,
                      AutoinstallMachineModel.HipersocketsInterface):
            ccw_base = []
            for channel in iface_entry.ccwgroup.split(','):
                ccw_base.append(channel.split('.')[-1])
            return {
                'id': ','.join(ccw_base),
                'type': 'hsi',
            }
        if isinstance(iface_entry, AutoinstallMachineModel.RoceInterface):
            return {
                'id': iface_entry.fid,
                'type': 'pci',
            }

        raise ValueError('Unsupported network card type {}'
                         .format(iface_entry.__class__.__qualname__))
    # _zvm_jsonify_iface()

    @staticmethod
    def _zvm_jsonify_vol(vol_entry: AutoinstallMachineModel.Volume):
        """
        Format a volume object to a json format expected by baselib.

        Args:
            vol_entry: db entry

        Returns:
            dict: volume information as expected by baselib

        Raises:
            ValueError: in case interface type is not supported
        """
        if isinstance(vol_entry, AutoinstallMachineModel.DasdVolume):
            return {
                'type': 'dasd',
                'devno': vol_entry.device_id
            }
        if isinstance(vol_entry, AutoinstallMachineModel.HpavVolume):
            return {
                'type': 'hpav',
                'devno': vol_entry.device_id
            }
        if isinstance(vol_entry, AutoinstallMachineModel.ScsiVolume):
            # compatibility layer to existing templates:
            # provide paths grouped by adapters
            adapters = {}
            for adapter, wwpn in vol_entry.paths:
                if not adapter in adapters:
                    adapters[adapter] = [wwpn]
                else:
                    adapters[adapter].append(wwpn)

            return {
                'type': 'fcp',
                'adapters': [{'devno': adapter, 'wwpns': wwpns}
                             for adapter, wwpns in adapters.items()],
                'lun': vol_entry.lun
            }
        raise ValueError('Unsupported storage type {}'
                         .format(vol_entry.volume_type))
    # _zvm_jsonify_vol()

    def boot(self, kargs):
        """
        Perform a network boot operation to start the installation process

        Args:
            kargs (str): kernel command line args for os' installer
        """
        # basic information
        cpu = self._guest_prof.cpus
        memory = self._guest_prof.memory
        guest_name = self._guest_prof.system_name

        # prepare entries in the format expected by baselib
        svols = []
        for svol in self._guest_prof.volumes:
            svols.append(self._zvm_jsonify_vol(svol))
        ifaces = []
        for iface in self._guest_prof.ifaces:
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
        # login to 3270 console
        self._hyp_obj.login()
        # boot into installer
        self._hyp_obj.start(guest_name, cpu, memory, params)
        # clear the underlying s3270 process
        self._hyp_obj.logoff()
    # boot()

    def set_boot_device(self, boot_device):
        """
        Set boot device to perform later boot

        Args:
            boot_device (dict): boot device description
                "storage" (StorageVolume): volume
                "network" (string): URI with boot source
        """
        self._logger.debug("set_boot_device on z/VM is not implemented")
    # set_boot_device()
# PlatZvm
