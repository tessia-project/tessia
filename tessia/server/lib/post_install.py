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
Post installation verification using ansible tool
"""

#
# IMPORTS
#
from collections import OrderedDict
from copy import deepcopy
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from pprint import pformat
from tempfile import NamedTemporaryFile

import ipaddress
import json
import logging
import os
import re
import subprocess

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class Misconfiguration(RuntimeError):
    """
    Error caused when the value of parameter received from the remote instance
    does not match the expected one.
    """
    def __init__(self, name_param, exp_value, actual_value):
        """
        name_param (str): name of parameter which caused the error
        exp_value (str): value expected for the parameter
        actual_value (str): actual value found
        """
        super().__init__()

        self.name_param = name_param
        self.exp_value = exp_value
        self.actual_value = actual_value
    # __init__()

    def __str__(self):
        """
        String representation for this error
        """
        error_msg = (
            "Configuration mismatch in {}: expected '{}', actual is '{}'")
        if self.actual_value is None:
            error_msg = error_msg.format(
                self.name_param, self.exp_value, '<not found>')
        else:
            error_msg = error_msg.format(
                self.name_param, self.exp_value, self.actual_value)
        return error_msg
    # __str__()
# Misconfiguration

class PostInstallChecker(object):
    """
    Implementation of the post install checker
    """
    def __init__(self, profile_obj, os_obj=None, permissive=False):
        """
        Constructor.

        Args:
            profile_obj (SystemProfile): profile's db object.
            os_obj (OperatingSystem): operating system db's object.
            permissive (bool): if True, misconfiguration findings will be
                               logged as warnings, otherwise an exception will
                               be raised.

        Raises:
            ValueError: in case connection information is missing
        """
        self._logger = logging.getLogger(__name__)

        # convert the attributes from the sqlalchemy objects to an internal
        # dictionary format
        self._expected_params = self._parse_obj_profile(
            profile_obj, os_obj)

        # parse target connection information
        self._hostname = profile_obj.system_rel.hostname
        try:
            self._user = profile_obj.credentials['user']
            self._passwd = profile_obj.credentials['passwd']
        except (AttributeError, TypeError):
            raise ValueError('Credentials in profile are missing')

        # whether misconfiguration findings should be only logged or cause an
        # exception to be raised
        self._permissive = permissive

        # fetched at verification time
        self._facts = None
    # __init__()

    def _exec_ansible(self, module, args=None):
        """
        Helper method to call ansible and return its output

        Args:
            module (str): ansible module to execute
            args (str): optional module arguments

        Returns:
            str: output from module execution

        Raises:
            RuntimeError: if module execution fails
            SystemError: if module output can't be parsed
            ConnectionError: if ansible can't connect to target system
        """
        process_env = os.environ.copy()
        process_env['ANSIBLE_SSH_PIPELINING'] = 'true'
        process_env['ANSIBLE_HOST_KEY_CHECKING'] = 'false'

        with NamedTemporaryFile(mode='w') as file_fd:
            file_fd.write(
                '{0} ansible_host={0} ansible_user={1} '
                'ansible_ssh_pass={2}\n'.format(
                    self._hostname, self._user, self._passwd))
            file_fd.flush()

            # we use the default 'minimal' stdout callback for stable output
            # parsing
            cmd = ['ansible', '-i', file_fd.name, self._hostname, '-m', module]
            if args:
                cmd.extend(['-a', args])
            try:
                output = subprocess.check_output(
                    cmd, stderr=subprocess.STDOUT, env=process_env,
                    universal_newlines=True)
            except subprocess.CalledProcessError as exc:
                error_fields = exc.output.split('|', 1)
                if len(error_fields) < 2:
                    raise SystemError(
                        'Unknown error, output: {}'.format(exc.output))

                # determine from the output whether it was a connection error
                # (i.e. unreachable hostname, authentication error) or a module
                # error (i.e. invalid command, command failed)
                if error_fields[1].lstrip().startswith('UNREACHABLE!'):
                    raise ConnectionError(
                        'Connection failed, output: {}'.format(exc.output))

                raise RuntimeError(
                    'Command failed, output: {}'.format(exc.output))

        # extract output, it might come in different formats depending on the
        # module used
        try:
            cmd_output = output.split('| SUCCESS =>', 1)[1]
        except IndexError:
            try:
                cmd_output = output.split(' >>\n', 1)[1]
            except IndexError:
                raise SystemError(
                    'Could not parse command output: {}'.format(output)
                ) from None

        return cmd_output
    # _exec_ansible()

    def _fetch_facts(self):
        """
        Get and store 'ansible facts' from a target instance.

        Raises:
            ConnectionError: if connection to the system cannot be established
            SystemError: in case ansible output can't be parsed
        """
        params = self._exec_ansible('setup')

        # ansible's output has additional service info, so we need to clean it
        try:
            params = json.loads(params)['ansible_facts']
        # different exceptions can happen here so we do a catch-all
        except Exception as exc:
            raise SystemError(
                'Could not parse output from ansible facts: {}'.format(
                    str(exc)))

        # Ansible does not provide partition information for FCP devices and
        # in the DASD case the entries are by kernel device name which cannot
        # be matched with our channel based device name. Therefore we create
        # additional entries with the necessary information.
        for svol in self._expected_params['storage']:
            devpath = svol['devpath']
            # call might fail if disk is not available
            parted_output = self._exec_ansible(
                'parted', 'device={} unit=B state=info'.format(devpath))
            try:
                parted_json = json.loads(parted_output)
            # should not happen as ansible output is stable
            except Exception as exc:
                raise SystemError(
                    'Could not parse parted output of disk {}: {}'.format(
                        devpath, str(exc)))

            # fetch mount point information
            lsblk_lines = self._exec_ansible(
                'command',
                'lsblk --raw --noheadings --output FSTYPE,MOUNTPOINT {}'
                .format(devpath)
            ).strip().splitlines()
            for i in range(0, len(parted_json['partitions'])):
                try:
                    line_fields = lsblk_lines[i].strip().split()
                # should not happen as the lists sizes should be the same
                except IndexError:
                    parted_json['partitions'][i]['fs'] = None
                    parted_json['partitions'][i]['mp'] = None
                    continue

                try:
                    parted_json['partitions'][i]['fs'] = line_fields[0]
                # partition has no filesystem (i.e. extended)
                except IndexError:
                    parted_json['partitions'][i]['fs'] = None
                    parted_json['partitions'][i]['mp'] = None
                    continue

                try:
                    parted_json['partitions'][i]['mp'] = line_fields[1]
                # no mount point for this partition
                except IndexError:
                    parted_json['partitions'][i]['mp'] = None

            params['ansible_devices'][devpath] = parted_json

        # FCP paths - not provided by ansible
        params['fcp_paths'] = self._fetch_fcp()

        # allocated crash kernel memory - not provided by ansible
        params['kexec_crash_size'] = int(self._exec_ansible(
            'command', 'cat /sys/kernel/kexec_crash_size'))

        # fetch pretty name from standard os-release file
        params['os_name'] = self._fetch_os()

        # threads per core (smt enabled/disabled) - not provided by
        # ansible on s390x
        params['ansible_processor_threads_per_core'] = self._fetch_smt()

        self._facts = params
    # _fetch_facts()

    def _fetch_fcp(self):
        """
        Get FCP information from a target instance.

        Returns:
            list: a list with all FCP entries or None if no FCP configured
        """
        try:
            fcp_entries = self._exec_ansible(
                'command', 'lszfcp -D').splitlines()
        # no fcp available/configured on the system
        except RuntimeError:
            return None

        fcp_paths = dict.fromkeys(
            [entry.partition(' ')[0] for entry in fcp_entries])

        return fcp_paths
    # _fetch_fcp()

    def _fetch_os(self):
        """
        Extract pretty name from standard os-release file
        """
        file_content = self._exec_ansible('command', 'cat /etc/os-release')
        for line in file_content.splitlines():
            match = re.search('^PRETTY_NAME=(.*)', line)
            if match:
                return match.group(1).strip('"')

        raise SystemError('Could not detect OS name')
    # _fetch_os()

    def _fetch_smt(self):
        """
        Extract the number of threads per core (smt enabled/disabled)
        """
        try:
            lscpu_lines = self._exec_ansible('command', "lscpu")
        except RuntimeError:
            return 1
        for line in lscpu_lines.splitlines():
            if line.startswith('Thread(s) per core:'):
                return int(line.split()[-1])
        # information not found: assume smt disabled as default
        return 1
    # _fetch_smt()

    def _pass_or_report(self, param_name, expected_value, actual_value):
        """
        Helper method, compare required parameter with actual one and raise
        exception if they don't match.

        Args:
            param_name (str): name of parameter to report in case of error
            expected_value (any): expected value
            actual_value (any): actual value

        Raises:
            Misconfiguration: if values don't match
        """
        if expected_value != actual_value:
            self._report(param_name, expected_value, actual_value)
    # _pass_or_report()

    def _pass_or_report_ipv4(self, iface_name, exp_addr, actual_iface):
        """
        Validate an ipv4 IP address and network range

        Args:
            iface_name (str): name of interface containing address
            exp_addr (dict): dict with expected ip and network addresses
            actual_iface (dict): iface entry from ansible facts

        Raises:
            Misconfiguration: if ip or network address don't match
        """
        try:
            actual_ip = actual_iface['ipv4']['address']
        # no ip assigned to the interface
        except KeyError:
            self._report(
                'iface {} ip'.format(iface_name), exp_addr['address'], None)

        # validate address
        self._pass_or_report(
            'iface {} ip'.format(iface_name), exp_addr['address'], actual_ip)

        # validate network subnet
        actual_net_str = '{}/{}'.format(
            actual_iface['ipv4']['network'], actual_iface['ipv4']['netmask'])
        try:
            actual_net_obj = ipaddress.ip_network(actual_net_str)
        # an invalid address should never occur, ansible provides valid values
        except ValueError:
            self._report('iface {} subnet'.format(iface_name),
                         exp_addr['network'], actual_net_str)
        self._pass_or_report(
            'iface {} subnet'.format(iface_name),
            ipaddress.ip_network(exp_addr['network']).with_netmask,
            actual_net_obj.with_netmask
        )
    # _pass_or_report_ipv4()

    def _pass_or_report_ipv6(self, iface_name, exp_addr, actual_iface):
        """
        Validate an ipv6 IP address and network range

        Args:
            iface_name (str): name of interface containing address
            exp_addr (dict): dict with expected ip and network addresses
            actual_iface (dict): iface entry from ansible facts

        Raises:
            Misconfiguration: if ip or network address don't match
        """
        try:
            actual_entry = actual_iface['ipv6'][0]
        # no ip assigned to the interface
        except IndexError:
            self._report(
                'iface {} ip'.format(iface_name), exp_addr['address'], None)

        # validate address
        exp_ip_obj = ipaddress.ip_address(exp_addr['address'])
        try:
            actual_ip_obj = ipaddress.ip_address(actual_entry['address'])
        # an invalid address should never occur, ansible provides valid values
        except ValueError:
            self._report('iface {} ip'.format(iface_name),
                         exp_addr['address'], actual_entry['address'])
        self._pass_or_report('iface {} ip'.format(iface_name),
                             str(exp_ip_obj), str(actual_ip_obj))

        # validate network subnet - for ipv6 checking the prefix is enough
        # as we have already checked the network as part of the address
        exp_prefixlen = ipaddress.ip_network(exp_addr['network']).prefixlen
        try:
            actual_prefixlen = int(actual_entry['prefix'])
        # an invalid prefix should never occur, ansible provides valid values
        except ValueError:
            self._report('iface {} ipv6 prefix'.format(iface_name),
                         exp_prefixlen, actual_entry['prefix'])

        self._pass_or_report('iface {} ipv6 prefix'.format(iface_name),
                             exp_prefixlen, actual_prefixlen)
    # _pass_or_report_ipv6()

    def _pass_or_report_mo(self, devpath, part_num, expected, actual):
        """
        Helper to validate if an expected list of mount options is included in
        the actual list.

        Args:
            devpath (str): device path on fs to report in case of error
            part_num (str): partition order on disk to report in case of error
            expected (str): mount options expected, separated by comma
            actual (str): actual mount options, separated by comma

        Raises:
            Misconfiguration: in case an expected mount option is not found
        """
        exp_options = expected.split(',')
        actual_options = actual.split(',')
        for option in exp_options:
            # option found: check next
            if option in actual_options:
                continue
            self._logger.warning(
                'Mount option expected for partnum %s disk %s was %s, '
                'but is not applied. Note that some Linux distributions '
                'have errors related to using certain mount options. You '
                'can skip this difference, otherwise try to set these '
                'parameters manually.',
                part_num, devpath, exp_options)
    # _pass_or_report_mo()

    def _pass_or_report_part(self, devpath, part_pos, exp_part, actual_part):
        """
        Validate if a partition entry has its attributes as expected.

        Args:
            devpath (str): volume device path
            part_pos (int): partition position in table
            exp_part (dict): partition entry from db
            actual_part (dict): partition entry from facts

        Raises:
            Misconfiguration: in case any parameter value does not match
        """
        # work with a tolerance
        min_size = exp_part['size'] - 100
        max_size = exp_part['size'] + 100
        # convert from bytes to mib
        actual_size = int(actual_part['size'] / 1024 / 1024)
        # size smaller than expected: report mismatch
        if actual_size < min_size:
            self._report(
                'min MiB size partnum {} disk {}'.format(part_pos, devpath),
                min_size, actual_size)
        # some distros (ubuntu) maximize disk usage, so do not consider it an
        # error and  only warn the user
        elif actual_size > max_size:
            self._logger.warning(
                'Max MiB size expected for partnum %s disk %s was %s, but '
                'actual is %s. Certain Linux installers maximize disk usage '
                'automatically therefore this difference is ignored.',
                part_pos, devpath, max_size, actual_size)

        # verify fstype
        actual_fs = actual_part['fstype']
        # normalize swap
        if 'linux-swap' in actual_part['fstype']:
            actual_fs = 'swap'
        self._pass_or_report(
            'fstype partnum {} disk {}'.format(part_pos, devpath),
            exp_part['fs'], actual_fs)

        # swap: special handling
        if exp_part['fs'] == 'swap':
            # from profile side any swap partition is automatically active
            # however from facts the partition might be of swap type and still
            # not be active, therefore we cross compare fs with mp here.
            if actual_part['mp'] != '[SWAP]':
                self._report(
                    'swap active partnum {} disk {}'.format(part_pos, devpath),
                    'true', 'false')

            # no more verifications for swap
            return

        # verify mount point
        self._pass_or_report(
            'mountpoint partnum {} disk {}'.format(part_pos, devpath),
            exp_part['mp'], actual_part['mp'])

        # no mount point or no mount options defined: skip mount options
        # verification
        if not exp_part['mp'] or not exp_part['mo']:
            return

        # facts has mount options in a different location
        mo_missed = True
        for search_mount in self._facts['ansible_mounts']:
            # not the same mount point: skip entry
            if search_mount['mount'] != exp_part['mp']:
                continue
            self._pass_or_report_mo(
                devpath, part_pos, exp_part['mo'], search_mount['options'])
            mo_missed = False
            break
        # mount option not found: report mismatch
        if mo_missed:
            self._report(
                'mountoptions partnum {} disk {}'.format(part_pos, devpath),
                exp_part['mp'], None)
    # _pass_or_report_part()

    @staticmethod
    def _parse_obj_iface(iface_obj):
        """
        Parse the object into a dictionary-based format recognized by the
        methods in this class.

        Args:
            iface_obj (SystemIface): db's object

        Returns:
            dict: dictionary with keys in format expected by this class
        """
        iface = {
            'attributes': deepcopy(iface_obj.attributes),
            'osname': iface_obj.osname,
            'mac': iface_obj.mac_address,
            'type': iface_obj.type,
            'addresses': [],
            'nameservers': set(),
        }

        # ip address associated: parse it
        if iface_obj.ip_address_rel:
            # today the db schema allows only one ip associated, in future when
            # this changes to allow multiple addresses we can point to the
            # relationship directly
            parse_addresses = [iface_obj.ip_address_rel]
        else:
            parse_addresses = []

        for addr in parse_addresses:
            entry = {
                'address': addr.address,
                'network': addr.subnet_rel.address,
            }
            if addr.subnet_rel.dns_1:
                iface['nameservers'].add(addr.subnet_rel.dns_1)
            if addr.subnet_rel.dns_2:
                iface['nameservers'].add(addr.subnet_rel.dns_2)
            iface['addresses'].append(entry)

        return iface
    # _parse_obj_iface()

    def _parse_obj_profile(self, profile_obj, os_obj=None):
        """
        Convert the system profile object to a dict in the form expected by the
        class.

        Args:
            profile_obj (SystemProfile): system activation profile object.
            os_obj (OperatingSystem): os object, if not specified use from
                                        system profile

        Returns:
            dict: a dictionary with the parsed parameters.
        """
        params = {
            # cpu is a flat value, no parsing needed
            'cpu': profile_obj.cpu,
            # memory is a flat value, no parsing needed
            'memory': profile_obj.memory
        }

        if os_obj:
            params['os'] = os_obj.pretty_name
        # os not specified: use from system profile
        elif profile_obj.operating_system_rel:
            params['os'] = profile_obj.operating_system_rel.pretty_name
        else:
            self._logger.warning(
                'System profile has no OS defined, skipping OS check')
            params['os'] = None

        params['network'] = {
            'gateway': None,
            'ifaces': [],
        }
        # network interfaces exist: parse them
        if profile_obj.system_ifaces_rel:
            for entry in profile_obj.system_ifaces_rel:
                params['network']['ifaces'].append(
                    self._parse_obj_iface(entry))

            # determine gateway interface
            gw_iface = profile_obj.gateway_rel
            # gateway interface not defined: use first available
            if not gw_iface:
                gw_iface = profile_obj.system_ifaces_rel[0]
            try:
                gw_address = gw_iface.ip_address_rel.subnet_rel.gateway
            except AttributeError:
                pass
            else:
                params['network']['gateway'] = {
                    'iface': gw_iface.osname,
                    'address': gw_address
                }

        params['storage'] = []
        # storage volumes exist: parse them
        if profile_obj.storage_volumes_rel:
            for entry in profile_obj.storage_volumes_rel:
                params['storage'].append(self._parse_obj_svol(entry))

        # misc parameters
        if not profile_obj.parameters:
            params['kernel_version'] = None
        else:
            params['kernel_version'] = profile_obj.parameters.get(
                'kernel_version')

        return params
    # _parse_obj_profile()

    @staticmethod
    def _parse_obj_svol(svol_obj):
        """
        Parse the object into a dictionary-based format recognized by other
        methods in this class.

        Args:
            svol_obj (StorageVolume): db's object

        Raises:
            ValueError: in case wwid for a fcp volume is missing

        Returns:
            dict: dictionary with keys in format expected by this class
        """
        part_table = {}
        if svol_obj.part_table:
            part_table = deepcopy(svol_obj.part_table)

        # determine the device path based on its type
        if svol_obj.type == 'FCP':
            # make sure specs is filled
            fcp_schema = svol_obj.get_schema('specs')['oneOf'][0]
            try:
                validate(svol_obj.specs, fcp_schema)
            except ValidationError as exc:
                raise ValueError(
                    'FCP parameters of volume {} not set: '
                    '{}'.format(svol_obj.volume_id, exc.message))

            if svol_obj.specs['multipath']:
                prefix = '/dev/disk/by-id/dm-uuid-mpath-{}'
            else:
                prefix = '/dev/disk/by-id/scsi-{}'
            devpath = prefix.format(svol_obj.specs['wwid'])
        else:
            vol_id = svol_obj.volume_id
            if vol_id.find('.') < 0:
                vol_id = '0.0.{}'.format(vol_id)
            devpath = '/dev/disk/by-path/ccw-{}'.format(vol_id)

        svol = {
            'devpath': devpath,
            'id': svol_obj.volume_id,
            'type': svol_obj.type,
            'part_table': part_table,
            'specs': deepcopy(svol_obj.specs),
            'size': svol_obj.size
        }
        return svol
    # _parse_obj_svol()

    def _report(self, *args, **kwargs):
        """
        Log a misconfiguration warning if permissive is false, raise
        the Misconfiguration exception if permissive is true.
        """
        misconf_exc = Misconfiguration(*args, **kwargs)
        if self._permissive:
            self._logger.warning(str(misconf_exc))
            return
        raise misconf_exc
    # _report()

    def _verify_cpu(self):
        """
        Check the cpu quantity of a target instance.
        """
        expected_cpu = (self._expected_params['cpu'] *
                        self._facts['ansible_processor_threads_per_core'])
        actual_cpu = self._facts['ansible_processor_cores']
        self._pass_or_report('cpu quantity', expected_cpu, actual_cpu)
    # _verify_cpu()

    def _verify_kernel(self):
        """
        Check the kernel running in a target instance.
        """
        # TODO: kargs verification

        expected_kernel = self._expected_params['kernel_version']
        # no kernel specified: nothing to check
        if not expected_kernel:
            return
        actual_kernel = self._facts['ansible_kernel']
        self._pass_or_report('kernel version', expected_kernel, actual_kernel)
    # _verify_kernel()

    def _verify_os(self):
        """
        Check the OS name of the target instance.
        """
        if not self._expected_params['os']:
            return

        self._pass_or_report('OS name', self._expected_params['os'].strip(),
                             self._facts['os_name'].strip())
    # _verify_os()

    def _verify_memory(self):
        """
        Check memory size of a target instance.
        """
        # sizes are in binary unit (MiB)
        total_mem = int(self._facts['ansible_memtotal_mb'] +
                        (self._facts['kexec_crash_size'] / 1024 / 1024))

        min_mem = self._expected_params['memory'] - 128
        max_mem = self._expected_params['memory'] + 128
        if total_mem < min_mem:
            self._report(
                'minimum MiB memory', min_mem, total_mem)
        if total_mem > max_mem:
            self._report(
                'maximum MiB memory', max_mem, total_mem)
    # _verify_memory()

    def _verify_network(self):
        """
        Check network configuration of a target instance.
        """
        expected_gw = self._expected_params['network']['gateway']
        # gateway interface expected: verify it
        if expected_gw:
            gw_ip_obj = ipaddress.ip_address(expected_gw['address'])
            # define the ansible key based on the ip type
            ansible_gw_key = 'ansible_default_ipv4'
            if isinstance(gw_ip_obj, ipaddress.IPv6Address):
                ansible_gw_key = 'ansible_default_ipv6'
            try:
                actual_gw_ip_obj = ipaddress.ip_address(
                    self._facts[ansible_gw_key]['gateway'])
            # no gateway defined
            except KeyError:
                self._report('gateway', expected_gw['address'], None)
            except ValueError:
                self._report('gateway', expected_gw['address'],
                             self._facts[ansible_gw_key]['gateway'])
            else:
                # check gateway's address
                self._pass_or_report(
                    'gateway', str(gw_ip_obj), str(actual_gw_ip_obj))

                # check gateway's iface name
                self._pass_or_report(
                    'gateway iface',
                    expected_gw['iface'],
                    self._facts[ansible_gw_key]['interface'])

        # validate that each expected interface is present
        for exp_iface in self._expected_params['network']['ifaces']:
            try:
                actual_iface = self._facts['ansible_{}'.format(
                    exp_iface['osname'])]
            # interface not present
            except KeyError:
                self._report('iface', exp_iface['osname'], None)
                continue

            # TODO: check interface type

            # iface has mac address defined: verify it
            if exp_iface['mac']:
                self._pass_or_report(
                    'iface {} mac'.format(exp_iface['osname']),
                    exp_iface['mac'],
                    actual_iface['macaddress'])

            # validate dns servers
            for name_server in exp_iface['nameservers']:
                name_server_obj = ipaddress.ip_address(name_server)
                found = False
                for actual_name_server in \
                        self._facts['ansible_dns']['nameservers']:
                    try:
                        actual_ns_obj = ipaddress.ip_address(
                            actual_name_server)
                    # bad nameserver address: skip it
                    except ValueError:
                        continue
                    if name_server_obj == actual_ns_obj:
                        found = True
                        break
                # nameserver not found in list: report mismatch
                if not found:
                    self._pass_or_report(
                        'iface {} nameservers'.format(exp_iface['osname']),
                        name_server_obj, None)

            # verify ip address assigned to interface
            # TODO: verify multiple addresses (with alias i.e. eth0:0)
            try:
                exp_addr = exp_iface['addresses'][0]
            except IndexError:
                continue

            # convert to an aware-object to detect its type
            exp_ip_obj = ipaddress.ip_address(exp_addr['address'])
            if isinstance(exp_ip_obj, ipaddress.IPv6Address):
                self._pass_or_report_ipv6(
                    exp_iface['osname'], exp_addr, actual_iface)
            else:
                self._pass_or_report_ipv4(
                    exp_iface['osname'], exp_addr, actual_iface)
    # _verify_network()

    def _verify_storage(self):
        """
        Check storage volumes (disks) configuration of a target instance.
        """
        for svol in self._expected_params['storage']:
            # verify FCP paths
            if svol['type'] == "FCP":
                # no fcp configuration available on the host: report mismatch
                if not self._facts['fcp_paths']:
                    self._pass_or_report(
                        'fcp paths', 'fcp path for LUN {}'.format(svol['id']),
                        None)
                    continue

                # go over each fcp path combination and verify if it's there
                for exp_adapter in svol['specs']['adapters']:
                    exp_devno = exp_adapter['devno']
                    # not in full format: normalize it
                    if exp_devno.find('.') == -1:
                        exp_devno = '0.0.{}'.format(exp_devno)
                    for exp_wwpn in exp_adapter['wwpns']:
                        # build the full expected path
                        exp_path = '{}/0x{}/0x{}'.format(
                            exp_devno, exp_wwpn, svol['id'])
                        try:
                            self._facts['fcp_paths'][exp_path]
                        # fcp path not available on host
                        except KeyError:
                            self._report('fcp path', exp_path, None)

            # verify partition table
            exp_table = svol['part_table']

            devpath = svol['devpath']
            actual_table = deepcopy(self._facts['ansible_devices'][devpath])

            # verify disk size
            actual_size = int(actual_table['disk']['size'] / 1024 / 1024)
            min_size = svol['size'] - 200
            max_size = svol['size'] + 200
            # size smaller than expected: report mismatch
            if actual_size < min_size:
                self._report('min MiB size disk {}'.format(devpath),
                             min_size, actual_size)
            # it's common that the user registers the size in the db a bit
            # smaller than the actual size so we give a hint so that this can
            # be fixed.
            elif actual_size > max_size:
                self._logger.warning(
                    'Max MiB size expected for disk %s was %s, but actual is '
                    '%s. You might want to adjust the volume size in the db '
                    'entry.', devpath, max_size, actual_size)

            # expected table might be empty therefore we refer to the key
            # indirectly; past this point it's guaranteed to have a dict
            # and no indirect referencing is needed
            self._pass_or_report(
                'parttable type disk {}'.format(devpath),
                exp_table.get('type', '<empty>'),
                actual_table['disk']['table'])
            if not exp_table:
                return

            # msdos type: filter out the extended partition
            if actual_table['disk']['table'] == 'msdos':
                index = None
                for i in range(0, len(actual_table['partitions'])):
                    if actual_table['partitions'][i]['num'] == 5:
                        index = i - 1
                        break
                if index is not None:
                    actual_table['partitions'].pop(index)

            # number of partitions should be the same
            len_exp = len(exp_table['table'])
            self._pass_or_report(
                'partition quantity disk {}'.format(devpath), len_exp,
                len(actual_table['partitions']))

            # check each partition size and mount attributes
            for i in range(0, len_exp):
                self._pass_or_report_part(
                    devpath, i+1, exp_table['table'][i],
                    actual_table['partitions'][i])
    # _verify_storage()

    def verify(self, areas=None):
        """
        Compare and validate the existing configuration of a running system
        against what is expected by the system activation profile entry from
        the database.

        Args:
            areas (list): areas to check, possible values are cpu, kernel, os,
                          memory, network, storage.

        Raises:
            ValueError: in case an invalid area is specified
            Misconfiguration: if an actual parameter does not match the
                              expected value
        """
        self._fetch_facts()
        self._logger.debug(
            'expected params are: %s', pformat(self._expected_params))
        self._logger.debug(
            'facts are: %s', pformat(self._facts))

        area_map = OrderedDict({
            'cpu': self._verify_cpu,
            'kernel': self._verify_kernel,
            'os': self._verify_os,
            'memory': self._verify_memory,
            'network': self._verify_network,
            'storage': self._verify_storage,
        })
        if not areas:
            areas = area_map.keys()
        for area in areas:
            try:
                area_method = area_map[area]
            except KeyError:
                raise ValueError('Invalid area {}'.format(area))
            area_method()
    # verify()
# PostInstallChecker
