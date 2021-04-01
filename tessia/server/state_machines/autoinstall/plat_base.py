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
from tessia.baselib.hypervisors.base import HypervisorBase
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from tessia.baselib.common.ssh.client import SshClient

import abc
import logging

#
# CONSTANTS AND DEFINITIONS
#
HYP_TYPES_BASELIB = {
    AutoinstallMachineModel.SystemProfile.SystemTypes.LPAR: 'hmc',
    AutoinstallMachineModel.SystemProfile.SystemTypes.KVM: 'kvm',
    AutoinstallMachineModel.SystemProfile.SystemTypes.ZVM: 'zvm'
}

#
# CODE
#


class PlatBase(metaclass=abc.ABCMeta):
    """
    Base class for all platforms
    """

    def __init__(self, model: AutoinstallMachineModel,
            hypervisor: HypervisorBase):
        """
        Constructor, store references and create hypervisor object

        Args:
            model: autoinstall model
        """
        self._logger = logging.getLogger(__name__)
        self._model = model

        # these are convenience shortcuts used by specializations
        self._hyp_system = model.system_profile.hypervisor
        self._guest_prof = model.system_profile
        self._os = model.operating_system
        self._repo = model.os_repos[0]
        self._gw_iface = model.system_profile.gateway_interface

        # base class no knowledge about parameters so _create_hyp can be
        # implemented by children classes
        self._hyp_obj = hypervisor
    # __init__()

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

    @classmethod
    def create_hypervisor(cls, model: AutoinstallMachineModel):
        """
        Create an instance of baselib's hypervisor. Here we have no
        knowledge about parameters so _create_hyp can be re-implemented
        by children classes
        """
        raise NotImplementedError()
    # create_hypervisor()

    def reboot(self):
        """
        Restart the guest after installation is finished.
        """
        # perform a soft reboot
        self._logger.info('rebooting the system now')

        hostname = self._model.system_profile.hostname
        user = self._model.os_credentials['user']
        password = self._model.os_credentials['password']

        ssh_client = SshClient()
        ssh_client.login(hostname, user=user, passwd=password, timeout=10)
        shell = ssh_client.open_shell()
        try:
            shell.run('nohup reboot -f; nohup killall sshd', timeout=1)
        except TimeoutError:
            pass
        shell.close()
        ssh_client.logoff()
    # reboot()

    @abc.abstractmethod
    def set_boot_device(self, boot_device):
        """
        Set boot device to perform later boot

        Args:
            boot_device (dict): boot device description
                "storage": StorageVolume
                "network": string

                Specific device support depends on the hypervisor and baselib
                implementation

        Raises:
            NotImplementedError: as it should be implemented by child class
        """
        raise NotImplementedError()
    # set_boot_device()
# PlatBase
