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
from collections import defaultdict
from queue import Queue

from tessia.baselib.hypervisors.hmc import HypervisorHmc
from tessia.baselib.hypervisors.hmc.volume_descriptor import \
    FcpVolumeDescriptor
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from tessia.server.config import Config
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from threading import Event, Thread
from urllib.parse import urljoin, urlsplit

import logging
import sys

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class HmcThread(Thread):
    """
    Thread for handling HMC communications
    """

    def __init__(self, exc_store, target, *args):
        """
        Init with exception storage

        Args:
            exc_store (Queue): a thread-safe storage for exception information
            target (Callable): thread main function
            args (Iterable): arguments to thread main function
        """
        Thread.__init__(self, name='hmc-thread', target=target, args=args)
        self.exc_store = exc_store

    def run(self):
        """
        Run with exception handling
        """
        try:
            super().run()
        except Exception:
            self.exc_store.put(sys.exc_info())


class PlatLpar(PlatBase):
    """
    Handling for HMC's LPARs
    """

    def __init__(self, model: AutoinstallMachineModel,
                 hypervisor: HypervisorHmc = None):
        """
        Constructor, validate values provided.
        """
        super().__init__(model)
        # create our own logger so that the right module name is in output
        self._logger = logging.getLogger(__name__)

        if hypervisor:
            self._hyp_obj = hypervisor
        else:
            self._hyp_obj = PlatLpar.create_hypervisor(model)

        # create HMC session
        self._hyp_obj.login()

        try:
            self._live_passwd = Config.get_config().get(
                'auto_install')['live_img_passwd']
        except (TypeError, KeyError):
            raise ValueError(
                'Live-image password missing in config file') from None
    # __init__()

    @staticmethod
    def _boot_device_to_baselib_params(boot_device):
        """
        Convert boot device specs to baselib parameters

        Args:
            boot_device (StorageVolume): boot device

        Returns:
            Tuple[dict, string]: (params, None) or (None, error)

        Raises:
            RuntimeError: no paths available for SCSI device
        """
        params = None
        if isinstance(boot_device, AutoinstallMachineModel.ZfcpVolume):
            if not boot_device.paths:
                raise RuntimeError(
                    "Boot device {} has no paths available".format(
                        boot_device.lun
                    ))

            adapter, wwpn = boot_device.paths[0]
            params = {
                'boot_method': 'scsi',
                'devicenr': adapter,
                'wwpn': wwpn,
                'lun': boot_device.lun,
                'uuid': boot_device.uuid,
            }
            # NOTE: WWIDs specified in storage in general follow
            # udev rules, which commonly add a prefix '3' to volume UUID.
            # The UUID itself is 32 nibbles long, but may be 16 or something
            # else entirely. There is no exact rule to figure out
            # one from the other, but otherwise we would have to have
            # very similar data (wwid and uuid) in device configuration.
        elif isinstance(boot_device, AutoinstallMachineModel.NvmeVolume):
            params = {
                'boot_method': 'nvme',
                'devicenr': boot_device.device_id
            }
        else:
            params = {
                'boot_method': 'dasd',
                'devicenr': boot_device.device_id
            }

        if params:
            return (params, None)
        return (None, "No boot parameters specified")
    # _boot_device_to_baselib_params()

    @classmethod
    def _boot_options_to_baselib_params(cls, boot_options: dict):
        """
        Convert boot device specs to baselib parameters

        Args:
            boot_options: CPC boot options

        Returns:
            Tuple[dict, string]: (params, None) or (None, error)
        """
        params = None
        if boot_options['boot-method'] == 'storage':
            if 'boot-device-lun' in boot_options:
                params = {
                    'boot_method': 'scsi',
                    'devicenr': boot_options['boot-device'],
                    'wwpn': boot_options['boot-device-wwpn'],
                    'lun': boot_options['boot-device-lun'],
                    'uuid': boot_options['boot-device-uuid'],
                }
            else:
                params = {
                    'boot_method': 'dasd',
                    'devicenr': boot_options['boot-device']
                }
        elif boot_options['boot-method'] == 'network':
            boot_uri = boot_options['boot-uri']
            try:
                parsed_url = urlsplit(boot_uri)
            except ValueError as exc:
                return (None, 'Boot URL {} is invalid: {}'.format(
                    boot_uri, str(exc)))
            params = {
                'boot_method': parsed_url.scheme,
                'insfile': ''.join(parsed_url[1:]),
            }

        if params:
            return (params, None)
        return (None, "No boot parameters specified")
    # _boot_options_to_baselib_params()

    def _prepare_network_parameters(self):
        """
        Prepare network configuration for baselib

        Raises:
            ValueError: unsupported network card

        Returns:
            dict: netsetup for baselib
        """
        subnet_model = self._gw_iface.gateway_subnets[0]
        # network configuration
        netsetup = {
            "mac": self._gw_iface.mac_address,
            "ip": str(subnet_model.ip_address),
            "mask": subnet_model.subnet.prefixlen,
            "gateway": str(subnet_model.gateway),
            "password": self._live_passwd,
        }
        if subnet_model.vlan:
            netsetup['vlan'] = (
                subnet_model.vlan)
        # osa cards
        if isinstance(self._gw_iface, AutoinstallMachineModel.OsaInterface):
            netsetup['type'] = 'osa'
            netsetup['device'] = (
                self._gw_iface.ccwgroup.split(",")[0].split('.')[-1])
            netsetup['options'] = {
                'layer2': self._gw_iface.layer2,
                'portno': self._gw_iface.portno,
                'portname': self._gw_iface.portname,
            }
        # roce cards
        elif isinstance(self._gw_iface, AutoinstallMachineModel.RoceInterface):
            netsetup['type'] = 'pci'
            netsetup['device'] = self._gw_iface.fid
        else:
            raise ValueError('Unsupported network card type {}'
                             .format(self._gw_iface.type))
        if subnet_model.dns:
            netsetup['dns'] = subnet_model.dns

        return netsetup
    # _prepare_network_parameters()

    def _prepare_installation_parameters(self, kargs):
        """
        Prepare network installation parameters for baselib
        using repository information

        Args:
            kargs (str): kernel command line args for os' installer

        Returns:
            dict: netboot for baselib
        """
        repo = self._repo
        kernel_uri = urljoin(repo.url + '/', repo.kernel.strip('/'))
        initrd_uri = urljoin(repo.url + '/', repo.initrd.strip('/'))

        return {
            "kernel_url": kernel_uri,
            "initrd_url": initrd_uri,
            "cmdline": kargs
        }

    def _update_model_zfcp_volumes(self, volumes_desc):
        """
        Update zFCP volumes that match descriptors

        Args:
            volumes_desc (list): list of volume descriptors from baselib
        """

        # model identifies disks by LUN, but descriptors
        # may have multiple paths with different LUNs.
        # Let's regroup incoming data first
        paths_by_uuids = defaultdict(list)
        for volume_desc in volumes_desc:
            for path in volume_desc.paths:
                paths_by_uuids[volume_desc.uuid.lower()].append(
                    (path['device_nr'].lower(),
                     path['wwpn'].lower()))

        # add paths to model SCSI volume if there are none specified
        for volume in self._model.system_profile.volumes:
            if (isinstance(volume, AutoinstallMachineModel.ZfcpVolume)
                    and not volume.paths):
                for adapter, wwpn in paths_by_uuids[volume.uuid]:
                    volume.add_path(adapter, wwpn)
                if paths_by_uuids[volume.uuid]:
                    self._logger.debug("Added paths for volume %s", volume.lun)
                else:
                    self._logger.warning(
                        "HMC reported no paths for volume %s with WWID %s",
                        volume.lun, volume.wwid)
    # _update_model_zfcp_volumes()

    @classmethod
    def create_hypervisor(cls, model: AutoinstallMachineModel):
        """
        Create an instance of baselib's hypervisor. Here we have no
        knowledge about parameters so _create_hyp can be re-implemented
        by children classes
        """
        parameters = None
        if model.system_profile.hypervisor.credentials.get('private-key'):
            parameters = {
                'private-key':
                    model.system_profile.hypervisor.credentials['private-key']
                    }

        return HypervisorHmc(
            model.system_profile.hypervisor.name,
            model.system_profile.hypervisor.hmc_address,
            model.system_profile.hypervisor.credentials['user'],
            model.system_profile.hypervisor.credentials['password'],
            parameters)
    # create_hypervisor()

    def prepare_guest(self):
        """
        Initialize guest (activate, prepare hardware etc.)
        and boot live image.

        Raises:
            RuntimeError: wrong options passed
        """
        # basic information
        cpu = self._guest_prof.cpus
        memory = self._guest_prof.memory
        guest_name = self._hyp_system.boot_options['partition-name']

        # parameters argument, see baselib schema for details
        params = {}
        params['boot_params'], err = self._boot_options_to_baselib_params(
            self._hyp_system.boot_options
        )
        if err:
            raise RuntimeError(err)

        # call baselib to bring up the guest system
        self._hyp_obj.start(guest_name, cpu, memory, params)

        # query storage configuration after activation
        storage_info = self._hyp_obj.query_dpm_storage_devices(guest_name)
        self._logger.debug(
            "Retrieved data about %d devices in storage groups for system %s",
            len(storage_info), guest_name)
        self._update_model_zfcp_volumes(
            [volume for volume in storage_info
             if isinstance(volume, FcpVolumeDescriptor)])
    # prepare_guest()

    def set_boot_device(self, boot_device):
        """
        Set boot device to perform later boot

        Args:
            boot_device (dict): boot device description
                "storage" (StorageVolume): volume
                "network" (string): URI with boot source

        Raises:
            RuntimeError: invalid parameters
        """
        guest_name = self._hyp_system.boot_options['partition-name']
        params, err = self._boot_device_to_baselib_params(boot_device)
        if err:
            raise RuntimeError("Missing set_boot_device parameters")
        self._hyp_obj.set_boot_device(guest_name, params)
    # set_boot_device()

    def start_installer(self, kargs):
        """
        Perform a boot operation so that the installation process can start.

        Args:
            kargs (str): kernel command line args for os' installer

        Raises:
            RuntimeError: wrong options passed
        """
        guest_name = self._hyp_system.boot_options['partition-name']

        # parameters argument, see baselib schema for details
        params = {
            'boot_params': {
                'boot_method': 'none',
                'netsetup': self._prepare_network_parameters(),
                'netboot': self._prepare_installation_parameters(kargs),
            }
        }

        # call baselib to continue with the installer

        # Run HMC communication in separate thread to be able to continue
        # with the state machine after boot_notification has been signaled.
        # Thread will continue running for some time, providing HMC output.
        # If an exception happens in the thread before boot happened,
        # we should re-raise it to stop further processing
        boot_notification = Event()
        exception_store = Queue()
        hyp_thread = HmcThread(
            exception_store, self._hyp_obj.start,
            guest_name, 0, 0, params, boot_notification)
        hyp_thread.start()

        # wait until either we have been notified that we can go on,
        # or baselib thread has exited for some reason
        while not boot_notification.wait(5.) and hyp_thread.is_alive():
            pass
        if not exception_store.empty():
            exc_info = exception_store.get()
            self._logger.debug('HMC thread exception: %s', str(exc_info[1]))
            raise RuntimeError("Failed to start installation") from exc_info[1]

        if boot_notification.is_set():
            self._logger.debug("Received initial boot complete notification")
    # start_installer()
# PlatLpar
