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
from queue import Queue
from tessia.server.config import Config
from tessia.server.db.models import StorageVolume
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from threading import Event, Thread
from urllib.parse import urljoin, urlsplit

import ipaddress
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

        # make sure the CPC of the LPAR has a live-image disk configured
        try:
            self._live_src = self._hyp_prof.storage_volumes_rel[0]
        except IndexError:
            try:
                self._live_src = (
                    self._hyp_prof.parameters['liveimg-insfile-url'])
            except (KeyError, TypeError):
                raise ValueError(
                    'CPC {} has neither an auxiliary disk (DPM and classic '
                    ' mode) nor an insfile URL (DPM only) registered to '
                    'serve the live-image required for installation'
                    .format(self._hyp_prof.system_rel.name)) from None
        try:
            self._live_passwd = Config.get_config().get(
                'auto_install')['live_img_passwd']
        except (TypeError, KeyError):
            raise ValueError(
                'Live-image password missing in config file') from None
    # __init__()

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
        cpu = self._guest_prof.cpu
        memory = self._guest_prof.memory
        guest_name = self._guest_prof.system_rel.name

        # repository related information
        repo = self._repo
        kernel_uri = urljoin(repo.url + '/', repo.kernel.strip('/'))
        initrd_uri = urljoin(repo.url + '/', repo.initrd.strip('/'))

        # parameters argument, see baselib schema for details
        params = {}
        # serve live image from aux disk
        if isinstance(self._live_src, StorageVolume):
            if self._live_src.type.lower() == 'fcp':
                # WARNING: so far with DS8K storage servers the wwid seems to
                # correspond to the uuid by removing only the first digit, but
                # this not documented so it might change in future or even be
                # different with other storage types
                vol_uuid = self._live_src.specs['wwid'][1:]
                params['boot_params'] = {
                    'boot_method': 'scsi',
                    'devicenr': (
                        self._live_src.specs['adapters'][0]['devno']),
                    'wwpn': self._live_src.specs['adapters'][0]['wwpns'][0],
                    'lun': self._live_src.volume_id,
                    'uuid': vol_uuid,
                }
            else:
                params['boot_params'] = {
                    'boot_method': 'dasd',
                    'devicenr': self._live_src.volume_id
                }
        # serve live image from network (DPM only)
        else:
            try:
                parsed_url = urlsplit(self._live_src)
            except ValueError as exc:
                raise ValueError('Live image URL {} is invalid: {}'
                                 .format(self._live_src, str(exc)))
            params['boot_params'] = {
                'boot_method': parsed_url.scheme,
                'insfile': ''.join(parsed_url[1:]),
            }
        params['boot_params']['netboot'] = {
            "kernel_url": kernel_uri,
            "initrd_url": initrd_uri,
            "cmdline": kargs
        }
        subnet_pyobj = ipaddress.ip_network(
            self._gw_iface.ip_address_rel.subnet_rel.address, strict=True)
        # network configuration
        params['boot_params']['netsetup'] = {
            "mac": self._gw_iface.mac_address,
            "ip": self._gw_iface.ip_address_rel.address,
            "mask": subnet_pyobj.prefixlen,
            "gateway": self._gw_iface.ip_address_rel.subnet_rel.gateway,
            "password": self._live_passwd,
        }
        if self._gw_iface.ip_address_rel.subnet_rel.vlan:
            params['boot_params']['netsetup']['vlan'] = (
                self._gw_iface.ip_address_rel.subnet_rel.vlan)
        # osa cards
        if self._gw_iface.type.lower() == 'osa':
            params['boot_params']['netsetup']['type'] = 'osa'
            params['boot_params']['netsetup']['device'] = (
                self._gw_iface.attributes['ccwgroup']
                .split(",")[0].split('.')[-1])
            options = deepcopy(self._gw_iface.attributes)
            options.pop('ccwgroup')
            params['boot_params']['netsetup']['options'] = options
        # roce cards
        elif self._gw_iface.type.lower() == 'roce':
            params['boot_params']['netsetup']['type'] = 'pci'
            params['boot_params']['netsetup']['device'] = (
                self._gw_iface.attributes['fid'])
        else:
            raise ValueError('Unsupported network card type {}'
                             .format(self._gw_iface.type))
        dns_servers = []
        if self._gw_iface.ip_address_rel.subnet_rel.dns_1:
            dns_servers.append(self._gw_iface.ip_address_rel.subnet_rel.dns_1)
        if self._gw_iface.ip_address_rel.subnet_rel.dns_2:
            dns_servers.append(self._gw_iface.ip_address_rel.subnet_rel.dns_2)
        if dns_servers:
            params['boot_params']['netsetup']['dns'] = dns_servers

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
        if vol_obj.type in ('DASD', 'HPAV'):
            vol_id = vol_obj.volume_id
            if vol_id.find('.') < 0:
                vol_id = '0.0.' + vol_id
            return '/dev/disk/by-path/ccw-{}'.format(vol_id)

        if vol_obj.type == 'FCP':
            if vol_obj.specs['multipath']:
                prefix = '/dev/disk/by-id/dm-uuid-mpath-{}'
            else:
                prefix = '/dev/disk/by-id/scsi-{}'
            return prefix.format(vol_obj.specs['wwid'])

        raise RuntimeError(
            "Unknown volume type'{}'".format(vol_obj.type))

    # get_vol_devpath()
# PlatLpar
