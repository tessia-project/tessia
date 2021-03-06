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
Interface for epresentation of each platform type
"""

#
# IMPORTS
#
from tessia.baselib.common.ssh.client import SshClient
from tessia.baselib.hypervisors import Hypervisor

import abc
import logging

#
# CONSTANTS AND DEFINITIONS
#
HYP_TYPES_BASELIB = {
    'lpar': 'hmc',
    'kvm': 'kvm',
    'zvm': 'zvm'
}

#
# CODE
#


class PlatBase(metaclass=abc.ABCMeta):
    """
    Base class for all platforms
    """

    def __init__(self, hyp_profile, guest_profile, os_entry, repo_entry,
                 gw_iface):
        """
        Constructor, store references and create hypervisor object

        Args:
            hyp_profile (SystemProfile): hypervisor profile's db entry
            guest_profile (SystemProfile): guest profile's db entry
            os_entry (OperatingSystem): db's entry
            repo_entry (Repository): entry of install source repository
            gw_iface (SystemIface): gateway network interface

        Raises:
            RuntimeError: if hypervisor type in profile is unknown
        """
        self._logger = logging.getLogger(__name__)
        self._hyp_system = hyp_profile.system_rel
        self._hyp_prof = hyp_profile
        self._guest_prof = guest_profile
        self._os = os_entry
        self._repo = repo_entry
        self._gw_iface = gw_iface

        # TODO: normalize names between baselib and server to get rid of this
        hyp_type = self._guest_prof.system_rel.type_rel.name.lower()
        try:
            self._hyp_type = HYP_TYPES_BASELIB[hyp_type]
        except KeyError:
            msg = 'Unknown hypervisor type {}'.format(hyp_type)
            raise RuntimeError(msg)

        # base class no knowledge about parameters so _create_hyp can be
        # implemented by children classes
        self._hyp_obj = self._create_hyp()
    # __init__()

    def _create_hyp(self):
        """
        Create an instance of baselib's hypervisor. Here we have no
        knowledge about parameters so _create_hyp can be re-implemented
        by children classes
        """
        return Hypervisor(
            self._hyp_type,
            self._hyp_system.name,
            self._hyp_system.hostname,
            self._hyp_prof.credentials['admin-user'],
            self._hyp_prof.credentials['admin-password'],
            None)
    # _create_hyp()

    @abc.abstractmethod
    def boot(self, kargs):
        """
        Perform a boot operation so that the installation process can start.

        Args:
            kargs (str): kernel command line args for os' installer

        Raises:
            NotImplementedError: as it should be implemented by child class
        """
        raise NotImplementedError()
    # boot()

    @abc.abstractmethod
    def get_vol_devpath(self, vol_obj):
        """
        Given a volume entry, return the correspondent device path on operating
        system.

        Args:
            vol_obj (StorageVolume): storage volume db object

        Raises:
            NotImplementedError: as it should be implemented by child class
        """
        raise NotImplementedError()
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
        user = system_profile.credentials['admin-user']
        password = system_profile.credentials['admin-password']

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

# PlatBase
