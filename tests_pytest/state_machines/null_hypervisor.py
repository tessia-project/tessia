# Copyright 2021 IBM Corp.
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
NullHypervisor supporting class
"""

#
# IMPORTS
#
from tessia.baselib.hypervisors.base import HypervisorBase
from tests_pytest.decorators import tracked

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


class NullHypervisor(HypervisorBase):
    """
    Null hypervisor implementation

    It is a hypervisor stub that does nto communicate to any real hardware,
    instead reporting success
    """

    @tracked
    def login(self):
        """Logon to hypervisor always succeeds"""

    @tracked
    def logoff(self):
        """Logon from hypervisor always succeeds"""

    @tracked
    def set_boot_device(self, guest_name, boot_device_params):
        """Set boot device alwas succeeds"""

    @tracked
    def start(self, guest_name, cpu, memory, parameters, notify=None):
        """System starts immediately"""
        if notify:
            notify.set()

    @tracked
    def stop(self, guest_name, parameters):
        """System stops immediately"""

    @tracked
    def reboot(self, guest_name, parameters):
        """System reboots immediately"""
