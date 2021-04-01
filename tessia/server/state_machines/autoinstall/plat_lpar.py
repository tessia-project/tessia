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
from queue import Queue

from tessia.baselib.hypervisors.hmc import HypervisorHmc
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

    def __init__(self, *args, **kwargs):
        """
        Constructor, validate values provided.
        """
        super().__init__(*args, **kwargs)
        # create our own logger so that the right module name is in output
        self._logger = logging.getLogger(__name__)

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
        if isinstance(boot_device, AutoinstallMachineModel.ScsiVolume):
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
                'uuid': boot_device.wwid[-32:],
            }
            # NOTE: WWIDs specified in storage in general follow
            # udev rules, which commonly add a prefix '3' to volume UUID.
            # The UUID itself is 32 nibbles long, but may be 16 or something
            # else entirely. There is no exact rule to figure out
            # one from the other, but otherwise we would have to have
            # very similar data (wwid and uuid) in device configuration.
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

        Raises:
            ValueError: failed to parse boot URI
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
    # _boot_device_to_baselib_params()

    @classmethod
    def create_hypervisor(cls, model: AutoinstallMachineModel):
        """
        Create an instance of baselib's hypervisor. Here we have no
        knowledge about parameters so _create_hyp can be re-implemented
        by children classes
        """
        return HypervisorHmc(
            model.system_profile.hypervisor.name,
            model.system_profile.hypervisor.hmc_address,
            model.system_profile.hypervisor.credentials['user'],
            model.system_profile.hypervisor.credentials['password'],
            None)
    # create_hypervisor()

    def boot(self, kargs):
        """
        Perform a boot operation so that the installation process can start.

        Args:
            kargs (str): kernel command line args for os' installer

        Raises:
            ValueError: in case an unsupported network type is found
            RuntimeError: baselib exception occurred
        """
        # basic information
        cpu = self._guest_prof.cpus
        memory = self._guest_prof.memory
        guest_name = self._hyp_system.boot_options['partition-name']

        # repository related information
        repo = self._repo
        kernel_uri = urljoin(repo.url + '/', repo.kernel.strip('/'))
        initrd_uri = urljoin(repo.url + '/', repo.initrd.strip('/'))

        # parameters argument, see baselib schema for details
        params = {}
        params['boot_params'], err = self._boot_options_to_baselib_params(
            self._hyp_system.boot_options
        )
        if err:
            raise RuntimeError(err)

        params['boot_params']['netboot'] = {
            "kernel_url": kernel_uri,
            "initrd_url": initrd_uri,
            "cmdline": kargs
        }
        subnet_model = self._gw_iface.gateway_subnets[0]
        # network configuration
        params['boot_params']['netsetup'] = {
            "mac": self._gw_iface.mac_address,
            "ip": str(subnet_model.ip_address),
            "mask": subnet_model.subnet.prefixlen,
            "gateway": str(subnet_model.gateway),
            "password": self._live_passwd,
        }
        if subnet_model.vlan:
            params['boot_params']['netsetup']['vlan'] = (
                subnet_model.vlan)
        # osa cards
        if isinstance(self._gw_iface, AutoinstallMachineModel.OsaInterface):
            params['boot_params']['netsetup']['type'] = 'osa'
            params['boot_params']['netsetup']['device'] = (
                self._gw_iface.ccwgroup.split(",")[0].split('.')[-1])
            params['boot_params']['netsetup']['options'] = {
                'layer2': self._gw_iface.layer2,
                'portno': self._gw_iface.portno,
                'portname': self._gw_iface.portname,
            }
        # roce cards
        elif isinstance(self._gw_iface, AutoinstallMachineModel.RoceInterface):
            params['boot_params']['netsetup']['type'] = 'pci'
            params['boot_params']['netsetup']['device'] = self._gw_iface.fid
        else:
            raise ValueError('Unsupported network card type {}'
                             .format(self._gw_iface.type))
        if subnet_model.dns:
            params['boot_params']['netsetup']['dns'] = subnet_model.dns

        # Run HMC communication in separate thread to be able to continue
        # with the state machine after boot_notification has been signaled.
        # Thread will continue running for some time, providing HMC output.
        # If an exception happens in the thread before boot happened,
        # we should re-raise it to stop further processing
        boot_notification = Event()
        exception_store = Queue()
        hyp_thread = HmcThread(
            exception_store, self._hyp_obj.start,
            guest_name, cpu, memory, params, boot_notification)
        hyp_thread.start()

        # wait until either we have been notified that we can go on,
        # or baselib thread has exited for some reason
        while not boot_notification.wait(5.) and hyp_thread.is_alive():
            pass
        if not exception_store.empty():
            exc_info = exception_store.get()
            self._logger.debug('HMC thread exception: %s', str(exc_info[1]))
            raise RuntimeError("Failed to prepare partition") from exc_info[1]

        if boot_notification.is_set():
            self._logger.debug("Received initial boot complete notification")
    # boot()

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
# PlatLpar
