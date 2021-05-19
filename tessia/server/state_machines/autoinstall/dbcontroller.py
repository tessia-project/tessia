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
Autoinstall machine database controller

Controller transforms database into machine model and
provides writeback interface to database
"""

# pylint: disable=no-self-use
# There is an implicit database session in controller, even though methods
# do not call database session directly, at least for SqlAlchemy 1.3.
# Which means, a DbController instance is required anyway, and making methods
# static will not help code readability

#
# IMPORTS
#
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified
from tessia.server.db.connection import _DbManager
from tessia.server.db.models import OperatingSystem, Repository, SystemIface
from tessia.server.db.models import Template
from tessia.server.db.models import System, SystemProfile
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from urllib.parse import urlsplit

import re

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#

class DbController:
    """
    Class encapsulating database operations
    """

    def __init__(self, manager: _DbManager):
        self._manager = manager
    # __init__()

    def _get_cpc_boot_method(self, profile):
        """
        Return boot method for CPC
        """
        if (isinstance(profile.parameters, dict) and
                profile.parameters.get('liveimg-insfile-url')):
            return {
                'boot-method': 'network',
                'boot-uri': profile.parameters.get('liveimg-insfile-url')
            }
        if len(profile.storage_volumes_rel) >= 1:
            volume = profile.storage_volumes_rel[0]
            if volume.type == 'DASD':
                return {
                    'boot-method': 'storage',
                    'boot-device': volume.volume_id,
                }
            if volume.type == 'FCP':
                adapter = volume.specs.get('adapters', [None])[0]
                if not adapter:
                    raise ValueError(
                        'No adapter found for volume {} attached to '
                        'system {} profile {}'.format(
                            volume.volume_id, profile.system_rel.name,
                            profile.name
                        ))
                return {
                    'boot-method': 'storage',
                    'boot-device': adapter['devno'],
                    'boot-device-wwpn': adapter['wwpns'][0],
                    'boot-device-lun': volume.volume_id,
                    'boot-device-uuid': volume.specs.get('wwid', '')[-32:],
                }
                # NOTE: WWIDs specified in storage in general follow
                # udev rules, which commonly add a prefix '3' to volume UUID.
                # The UUID itself is 32 nibbles long, but may be 16 or
                # something else entirely. There is no exact rule to figure out
                # one from the other, but otherwise we would have to have
                # very similar data (wwid and uuid) in device configuration.

            raise ValueError("Storage {} attached to CPC {} profile {} "
                             "is not supported for live image booting".format(
                                 volume.volume_id, profile.system_rel.name,
                                 profile.name
                             ))
        if len(profile.storage_volumes_rel) == 0:
            raise ValueError(
                'CPC {} has neither an auxiliary disk (DPM and classic '
                ' mode) nor an insfile URL (DPM only) registered to '
                'serve the live-image required for installation'
                .format(profile.system_rel.name))
        return None

    def _get_iface_subnet(self, profile_iface: SystemIface):
        """
        Return SubnetAffiliation for a network interface
        """
        ip_addr = profile_iface.ip_address_rel
        if ip_addr is None:
            return None
        subnet = ip_addr.subnet_rel
        model_subnet = AutoinstallMachineModel.SubnetAffiliation(
            ip_addr.address,
            subnet.address,
            gateway=subnet.gateway,
            vlan=subnet.vlan,
            dns=[dns for dns in [subnet.dns_1, subnet.dns_2] if dns],
            search_list=subnet.search_list or ''
        )
        return model_subnet

    def _get_sysprof_entries(self, system_name, profile_name):
        """
        Retrieve system and profile database entries
        """
        system = System.query.filter(
            System.name == system_name
        ).one_or_none()
        if system is None:
            raise ValueError('System {} not found'.format(system_name))

        if profile_name is not None:
            profile = SystemProfile.query.join(
                'system_rel'
            ).filter(
                SystemProfile.name == profile_name
            ).filter(
                System.id == system.id
            ).one_or_none()
            if profile is None:
                raise ValueError('Profile {} for system {} not found'.format(
                    profile_name, system_name))
        else:
            profile = SystemProfile.query.join(
                'system_rel'
            ).filter(
                SystemProfile.default == bool(True)
            ).filter(
                System.id == system.id
            ).one_or_none()
            if profile is None:
                raise ValueError(
                    'Default profile for system {} not available'.format(
                        system_name)
                )
        return (system, profile)

    def get_system(self, system_name, profile_name):
        """
        Return data required for autoinstall machine
        """
        system, profile = self._get_sysprof_entries(
            system_name, profile_name)

        hypervisor = None
        hyp_profile = profile.hypervisor_profile_rel
        hyp_system = system.hypervisor_rel
        if not hyp_profile:
            # when hypervisor profile is not set in system profile,
            # take default profile from hypervisor system
            _, hyp_profile = self._get_sysprof_entries(hyp_system.name,
                                                       None)

        if hyp_system != hyp_profile.system_rel:
            raise ValueError('Hypervisors in system {} and system profile {}'
                             ' do not match: {} and {}'.format(
                                 system.name, profile.name,
                                 hyp_system, hyp_profile.system
                             ))
        if system.type == 'LPAR' and hyp_system.type == 'CPC':
            boot_method = self._get_cpc_boot_method(hyp_profile)
            boot_method['partition-name'] = system.name
            hypervisor = AutoinstallMachineModel.HmcHypervisor(
                hyp_system.name,
                hyp_system.hostname,
                {
                    'user': hyp_profile.credentials.get('admin-user'),
                    'password': hyp_profile.credentials.get('admin-password')
                },
                boot_method
            )
        elif system.type == 'ZVM' and hyp_system.type == 'LPAR':
            hypervisor = AutoinstallMachineModel.ZvmHypervisor(
                hyp_system.name,
                hyp_system.hostname,
                {
                    'user': system.name,
                    'password': profile.credentials.get('zvm-password')
                },
                {
                    'logon-by': profile.credentials.get('zvm-logonby')
                }
            )
        elif system.type == 'KVM':
            hypervisor = AutoinstallMachineModel.KvmHypervisor(
                hyp_system.name,
                hyp_system.hostname,
                {
                    'user': hyp_profile.credentials.get('admin-user'),
                    'password': hyp_profile.credentials.get('admin-password')
                }
            )

        if not hypervisor:
            raise ValueError('Cannot determine hypevisor for system {}'.format(
                             system.name))

        # Combine information about hypervisor and system profile into model
        result = AutoinstallMachineModel.SystemProfile(
            system.name, profile.name, hypervisor, system.hostname,
            profile.cpu, profile.memory)

        # add network interfaces
        for profile_iface in profile.system_ifaces_rel:
            if profile_iface.type == 'OSA':
                model_iface = AutoinstallMachineModel.OsaInterface(
                    profile_iface.attributes.get('ccwgroup'),
                    profile_iface.attributes.get('layer2', False),
                    portno=profile_iface.attributes.get('portno'),
                    portname=profile_iface.attributes.get('portname'),
                    os_device_name=profile_iface.osname,
                    mac_address=profile_iface.mac_address
                )
            elif profile_iface.type == 'HSI':
                model_iface = AutoinstallMachineModel.HipersocketsInterface(
                    profile_iface.attributes.get('ccwgroup'),
                    profile_iface.attributes.get('layer2', False),
                    os_device_name=profile_iface.osname,
                    mac_address=profile_iface.mac_address
                )
            elif (profile_iface.type == 'MACVTAP' and
                  profile_iface.attributes.get('hostiface')):
                model_iface = AutoinstallMachineModel.MacvtapHostInterface(
                    profile_iface.attributes.get('hostiface'),
                    os_device_name=profile_iface.osname,
                    mac_address=profile_iface.mac_address
                )
            elif (profile_iface.type == 'MACVTAP' and
                  profile_iface.attributes.get('libvirt')):
                model_iface = AutoinstallMachineModel.MacvtapLibvirtInterface(
                    profile_iface.attributes.get('libvirt'),
                    os_device_name=profile_iface.osname,
                    mac_address=profile_iface.mac_address
                )
            elif profile_iface.type == 'ROCE':
                model_iface = AutoinstallMachineModel.RoceInterface(
                    profile_iface.attributes.get('fid'),
                    os_device_name=profile_iface.osname,
                    mac_address=profile_iface.mac_address
                )
            else:
                raise ValueError(
                    "Unsupported interface type {} attached to system {} "
                    "profile {}".format(profile_iface.type, system.name,
                                        profile.name))

            iface_subnet = self._get_iface_subnet(profile_iface)
            if iface_subnet:
                model_iface.add_to_subnet(iface_subnet)
            # One of the interfaces shuold be set as "gateway" so that
            # tessia could connect to it.
            # TODO: improve default gateway selection, because it is
            # currently non-deterministic ("first" passing from database).
            result.add_network_interface(
                model_iface,
                (not result.gateway_interface and model_iface.gateway_subnets)
                or (profile.gateway_rel == profile_iface))

        # add volumes
        for profile_volume in profile.storage_volumes_rel:
            attrs = profile_volume.system_attributes
            specs = profile_volume.specs
            if attrs:
                dev_path = attrs.get('device')
            else:
                dev_path = None

            if profile_volume.type == 'DASD':
                model_vol = AutoinstallMachineModel.DasdVolume(
                    profile_volume.volume_id,
                    profile_volume.size,
                    device_path=dev_path
                )
            elif profile_volume.type == 'FCP':
                model_vol = AutoinstallMachineModel.ScsiVolume(
                    profile_volume.volume_id,
                    profile_volume.size,
                    specs.get('multipath'),
                    specs.get('wwid'),
                    device_path=dev_path
                )
                for adapter in specs.get('adapters', []):
                    model_vol.create_paths([adapter.get('devno')],
                                           adapter.get('wwpns'))
            elif profile_volume.type == 'HPAV':
                model_vol = AutoinstallMachineModel.HpavVolume(
                    profile_volume.volume_id,
                    device_path=dev_path
                )
            else:
                raise ValueError(
                    "Unsupported volume type {} attached to system {} "
                    "profile {}".format(profile_volume.type, system.name,
                                        profile.name))

            # add partitions
            part_table = profile_volume.part_table
            if part_table:
                model_vol.set_partitions(part_table['type'], [
                    {
                        'mount_point': partition['mp'],
                        'size': partition['size'],
                        'filesystem': partition['fs'],
                        'part_type': partition['type'],
                        'mount_opts': partition['mo'],
                    } for partition in part_table['table']
                ])
            # TODO: add libvirt definiton

            result.add_volume(model_vol)

        return result
    # get_system()

    def get_os(self, os_name):
        """
        Return the OS version to be used for the installation

        Args:
            os_name (str): os identifier

        Returns:
            Tuple[OperatingSystem, Repository]:
                os and its default repository (if present)

        Raises:
            ValueError: in case specified os does not exist
        """
        os_entry = OperatingSystem.query.filter_by(
            name=os_name).one_or_none()
        if os_entry is None:
            raise ValueError('OS {} not found'.format(os_name))
        operating_system = AutoinstallMachineModel.OperatingSystem(
            name=os_entry.name,
            _type=os_entry.type,
            major=os_entry.major,
            minor=os_entry.minor,
            pretty_name=os_entry.pretty_name,
            template_name=os_entry.template
        )
        available_repos = [AutoinstallMachineModel.OsRepository(
            name=repo.name,
            url=repo.url,
            kernel=repo.kernel,
            initrd=repo.initrd,
            install_image=repo.install_image,
            installable_os=os_entry.name,
            description=repo.desc
        ) for repo in os_entry.repository_rel]
        return (operating_system, available_repos)
    # get_os()

    def get_custom_repos(self, custom_repos):
        """
        Return repository representation for custom repos

        Args:
            custom_repos (List[str]): custom repo definition

        Returns:
            Tuple[List[OsRepository], List[PackageRepository]]:
                Repository representations

        Raises:
            ValueError: repository not found
        """
        os_repos = []
        package_repos = []

        # check the repositories specified by the user
        for repo_entry in custom_repos:
            if (repo_entry.split('://')[0] in ('http', 'https', 'ftp', 'file')
                    and '://' in repo_entry):
                # repo URL provided
                try:
                    urlsplit(repo_entry).hostname
                except Exception:
                    raise ValueError(
                        'Repository <{}> specified by user is not a valid URL'
                        .format(repo_entry))
                # sanitize to avoid invalid syntax problems with distro package
                # managers
                repo_name = re.sub('[^a-zA-Z0-9]', '_', repo_entry)
                package_repos.append(
                    AutoinstallMachineModel.PackageRepository(
                        name=repo_name,
                        url=repo_entry,
                        description='User defined repo {}'.format(repo_name),
                    ))
                # move on to next item in list
                continue

            # see if name refers to a registered repository
            repo_obj = Repository.query.filter_by(name=repo_entry).first()
            if not repo_obj:
                raise ValueError(
                    "Repository <{}> specified by user does not exist"
                    .format(repo_entry))
            # user specified an install repository: use it
            if repo_obj.operating_system:
                os_repos.append(
                    AutoinstallMachineModel.OsRepository(
                        name=repo_obj.name,
                        url=repo_obj.url,
                        kernel=repo_obj.kernel,
                        initrd=repo_obj.initrd,
                        install_image=repo_obj.install_image,
                        installable_os=repo_obj.operating_system,
                        description=repo_obj.desc
                    ))
            # package repository: don't use for installation, just add to the
            # list
            else:
                package_repos.append(
                    AutoinstallMachineModel.PackageRepository(
                        name=repo_obj.name,
                        url=repo_obj.url,
                        description='User defined repo {}'.format(
                            repo_obj.name),
                    ))

        return (os_repos, package_repos)
    # make_custom_repos()

    def get_template(self, template_name):
        """
        Return template string

        Args:
            template_name (str): template name

        Returns:
            Template: template representation

        Raises:
            ValueError: template  not found
        """
        # template not specified: use OS' default
        template_entry = Template.query.filter_by(
            name=template_name).one_or_none()
        if template_entry is None:
            raise ValueError('Template {} not found'.format(
                template_name))

        return AutoinstallMachineModel.Template(
            name=template_entry.name,
            content=template_entry.content
        )
    # get_template()

    def get_install_opts(self, system_name, profile_name):
        """
        Return installation options (credentials, cmdline additions etc)

        Args:
            system_name (str): system name
            profile_name (str): profile name

        Returns:
            dict: install options

        Raises:
            ValueError: system/profile not found
        """
        _, profile = self._get_sysprof_entries(
            system_name, profile_name)

        result = {
            'user': profile.credentials.get('admin-user'),
            'password': profile.credentials.get('admin-password'),
        }

        for field in ('linux-kargs-target', 'linux-kargs-installer'):
            if profile.parameters and field in profile.parameters:
                result[field] = profile.parameters.get(field)

        return result
    # get_template()

    def clear_target_os_field(self,
                              installation_model: AutoinstallMachineModel):
        """
        Update OS field on target system profile

        Args:
            installation_model: model used for installation
        """
        system_entry, profile_entry = self._get_sysprof_entries(
            installation_model.system_profile.system_name,
            installation_model.system_profile.profile_name)
        profile_entry.operating_system_id = None
        system_entry.modified = datetime.utcnow()
        self._manager.session.add(system_entry)
        self._manager.session.add(profile_entry)
        self._manager.session.commit()
    # set_target_os_field()

    def set_target_os_field(self, installation_model: AutoinstallMachineModel):
        """
        Update OS field on target system profile

        Args:
            installation_model: model used for installation
        """
        system_entry, profile_entry = self._get_sysprof_entries(
            installation_model.system_profile.system_name,
            installation_model.system_profile.profile_name)
        profile_entry.operating_system = \
            installation_model.operating_system.name
        system_entry.modified = datetime.utcnow()
        self._manager.session.add(system_entry)
        self._manager.session.add(profile_entry)
        self._manager.session.commit()
    # set_target_os_field()

    def update_libvirt_on_volume(
            self, installation_model: AutoinstallMachineModel,
            updated_volumes: "list[AutoinstallMachineModel.Volume]"):
        """
        Update libvirt definition for a volume
        """
        _, profile_obj = self._get_sysprof_entries(
            installation_model.system_profile.system_name,
            installation_model.system_profile.profile_name)

        result = 0
        vols = list(profile_obj.storage_volumes_rel)
        # iterate over volumes. We don't store database object IDs in model.
        # so this search may become slow on a few thousand volumes
        for volume_obj in vols:
            # search same volume in profile
            for volume_model in updated_volumes:
                if volume_obj.type != volume_model.volume_type:
                    continue
                if ((isinstance(volume_model,
                                AutoinstallMachineModel.DasdVolume)
                        and volume_model.device_id == volume_obj.volume_id)
                    or (isinstance(volume_model,
                                   AutoinstallMachineModel.ScsiVolume)
                        and volume_model.lun == volume_obj.volume_id)):
                    # got it
                    result += 1
                    # update libvirt attribute
                    volume_attrs = volume_obj.system_attributes
                    if not volume_attrs:
                        volume_attrs = {}
                    volume_attrs['libvirt'] = volume_model.libvirt_definition
                    volume_obj.system_attributes = volume_attrs

                    # only modify one field in the database
                    flag_modified(volume_obj, 'system_attributes')
                    self._manager.session.add(volume_obj)

        self._manager.session.commit()
        return result
    # update_libvirt_on_volume()
