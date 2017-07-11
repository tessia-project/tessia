# Copyright 2017 IBM Corp.
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
Module is Proof Of Concept for a post installation verification with
ansible tool
"""

#
# IMPORTS
#
from tessia_engine.state_machines.autoinstall import exceptions

import ipaddress
import json
import re
import subprocess

#
# CONSTANTS AND DEFINITIONS
#
# tessia and ansible use different names for the same parameters
ANS_ALIASES = {
    'cpu': 'ansible_processor_cores',
    'os_name': ['ansible_distribution', 'ansible_distribution_version'],
    'memory': 'ansible_memtotal_mb',
    'network': 'ansible_interfaces',
    'storage': 'ansible_mounts',
    'kernel_version': 'ansible_kernel'
}
# tessia and ansible use different aliases for distros
OS_NAME_ALIASES = {
    'rhel': ['redhat', 'rhel'],
    'sles': 'sles',
    'ubuntu': 'ubuntu'
}
# parameters list for verification
PARAMS_TO_CHECK = ['cpu', 'os_name', 'memory', 'network', 'storage']

#
# CODE
#
def config_verificate(os_entry, profile_entry):
    """
    Check required parameters after installation.

    Args:
        os_entry (OperatingSystem): db's entry.
        profile_entry (SystemProfile): profile's db entry.
    """

    wish_params = get_wish_params(os_entry, profile_entry)
    hostname = profile_entry.system_rel.hostname
    ans_facts = get_actual_params(hostname)
    ans_fcp_specs = get_actual_fcp(hostname)

    for param in wish_params:
        if wish_params[param] is not None:
            if param == 'os_name':
                os_name_compare(param, wish_params, ans_facts)
            if param == 'memory':
                memory_compare(param, wish_params['memory'], ans_facts)
            if param == 'network':
                network_compare(wish_params['network'], ans_facts)
            if param == 'storage':
                storage_compare(
                    wish_params['storage'],
                    ans_facts,
                    ans_fcp_specs)
            if param == 'kernel_version':
                compare(
                    param,
                    wish_params['kernel_version'],
                    ans_facts[ANS_ALIASES['kernel_version']])
            if param == 'cpu':
                compare(
                    param,
                    wish_params['cpu'],
                    ans_facts[ANS_ALIASES['cpu']])
# config_verificate()


def get_wish_params(os_entry, profile_entry):
    """
    Get 'ansible facts' from a target instance.

    Args:
        os_entry (OperatingSystem): db's entry.
        profile_entry (SystemProfile): profile's db entry.

    Returns:
        dict: a dictionary with all required parameters.
    """

    params = dict.fromkeys(PARAMS_TO_CHECK)
    for param in params:
        if param == 'cpu':
            params[param] = profile_entry.cpu
        if param == 'os_name':
            params[param] = os_entry
        if param == 'memory':
            params[param] = profile_entry.memory
        if param == 'network':
            params[param] = profile_entry.system_ifaces_rel
        if param == 'storage':
            params[param] = profile_entry.storage_volumes_rel
        if param == 'kernel_version':
            params[param] = profile_entry.parameters['kernel_version']

    return params
# get_wish_params()


def get_actual_params(hostname):
    """
    Get 'ansible facts' from a target instance.

    Args:
        hostname (string): a target instance hostname.

    Raises:
        RuntimeError: in case the query fails to find an operating system.

    Returns:
        dict: a dictionary with all ansible facts.
    """
    try:
        params = subprocess.check_output(
            ["ansible", "-o", "-m", "setup", hostname]).decode()
    except subprocess.CalledProcessError:
        raise RuntimeError("Error while checking the installed system.")

    # ansible's output has additional service info, so we need to clean that
    ans_json = re.search('({.*})', params)
    try:
        params = json.loads(ans_json.group(1))
    except AttributeError:
        raise RuntimeError("Error while checking the installed system.")

    return params['ansible_facts']
# get_actual_params()


def get_actual_fcp(hostname):
    """
    Get FCP info from a target instance.

    Args:
        hostname (string): a target instance hostname.

    Raises:
        RuntimeError: in case the system hasn't FCP.

    Returns:
        list: a list with all FCP entries.
    """
    ans_fcp_specs = []
    try:
        ans_fcp = (subprocess.check_output(
            ["ansible", hostname, "-m", "command", "-a",
             "lszfcp -D"]).decode()).split('\n')[1:-1]
        for entry in ans_fcp:
            ans_fcp_specs.append(entry.partition(' ')[0].split("/"))
    except subprocess.CalledProcessError:
        ans_fcp_specs = None
    return ans_fcp_specs
# get_actual_fcp()


def compare(param_name, wish_param, ans_fact):
    """
    Compare required parameter with actual one.
    """
    if str(wish_param) != str(ans_fact):
        raise exceptions.Misconfiguration(param_name, wish_param, ans_fact)
# compare()


def os_name_compare(param, wish_params, ans_facts):
    """
   Check OS name after installation.

    Args:
        param (string): a parameter name.
        wish_params (dict): a dictionary with required parameters.
        ans_facts (dict): a dictionary with ansible facts.

    """
    for osname in OS_NAME_ALIASES:
        if str(ans_facts[ANS_ALIASES[param][0]]).lower() \
                in OS_NAME_ALIASES[osname]:
            ans_facts[ANS_ALIASES[param][0]] = osname

    full_os_name = wish_params[param].type \
                    + str(wish_params[param].major) \
                    + '.' \
                    + str(wish_params[param].minor)

    ans_os_name = ans_facts[ANS_ALIASES[param][0]] \
                    + ans_facts[ANS_ALIASES[param][1]]
    compare(param, full_os_name, ans_os_name)
# os_name_compare()


def memory_compare(param, wish_param, ans_facts):
    """
    Check memory after installation.

    Args:
        param (string): a parameter name.
        wish_param (int): a required size.
        ans_facts (dict): a dictionary with ansible facts.

    """
    def calc(size, size_format):
        """
        Size conversion: M <-> G.

        Args:
            size (string): a size in current units.
            size_format (string): a result format.

        Returns:
            float: a transformed size.
        """
        result = None
        if size_format == 'M':
            if 'M' in size:
                result = float(size.replace('M', ''))
            elif 'G' in size:
                result = float(size.replace('G', '')) * 1024
        elif size_format == 'G':
            if 'M' in size:
                result = round(float(size.replace('M', '')) / 1024, 1)
            elif 'G' in size:
                result = float(size.replace('G', ''))
        return result
    # calc()

    size_list = []

    ans_memory = ans_facts[ANS_ALIASES[param]]

    # ans_total_memory: crash kernel memory + real total memory
    ans_total_memory = 0

    cmd_line = ans_facts['ansible_cmdline']['crashkernel']
    cmd_line = cmd_line.split(",")

    for entry in cmd_line:
        range_entry = {'min': None, 'max': None, 'crash_mem_size': None}
        entry = entry.split(":")

        for i in (0, len(entry)-1):
            if i % 2 == 0:
                tmp = entry[i].split("-")
                range_entry['min'] = calc(tmp[0], 'M')
                range_entry['max'] = calc(tmp[1], 'M')
            else:
                range_entry['crash_mem_size'] = calc(entry[i], 'M')
        size_list.append(range_entry)

    for range_entry in size_list:
        if range_entry['max'] is None:
            range_entry['max'] = 'inf'
        if range_entry['min'] is None:
            range_entry['min'] = 0
        ans_total_memory = int(range_entry['crash_mem_size']) + ans_memory
        if range_entry['max'] != 'inf':
            if range_entry['min'] < ans_total_memory < range_entry['max']:
                break

    compare(param,
            str(calc(str(wish_param) + 'M', 'G')) + 'G',
            str(calc(str(ans_total_memory) + 'M', 'G')) + 'G')

# memory_compare()


def network_compare(wish_ifaces, ans_facts):
    """
    Check network configuration after installation.

    Args:
        wish_ifaces (list): a list with required parameters.
        ans_facts (dict): a dictionary with ansible facts.

    """
    ans_iface = ans_facts[ANS_ALIASES['network']]

    for iface in wish_ifaces:
        if iface.osname in ans_iface:
            compare('DEVICE TYPE',
                    iface.type,
                    ans_facts['ansible_' + iface.osname]['type'])

            addresses = []
            addresses.append(iface.ip_address_rel)

            for entry in addresses:
                alias = 'ansible_' + iface.osname

                compare('IP ADDRESS',
                        entry.address,
                        ans_facts[alias]['ipv4']['address'])

                compare('NETWORK',
                        ipaddress.ip_network(entry.subnet_rel.address).
                        with_netmask,
                        ans_facts[alias]['ipv4']['network']
                        + '/' + ans_facts[alias]['ipv4']['netmask'])

                dns_list = []

                if entry.subnet_rel.dns_1 is not None:
                    dns_list.append(entry.subnet_rel.dns_1)
                if entry.subnet_rel.dns_2 is not None:
                    dns_list.append(entry.subnet_rel.dns_2)

                compare('DNS',
                        dns_list,
                        ans_facts['ansible_dns']['nameservers'])

                compare('GATEWAY',
                        entry.subnet_rel.gateway,
                        ans_facts['ansible_default_ipv4']['gateway'])

        else:
            raise exceptions.Misconfiguration('interface', iface.osname, None)
# network_compare()


def storage_compare(wish_storages, ans_facts, ans_fcp_specs):
    """
    Check volume configuration after installation.

    Args:
        wish_storages (list): a list with required parameters.
        ans_facts (dict): a dictionary with ansible facts.
        ans_fcp_specs (list): a list with actual FCP parameters.

    """
    ans_storages = ans_facts[ANS_ALIASES['storage']]
    for storage in wish_storages:
        # compare FCP options
        if storage.type == "FCP":
            for fcp_entry in storage.specs['adapters']:
                if ans_fcp_specs is None:
                    compare('FCP PARAMETER',
                            fcp_entry['devno'],
                            None)
                for ans_fcp_entry in ans_fcp_specs:
                    compare('DEVNO',
                            fcp_entry['devno'],
                            ans_fcp_entry[0])
                    compare('WWPNS',
                            fcp_entry['wwpns'][0],
                            ans_fcp_entry[1].replace('0x', ''))

        for part_table in storage.part_table['table']:
            mp_is_correct = None

            for ans_storage in ans_storages:
                # try find right storage by mount point
                if part_table['mp'] == ans_storage['mount']:
                    mp_is_correct = True

                    compare('MOUNT OPTIONS',
                            part_table['mo'],
                            ans_storage['options'])
                    compare('FILE SYSTEM TYPE',
                            part_table['fs'],
                            ans_storage['fstype'])
                    compare('SIZE',
                            part_table['size'],
                            int(ans_storage['size_total'] / 1024))

            if mp_is_correct is None:
                compare('MOUNT POINT', part_table['mp'], None)

# storage_compare()
