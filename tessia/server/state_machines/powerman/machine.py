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
Machine to perform power management of systems
"""

#
# IMPORTS
#
from copy import deepcopy
from datetime import datetime
from itertools import chain
from jsonschema import validate
from time import sleep, monotonic

from tessia.baselib.common.s3270.terminal import Terminal
from tessia.baselib.guests import Guest
from tessia.baselib.hypervisors.hmc import HypervisorHmc
from tessia.baselib.hypervisors.kvm import HypervisorKvm
from tessia.baselib.hypervisors.zvm import HypervisorZvm
from tessia.baselib.hypervisors.hmc.volume_descriptor import \
    FcpVolumeDescriptor
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import System, SystemProfile
from tessia.server.lib import post_install
from tessia.server.state_machines.base import BaseMachine

import logging
import yaml

#
# CONSTANTS AND DEFINITIONS
#
LOAD_TIMEOUT = 600
POWERON = 'poweron'
POWERON_EXC = 'poweron-exclusive'
POWEROFF = 'poweroff'

# Schema to validate the job request
REQUEST_SCHEMA = {
    'type': 'object',
    'properties': {
        'systems': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'action': {
                        'type': 'string',
                        "enum": [
                            POWERON,
                            POWEROFF,
                            # for future usage in nightslots
                            POWERON_EXC,
                        ]

                    },
                    'force': {
                        'type': 'boolean'
                    },
                    'name': {
                        'type': 'string'
                    },
                    'profile': {
                        'type': 'string'
                    },
                    'profile_override': {
                        'type': 'object',
                        'properties': {
                            'cpu': {
                                'type': 'number'
                            },
                            'memory': {
                                'type': 'number'
                            },
                        },
                        'additionalProperties': False
                    }
                },
                'required': [
                    'action',
                    'name',
                ],
                'additionalProperties': False
            },
            # at lest one system must be specified
            'minItems': 1,
        },
        "verbosity": {
            "type": "string",
            "enum": list(BaseMachine._LOG_LEVELS),
        },
        'verify': {
            'type': 'boolean'
        },
    },
    'required': [
        'systems',
    ],
    'additionalProperties': False
}

#
# CODE
#


class PowerManagerMachine(BaseMachine):
    """
    This machine is responsible for performing power management actions
    (poweron, poweroff) of the managed systems.
    """

    def __init__(self, params):
        """
        See base class docstring.

        Args:
            params (str): A string containing a json in the format defined by
                          the REQUEST_SCHEMA constant.
        """
        super().__init__(params)

        # make sure query attribute is available on the models by explicitly
        # connecting to db
        MANAGER.connect()

        # process params and fetch necessary data
        self._params = self._load_data(params)

        # apply custom log level if specified
        self._log_config(self._params.get('verbosity'))
        self._logger = logging.getLogger(__name__)

        # keep track of systems which already incurred in the operation to
        # avoid double work
        self._powered_off = {}
        self._powered_on = {}
    # __init__()

    @staticmethod
    def _check_profile(profile_obj):
        """
        Process the content of the activation profile to confirm it's valid.

        Args:
            profile_obj (SystemProfile): profile db object

        Raises:
            ValueError: in case some parameter is missing/invalid
        """
        # a root volume must be available
        root_vol = None
        boot_vol = None
        for vol_obj in profile_obj.storage_volumes_rel:
            if not vol_obj.part_table:
                continue
            for entry in vol_obj.part_table.get("table", []):
                if entry["mp"] == "/":
                    root_vol = vol_obj
                elif entry["mp"] == "/boot":
                    boot_vol = vol_obj

        if not boot_vol:
            boot_vol = root_vol
        if not root_vol:
            raise ValueError(
                'Profile {} has no volume containing a root partition'
                .format(profile_obj.name))
        # save reference to root volume for use in other stages
        profile_obj.root_vol = root_vol
        profile_obj.boot_vol = boot_vol

        if (profile_obj.system_rel.type.lower() == 'zvm' and
                ('zvm-password' not in profile_obj.credentials)):
            raise ValueError('z/VM guest {} has no z/VM credentials '
                             'defined'.format(profile_obj.system_rel.name))
    # _check_profile()

    def _commit_modified_time(self):
        """
        Update 'modified' timestamp on all affected systems
        """
        # Rollback all profile overrides (if any)
        MANAGER.session.rollback()

        # Set 'modified' on systems that were powered on or off
        for profile_obj in chain(self._powered_on.values(),
                                 self._powered_off.values()):
            profile_obj.system_rel.modified = datetime.utcnow()

        MANAGER.session.commit()
    # _commit_modified_time()

    @staticmethod
    def _get_profile(system_name, profile_name=None):
        """
        Perform a db query and return the profile db object

        Args:
            system_name (str): system name
            profile_name (str): if not specified search for default

        Raises:
            ValueError: in case query produces no result

        Returns:
            SystemProfile: db object
        """
        query = SystemProfile.query.join(
            'system_rel').filter(System.name == system_name)
        # profile specified: add name filter to query
        if profile_name:
            query = query.filter(SystemProfile.name == profile_name)
        # profile not specified: use filter for default
        else:
            query = query.filter(SystemProfile.default == bool(True))

        # retrieve the system profile object
        profile_obj = query.first()
        # query produced no result: fatal condition
        if not profile_obj:
            if profile_name:
                error_msg = (
                    "Specified profile {profile} for system {name} "
                    "does not exist.")
            else:
                error_msg = (
                    "Default profile for system {name} does not exist.")
            raise ValueError(error_msg.format(
                profile=profile_name, name=system_name))

        return profile_obj
    # _get_profile()

    @staticmethod
    def _get_profile_by_id(system_id):
        """
        Helper to perform a joined query to retrieve the default profile of a
        given system id.

        Args:
            system_id (int): id of system in database

        Returns:
            SystemProfile: db object
        """
        profile_obj = SystemProfile.query.join(
            'system_rel'
        ).filter(
            System.id == system_id
        ).filter(
            SystemProfile.default == bool(True)
        ).first()
        return profile_obj
    # _get_profile_by_id()

    @classmethod
    def _get_resources(cls, systems):
        """
        Return the map of resources to be used in this job.

        Args:
            systems (list): list of dicts with the systems to be used.

        Returns:
            dict: {'shared': ['resource1'], 'exclusive': ['resource2,
                  'resource3']}

        Raises:
            ValueError: if validation of parameters fails
        """
        shared_res = set()
        exclusive_res = set()

        for system in systems:
            system_obj = System.query.filter_by(
                name=system['name']).one_or_none()

            # system does not exist in db: report error
            if system_obj is None:
                raise ValueError("System '{}' does not exist.".format(
                    system['name']))

            # profile not available: report error
            cls._get_profile(
                system['name'], system.get('profile'))

            # sanity check, without hypervisor it's not possible to power
            # manage system
            if not system_obj.hypervisor_id:
                raise ValueError(
                    'System {} cannot be managed because it has no '
                    'hypervisor defined'.format(system_obj.name)
                )

            exclusive_res.add(system_obj.name)

            # system is in poweron-exclusive mode: all other systems of same
            # hypervisor will be turned off therefore they need to be
            # blocked too
            if system['action'] == POWERON_EXC:
                siblings = System.query.filter(
                    System.hypervisor_id == system_obj.hypervisor_id
                ).filter(
                    System.name != system_obj.name
                ).all()
                for other_system in siblings:
                    exclusive_res.add(other_system.name)

            # the hypervisor hierarchy is a shared resource
            system_obj = system_obj.hypervisor_rel
            while system_obj:
                shared_res.add(system_obj.name)
                system_obj = system_obj.hypervisor_rel

        resources = {
            'shared': list(shared_res),
            'exclusive': list(exclusive_res)
        }
        return resources
    # _get_resources()

    def _start_hypervisor_lpar(self, hyp_prof, guest_prof):
        """
        Define the parameters in baselib format to start a LPAR system

        Args:
            hyp_prof (SystemProfile): hypervisor profile db object
            guest_prof (SystemProfile): guest profile db object

        Raises:
            ValueError: in case no root volume is defined

        Returns:
            tuple: containing init and start parameters
        """
        if not hasattr(guest_prof, 'root_vol'):
            raise ValueError(
                'Profile {} has no volume containing a root partition'
                .format(guest_prof.name))
        root_vol = guest_prof.root_vol

        parameters = None
        if hyp_prof.credentials.get('private-key'):
            parameters = {
                    'private-key': hyp_prof.credentials['private-key']
                    }

        baselib_hyp = HypervisorHmc(
            hyp_prof.system_rel.name, hyp_prof.system_rel.hostname,
            hyp_prof.credentials['admin-user'],
            hyp_prof.credentials['admin-password'], parameters)
        # login to hypervisor, but do not start machine
        baselib_hyp.login()

        params = {}
        if root_vol.type.lower() == 'fcp':
            # NOTE: wwid corresponds to volume uuid with a one-digit prefix,
            # so we can obtain one from the other, but not the other way around
            root_vol_uuid = root_vol.specs['wwid'][1:].lower()
            if not root_vol.specs.get('adapters'):
                self._logger.debug("Querying HMC for storage configuration")
                # there are no adapters defined - query hypervisor for them
                storage_descriptors = baselib_hyp.query_dpm_storage_devices(
                    guest_prof.system_rel.name)
                # find first one matching volume wwpn
                root_desc = [volume for volume in storage_descriptors
                             if isinstance(volume, FcpVolumeDescriptor)
                             and volume.uuid.lower() == root_vol_uuid]
                if not root_desc:
                    raise ValueError(
                        'Cannot boot: found no volume mathcing UUID {}'
                        'that is specified for FCP volume {}'.format(
                            root_vol_uuid, root_vol.volume_id
                        ))
                volume_desc = root_desc[0]
                if not volume_desc.paths:
                    raise ValueError(
                        'Cannot boot: no paths found for FCP volume {}'.format(
                            root_vol.volume_id))

                path = volume_desc.paths[0]
                params['boot_params'] = {
                    'boot_method': 'scsi',
                    'devicenr': path['device_nr'].lower(),
                    'wwpn': path['wwpn'].lower(),
                    'lun': path['lun'],
                    'uuid': volume_desc.uuid,
                }
            else:
                params['boot_params'] = {
                    'boot_method': 'scsi',
                    'devicenr': root_vol.specs['adapters'][0]['devno'],
                    'wwpn': root_vol.specs['adapters'][0]['wwpns'][0],
                    'lun': root_vol.volume_id,
                    'uuid': root_vol_uuid,
                }
        elif root_vol.type.lower() == 'nvme':
            params['boot_params'] = {
                'boot_method': 'nvme',
                'devicenr': root_vol.volume_id
            }
        else:
            params['boot_params'] = {
                'boot_method': 'dasd',
                'devicenr': root_vol.volume_id
            }

        baselib_hyp.start(guest_prof.system_rel.name, guest_prof.cpu,
                          guest_prof.memory, params)

        baselib_hyp.logoff()
    # _start_hypervisor_lpar()

    @staticmethod
    def _start_hypervisor_kvm(hyp_prof, guest_prof):
        """
        Define the parameters in baselib format to start a KVM guest system

        Args:
            hyp_prof (SystemProfile): hypervisor profile db object
            guest_prof (SystemProfile): guest profile db object

        Raises:
            ValueError: in case libvirt definitions are missing

        Returns:
            tuple: containing init and start parameters
        """
        # prepare entries in the format expected by baselib
        svols = []
        for vol_obj in guest_prof.storage_volumes_rel:
            try:
                vol_obj.system_attributes['libvirt']
            except KeyError:
                raise ValueError(
                    'Volume {} has a libvirt definition missing, '
                    'perform a system installation to create a valid entry'
                    .format(vol_obj.volume_id)) from None

            result = {
                "type": vol_obj.type_rel.name,
                "volume_id": vol_obj.volume_id,
                "system_attributes": vol_obj.system_attributes,
                "specs": vol_obj.specs,
            }
            svols.append(result)

        # network interfaces
        ifaces = []
        for iface_obj in guest_prof.system_ifaces_rel:
            result = {
                "attributes": iface_obj.attributes,
                "mac_address": iface_obj.mac_address,
                "type": iface_obj.type
            }
            ifaces.append(result)

        params = {
            'ifaces': ifaces,
            'storage_volumes': svols,
            'parameters': {
                'boot_method': 'disk'
            }
        }
        baselib_hyp = HypervisorKvm(
            hyp_prof.system_rel.name, hyp_prof.system_rel.hostname,
            hyp_prof.credentials['admin-user'],
            hyp_prof.credentials['admin-password'], None)
        baselib_hyp.login()
        baselib_hyp.start(guest_prof.system_rel.name, guest_prof.cpu,
                          guest_prof.memory, params)
        baselib_hyp.logoff()
    # _start_hypervisor_kvm()

    @staticmethod
    def _start_hypervisor_zvm(hyp_prof, guest_prof):
        """
        Define the parameters in baselib format to start a zVM guest system

        Args:
            hyp_prof (SystemProfile): hypervisor profile db object
            guest_prof (SystemProfile): guest profile db object

        Returns:
            tuple: containing init and start parameters

        Raises:
            ValueError: if zVM credentials are not defined
        """
        # prepare entries in the format expected by baselib
        svols = []
        for vol_obj in guest_prof.storage_volumes_rel:
            result = {'type': vol_obj.type_rel.name.lower()}
            if result['type'] != 'fcp':
                result['devno'] = vol_obj.volume_id.split('.')[-1]
            else:
                result['adapters'] = deepcopy(vol_obj.specs['adapters'])
                result['lun'] = vol_obj.volume_id
            if guest_prof.root_vol is vol_obj:
                result['boot_device'] = True
            svols.append(result)

        # network interfaces
        ifaces = []
        for iface_obj in guest_prof.system_ifaces_rel:
            # use only the base address
            if iface_obj.type.lower() == 'osa':
                ccw_base = []
                for channel in iface_obj.attributes['ccwgroup'].split(','):
                    ccw_base.append(channel.split('.')[-1])
                result = {
                    'id': ','.join(ccw_base),
                    'type': iface_obj.type.lower(),
                }
            elif iface_obj.type.lower() == 'roce':
                result = {
                    'id': iface_obj.attributes['fid'],
                    'type': 'pci',
                }
            else:
                raise ValueError('Unsupported network card type {}'
                                 .format(iface_obj.type))

            ifaces.append(result)

        # define args for the class constructor
        if guest_prof.credentials.get('zvm-logonby'):
            init_params = {'byuser': guest_prof.credentials['zvm-logonby']}
        else:
            init_params = None

        baselib_hyp = HypervisorZvm(
            hyp_prof.system_rel.name, hyp_prof.system_rel.hostname,
            guest_prof.system_rel.name,
            guest_prof.credentials['zvm-password'],
            init_params)
        baselib_hyp.login()
        # define args for the start call
        start_params = {
            'ifaces': ifaces,
            'storage_volumes': svols,
            'boot_method': 'disk',
        }
        baselib_hyp.start(guest_prof.system_rel.name, guest_prof.cpu,
                          guest_prof.memory, start_params)
        baselib_hyp.logoff()
    # _start_hypervisor_zvm()

    @staticmethod
    def _is_system_up(system_prof, guest_prof=None):
        """
        Verify if a given system is up by opening a connection to it.

        Args:
            system_prof (SystemProfile): profile object of system to check
            guest_prof (SystemProfile): (used for zvm) profile db object of
                guest containing zvm credentials for login

        Returns:
            bool: True if system is up, False otherwise

        Raises:
            ValueError: in case system_prof uses CMS but guest_prof is None
            Exception: underlying exception from baselib
        """
        system_obj = system_prof.system_rel

        os_obj = system_prof.operating_system_rel
        # linux based systems: use normal guest class
        if not os_obj or (os_obj.type.lower() not in ('cms', 'zcms')):
            try:
                guest_obj = Guest(
                    'linux', system_obj.name, system_obj.hostname,
                    system_prof.credentials['admin-user'],
                    system_prof.credentials['admin-password'], None)
                # small timeout, we don't want to wait for long if the system
                # is down
                guest_obj.login(timeout=15)
                guest_obj.logoff()
            except PermissionError:
                # PermissionError is acceptable,
                # because in this case the system is responsive
                return True

            return True

        # system is a z/VM hypervisor: need credentials from guest to login
        if not guest_prof:
            raise ValueError(
                f'Cannot login to CMS on {system_obj.name}: '
                'no z/VM guest defined with credentials')
        if 'zvm-password' not in guest_prof.credentials:
            raise ValueError(
                f'z/VM guest {guest_prof.system_rel.name} '
                'has no z/VM credentials defined')
        if not guest_prof.credentials['zvm-password']:
            raise ValueError(
                f'z/VM guest {guest_prof.system_rel.name} '
                'has empty z/VM password defined. '
                'Please set the correct password.')
        term_obj = Terminal()
        guest_params = {'here': True, 'noipl': True}
        if guest_prof.credentials.get('zvm-logonby'):
            guest_params['byuser'] = guest_prof.credentials['zvm-logonby']
        try:
            term_obj.login(
                system_obj.hostname, guest_prof.system_rel.name,
                guest_prof.credentials['zvm-password'],
                # small timeout, we don't want to wait for long if the
                # system is down
                guest_params, timeout=15)
            term_obj.disconnect()
        except PermissionError:
            # ignore PermissionError here, it will be raised somewhere else
            return True

        return True
    # _is_system_up()

    def _load_data(self, user_params):
        """
        Load all the necessary data for the machine to work.

        Args:
            user_params (str): request params according to REQUEST_SCHEMA

        Returns:
            dict: containing data required by the machine to run

        Raises:
            SyntaxError: in case request is in wrong format
            ValueError: if any system data is inconsistent for the operation
        """
        try:
            params = yaml.safe_load(user_params)
            validate(params, REQUEST_SCHEMA)
        # this exception should never happen as the request was already
        # validated by parse()
        except Exception as exc:
            raise SyntaxError(
                "Invalid request parameters: {}".format(str(exc))
            ) from None

        for system in params['systems']:
            system_obj = System.query.filter_by(
                name=system['name']).one_or_none()

            # system does not exist in db: report error
            if system_obj is None:
                raise ValueError("System '{}' does not exist.".format(
                    system['name']))

            # sanity check, without hypervisor it's not possible to manage
            # system
            if not system_obj.hypervisor_id:
                raise ValueError(
                    'System {} cannot be managed because it has no '
                    'hypervisor defined'.format(system_obj.name))

            profile_obj = self._get_profile(
                system['name'], system.get('profile'))
            # check if profile has valid values
            self._check_profile(profile_obj)

            hyp_profile_obj = profile_obj.hypervisor_profile_rel
            # no hypervisor profile defined: use default
            if not hyp_profile_obj:
                hyp_profile_obj = self._get_profile_by_id(
                    system_obj.hypervisor_id)
                if not hyp_profile_obj:
                    raise ValueError(
                        'Hypervisor {} of system {} has no default profile '
                        'defined'.format(system_obj.hypervisor_rel.name,
                                         system_obj.name))

            # store references to the objects
            system['profile_obj'] = profile_obj
            system['hyp_chain_objs'] = []
            system['sibling_objs'] = []

            # for poweroff only the immediate hypervisor is needed
            if system['action'] == POWEROFF:
                system['hyp_chain_objs'].append(hyp_profile_obj)
                continue

            # for poweron operations we need to check the complete chain to
            # be sure hypervisors are up and match expected profiles, for
            # that we build a list where the root hypervisor is the first item.
            parent_profile = hyp_profile_obj
            while True:
                system['hyp_chain_objs'].insert(0, parent_profile)
                next_parent = parent_profile.system_rel.hypervisor_rel
                # system has no hypervisor: end of hypervisor chain
                if not next_parent:
                    break
                parent_profile = parent_profile.hypervisor_profile_rel
                # no parent profile defined: use default
                if not parent_profile:
                    parent_profile = self._get_profile_by_id(
                        next_parent.id)
                    if not parent_profile:
                        raise ValueError(
                            'System {} has no default profile defined'
                            .format(next_parent.name))

            # for exclusive poweron we also need to collect the siblings
            # that will be powered off
            if system['action'] == POWERON_EXC:
                sibling_systems = System.query.filter(
                    System.hypervisor_id == system_obj.hypervisor_id
                ).filter(
                    System.name != system_obj.name
                ).all()
                # TODO: for now we just assume all siblings are running
                # with the default profile to use as credentials for
                # logging, this should be improved to use ssh private key
                # instead.
                for sibling in sibling_systems:
                    system['sibling_objs'].append(
                        self._get_profile(sibling.name))

        return params
    # _load_data()

    def _poweroff(self, hyp_prof, guests):
        """
        Perform the actual poweroff operation on a list of systems.

        Args:
            hyp_prof (SystemProfile): hypervisor to connect to perform the
                                      poweroff of the guest
            guests (list or SystemProfile): SystemProfile of the guest to be
                                          powered off
        Raises:
            ValueError: if system type is unknown
        """
        if not isinstance(guests, list):
            guests = [guests]

        # determine the hypervisor type for baselib call
        hyp_type = hyp_prof.system_rel.type.lower()
        os_obj = hyp_prof.operating_system_rel

        # z/VM hypervisor: use specialized function
        if (hyp_type != 'cpc' and os_obj and
                os_obj.type.lower() in ('cms', 'zcms')):
            for guest_prof in guests:
                system_name = guest_prof.system_rel.name
                self._logger.info('Powering off system %s', system_name)
                self._poweroff_zvm(hyp_prof, guest_prof)
                self._powered_off[system_name] = guest_prof
                self._logger.info(
                    'System %s successfully powered off', system_name)
            return

        # normalize names for baselib
        try:
            hyp_class = {'cpc': HypervisorHmc, 'lpar': HypervisorKvm}[hyp_type]
        except KeyError:
            raise ValueError("Unknown type '{}' for system {}".format(
                hyp_type, hyp_prof.system_rel.name))

        baselib_hyp = hyp_class(
            hyp_prof.system_rel.name, hyp_prof.system_rel.hostname,
            hyp_prof.credentials['admin-user'],
            hyp_prof.credentials['admin-password'], None)
        baselib_hyp.login()
        for guest_prof in guests:
            system_name = guest_prof.system_rel.name
            self._logger.info('Powering off system %s', system_name)
            baselib_hyp.stop(system_name, {})
            self._powered_off[system_name] = guest_prof
            self._logger.info(
                'System %s successfully powered off', system_name)

        baselib_hyp.logoff()
    # _poweroff()

    @staticmethod
    def _poweroff_zvm(hyp_prof, guest_prof):
        """
        Perform the poweroff operation on a list of zVM guests.
        """
        guest_name = guest_prof.system_rel.name

        init_params = {}
        try:
            init_params['byuser'] = guest_prof.credentials['zvm-logonby']
        except KeyError:
            pass

        baselib_hyp = HypervisorZvm(
            hyp_prof.system_rel.name,
            hyp_prof.system_rel.hostname,
            guest_name,
            guest_prof.credentials['zvm-password'],
            init_params)
        baselib_hyp.login()
        baselib_hyp.stop(guest_name, {})
    # _poweroff_zvm()

    def _poweron(self, hyp_prof, guest_prof, overrides=None):
        """
        Perform the actual poweron operation on a system

        Args:
            hyp_prof (SystemProfile): hypervisor of the guest
            guest_prof (SystemProfile): guest to be powered on
            overrides (dict): overrides for profile

        Raises:
            ValueError: in case guest type is unsupported
        """
        system_name = guest_prof.system_rel.name
        self._logger.info('Executing poweron of system %s', system_name)

        # custom values specified: apply them
        if overrides:
            # mark object as overriden so that the state_match() method can
            # properly report its activity
            guest_prof.overriden = True
            msg_overrides = []
            if 'cpu' in overrides:
                guest_prof.cpu = overrides['cpu']
                msg_overrides.append('cpu={}'.format(guest_prof.cpu))
            if 'memory' in overrides:
                guest_prof.memory = overrides['memory']
                msg_overrides.append('memory={}MiB'.format(guest_prof.memory))
            self._logger.info('Overriding profile with custom values: %s',
                              ', '.join(msg_overrides))

        system_type = guest_prof.system_rel.type.lower()
        if system_type == 'lpar':
            self._start_hypervisor_lpar(hyp_prof, guest_prof)
        elif system_type == 'kvm':
            self._start_hypervisor_kvm(hyp_prof, guest_prof)
        elif system_type == 'zvm':
            self._start_hypervisor_zvm(hyp_prof, guest_prof)
        else:
            raise ValueError(
                'Unsupported system type {}'.format(system_type)
            )

        self._powered_on[guest_prof.system_rel.name] = guest_prof
        self._logger.info('System %s successfully powered on', system_name)
    # _poweron()

    def _stage_exec(self):
        """
        Perform the power action (poweron/poweroff) for each system specified.
        """
        for system in self._params['systems']:
            profile_obj = system['profile_obj']
            system_obj = profile_obj.system_rel
            # the immediate hypervisor is at the end of the list
            hyp_profile_obj = system['hyp_chain_objs'][-1]

            # report the hierarchy so that the user understands what's going on
            self._logger.info('Current action is %s system %s',
                              system['action'], system_obj.name)
            topology = [
                '{} ({})'.format(obj.system_rel.name, obj.system_rel.type)
                for obj in system['hyp_chain_objs']
            ] + ['{} ({})'.format(system_obj.name, system_obj.type)]
            self._logger.info('System topology is: %s', ' -> '.join(topology))

            # poweroff requested
            if system['action'] == POWEROFF:
                if system_obj.name in self._powered_off:
                    self._logger.info('System %s was already powered off, '
                                      'skipping', system_obj.name)
                else:
                    self._poweroff(hyp_profile_obj, profile_obj)
                # proceed to next system
                continue

            # we need to check the complete chain to be sure that the
            # hypervisors are up and that they match expected profiles
            # cpc is not checked
            start_pos = 0
            if system['hyp_chain_objs'][0].system_rel.type.lower() == 'cpc':
                start_pos = 1
            for i in range(start_pos, len(system['hyp_chain_objs'])):
                hyp_profile = system['hyp_chain_objs'][i]
                # retrieve also the guest profile in order to have login
                # credentials for eventual z/VM hypervisors
                try:
                    guest_profile = system['hyp_chain_objs'][i+1]
                # last entry: guest is the target system
                except IndexError:
                    guest_profile = profile_obj

                self._logger.info('Checking if hypervisor %s is up',
                                  hyp_profile.system_rel.name)
                # hypervisor not up: not possible to activate system
                try:
                    self._is_system_up(hyp_profile, guest_profile)
                except Exception as exc:
                    raise RuntimeError(
                        f'Cannot poweron system {system_obj.name}, '
                        f'hypervisor {hyp_profile.system_rel.name} is not up'
                    ) from exc
                self._logger.info(
                    'Hypervisor %s is up', hyp_profile.system_rel.name)
                # hypervisor is up but profile doesn't match: fatal error,
                # cannot continue
                if (not self._state_match(hyp_profile) and
                        self._params.get('verify')):
                    raise RuntimeError(
                        'Cannot poweron system {} because hypervisor {} does '
                        'not match expected profile {}'.format(
                            system_obj.name, hyp_profile.system_rel.name,
                            hyp_profile.name)
                    )

            # exclusive operation: siblings must be powered off
            if system['action'] == POWERON_EXC:
                self._logger.info(
                    'Exclusive poweron requested for system %s, powering '
                    'off all sibling systems: %s', profile_obj.system_rel.name,
                    ', '.join([obj.system_rel.name
                               for obj in system['sibling_objs']])
                )

                # TODO: replace usage of credentials by ssh private key
                for sibling_prof in system['sibling_objs']:
                    sibling_system = sibling_prof.system_rel
                    if sibling_prof.system_rel.name in self._powered_off:
                        self._logger.info(
                            'System %s was already powered off, skipping',
                            sibling_system.name)
                        continue
                    self._poweroff(hyp_profile_obj, system['sibling_objs'])

            self._logger.info('Checking if target system %s is already up',
                              system_obj.name)
            # system is already up: additional verifications are needed
            try:
                system_is_up = self._is_system_up(profile_obj)
            except Exception as exc:
                system_is_up = False
                self._logger.info('System %s is not up', system_obj.name)
                self._logger.debug('is_system_up check raised %s', exc)

            if system_is_up:
                self._logger.info('System is already up')
                # force enabled: we need to poweroff the system first
                if system.get('force'):
                    self._logger.info(
                        'Force flag was specified therefore restart is needed')
                    self._poweroff(hyp_profile_obj, profile_obj)
                # overrides enabled: we need to poweroff the system in order to
                # boot with the new values
                elif system.get('profile_override'):
                    self._logger.info('Override parameters were specified '
                                      'therefore restart is needed')
                    self._poweroff(hyp_profile_obj, profile_obj)
                elif not self._state_match(profile_obj):
                    self._logger.info('Current state does not match profile '
                                      'therefore restart is needed')
                    self._poweroff(hyp_profile_obj, profile_obj)
                # system already up and match profile: nothing to do
                else:
                    self._logger.info(
                        "System %s is already running as expected, no poweron "
                        "needed", profile_obj.system_rel.name)
                    continue

            # proceed with the poweron action itself
            self._poweron(hyp_profile_obj, profile_obj,
                          system.get('profile_override'))

    # _stage_exec()

    def _stage_verify(self):
        """
        Verify for all powered on systems whether the running system's
        parameters correspond to the chosen activation profile.
        """
        for system_name, profile_obj in self._powered_on.items():
            # make sure system is already up
            self._logger.info('Waiting for system %s to come up (%s seconds)',
                              system_name, LOAD_TIMEOUT)
            timeout_secs = monotonic() + LOAD_TIMEOUT
            while True:
                try:
                    self._is_system_up(profile_obj)
                    break
                except Exception as exc:
                    if monotonic() >= timeout_secs:
                        raise TimeoutError(
                            'Could not establish a connection to system '
                            f'{system_name} after {LOAD_TIMEOUT} seconds') \
                            from exc
                    sleep(5)

            # do a state match always to log incinsitencies,
            # raise only if requested
            if (not self._state_match(profile_obj) and
                    self._params.get('verify')):
                raise RuntimeError(
                    'Failed to poweron system {} with expected configuration'
                    .format(system_name))
    # _stage_verify()

    def _state_match(self, system_prof):
        """
        Return whether the current system state matches the passed activation
        profile.

        Args:
            system_prof (SystemProfile): db object

        Raises:
            TimeoutError: in case a connection cannot be established

        Returns:
            bool: True if system matches passed profile, False otherwise
        """
        system_name = system_prof.system_rel.name

        if hasattr(system_prof, 'overriden') and system_prof.overriden:
            self._logger.info(
                'Verifying if current state of system %s matches expected '
                'configuration', system_name)
        else:
            self._logger.info(
                "Verifying if current state of system %s matches profile '%s'",
                system_name, system_prof.name)

        prof_os = system_prof.operating_system_rel
        if prof_os and prof_os.type.lower() in ('cms', 'zcms'):
            self._logger.info('Skipping check of system %s as CMS is not '
                              'supported', system_name)
            return True

        if not self._params.get('verify'):
            self._logger.info(
                'Potential configuration mismatches will be reported as '
                'warnings because verify flag is off')

        try:
            checker = post_install.PostInstallChecker(
                system_prof, permissive=True)
            # checked may still throw on unexpected errors
            mismatches = checker.verify()
        except Exception as exc:
            self._logger.warning('State verification of system %s '
                                 'failed: %s', system_name, str(exc))
            return False

        return not mismatches
    # _state_match()

    def cleanup(self):
        """
        Clean up in case of cancelation.
        """
        # When the job is canceled during a cleanup the routine
        # is not executed again by the scheduler.
        self.cleaning_up = True
        # make sure any profile overrides are discarded and not committed to
        # the db
        MANAGER.session.rollback()
    # cleanup()

    @classmethod
    def parse(cls, params):
        """
        Method called by the scheduler to validate the user's request and
        collect the resources (usually systems) to be reserved for the job.

        Args:
            params(str): A string containing a json in a format validated by
                         the SCHEMA constant

        Returns:
            dict: Resources allocated for the installation.

        Raises:
            SyntaxError: if content is in wrong format.
        """
        try:
            obj_params = yaml.safe_load(params)
            validate(obj_params, REQUEST_SCHEMA)
        except Exception as exc:
            raise SyntaxError(
                "Invalid request parameters: {}".format(str(exc))) from None

        # make sure query attribute is available on the models by explicitly
        # connecting to db
        MANAGER.connect()

        # resources used in this job
        used_resources = cls._get_resources(obj_params['systems'])

        systems_list = ', '.join(used_resources['exclusive'][:3])
        if len(used_resources['exclusive']) > 3:
            systems_list += ' (more)'
        result = {
            'resources': used_resources,
            'description': 'Power manage systems {}'.format(systems_list)
        }
        return result
    # parse()

    def start(self):
        """
        Start the machine execution.
        """
        self._logger.info('new stage: execute-action')
        self._stage_exec()

        self._logger.info('new stage: verify-configuration')
        self._stage_verify()

        self._logger.info('new stage: commit-modified')
        self._commit_modified_time()

        self._logger.info('Task finished successfully')
        return 0
    # start()
# PowerManagerMachine
