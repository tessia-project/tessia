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
Machine to enable the usage of ansible playbooks
"""

#
# IMPORTS
#
from jsonschema import validate
from tessia_engine.config import CONF
from tessia_engine.db.connection import MANAGER
from tessia_engine.db.models import System
from tessia_engine.db.models import SystemProfile
from tessia_engine.state_machines.base import BaseMachine
from tessia_engine.state_machines.autoinstall.machine import AutoInstallMachine
from urllib.parse import urlsplit

import logging
import os
import requests
import tempfile
import time
import subprocess
import yaml

#
# CONSTANTS AND DEFINITIONS
#

# name of inventory file created by tessia
INVENTORY_FILE_NAME = 'tessia-hosts'
# description for scheduler
MACHINE_DESCRIPTION = 'Execute playbook {} from {}'
# max allowed size for source repositories
MAX_REPO_MB_SIZE = 100
# Schema to validate the job request
REQUEST_SCHEMA = {
    'type': 'object',
    'properties': {
        'source': {
            'type': 'string'
        },
        'playbook': {
            'type': 'string',
            # prevent injection of parameters in ansible call
            'pattern': '[a-zA-Z0-9_]'
        },
        'systems': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string'
                    },
                    'groups': {
                        'type': 'array',
                        'items': {
                            'type': 'string'
                        },
                        # the system must belong at least to one group
                        'minItems': 1,
                    },
                    'profile': {
                        'type': 'string'
                    },
                    'autoinstall': {
                        'type': 'object',
                        'properties': {
                            'template': {
                                'type': 'string'
                            },
                            'os': {
                                'type': 'string'
                            },
                        },
                        'required': [
                            'template'
                        ],
                        'additionalProperties': False
                    },
                },
                'required': [
                    'groups',
                    'name',
                ],
                'additionalProperties': False
            },
            # at lest one system must be specified
            'minItems': 1,
        },
    },
    'required': [
        'playbook',
        'source',
        'systems'
    ],
    'additionalProperties': False
}

#
# CODE
#
class AnsibleMachine(BaseMachine):
    """
    This machine acts as a wrapper for the execution of ansible playbooks by
    performing preparation steps like fetching the ansible repo from a given
    url and creating an inventory file of the systems reserved for the job.
    """
    def __init__(self, params):
        """
        See base class docstring.

        Args:
            params (str): A string containing a json in the format defined by
                          the REQUEST_SCHEMA constant.
        """
        super(AnsibleMachine, self).__init__(params)

        # make sure query attribute is available on the models by explicitly
        # connecting to db
        MANAGER.connect()

        CONF.log_config()
        self._logger = logging.getLogger(__name__)

        # validate params and store them
        self.parse(params)
        self._params = yaml.safe_load(params)

        # work directory (to be created in download stage)
        self._temp_dir = None
        # dir where repo is extracted (to be created in download stage)
        self._repo_dir = None
    # __init__()

    @staticmethod
    def _get_url_type(source_url):
        """
        Return a string representing the type of the url provided.

        Args:
            source_url (str): repository network url

        Returns:
            str: web, git or unknown
        """
        http_protocols = ['http', 'https']

        parsed_url = urlsplit(source_url)

        if parsed_url.scheme == 'git' or (
                parsed_url.scheme in http_protocols and
                parsed_url.path.endswith('.git')):
            return 'git'

        elif parsed_url.scheme in http_protocols:
            return 'web'

        return 'unknown'
    # _get_url_type()

    @classmethod
    def _assert_source(cls, source_url):
        """
        Validate the passed ansible repository url.

        Args:
            source_url (str): repository network url

        Raises:
            ValueError: if validation of parameters fails
        """
        # TODO: sanitize source_url

        # git source: use git command to verify it
        url_type = cls._get_url_type(source_url)
        if url_type == 'git':
            process_env = os.environ.copy()
            process_env['GIT_SSL_NO_VERIFY'] = 'true'
            try:
                subprocess.run(
                    ['git', 'ls-remote', source_url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    env=process_env,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise ValueError('Source url is not accessible: {}'.format(
                    exc.stderr.decode('utf8')))
            except OSError as exc:
                raise ValueError('Failed to execute git: {}'.format(str(exc)))

        # http source: use the requests lib to verify it
        elif url_type == 'web':
            file_name = os.path.basename(urlsplit(source_url).path)
            # file to download is not in supported format: report error
            if not (file_name.endswith('tgz') or file_name.endswith('.tar.gz')
                    or file_name.endswith('.tar.bz2')):
                raise ValueError(
                    "Unsupported file format '{}'".format(file_name))

            # verify if url is accessible
            try:
                # set a reasonable timeout, let's not wait too long as the
                # scheduler is possibly waiting
                resp = requests.get(
                    source_url, stream=True, verify=False, timeout=5)
                resp.raise_for_status()
                resp.close()
            except requests.exceptions.RequestException as exc:
                raise ValueError(
                    "Source url is not accessible: {} {}".format(
                        exc.response.status_code, exc.response.reason))

        else:
            raise ValueError('Unsupported source url specified')

    # _assert_source()

    def _download_git(self):
        """
        Download a repository from a git url
        """
        self._logger.info(
            'cloning git repo from %s', self._params['source'])

        try:
            subprocess.run(
                ['git', 'clone', '--depth=1', self._params['source'],
                 self._repo_dir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env={'GIT_SSL_NO_VERIFY': 'true'},
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError('Source url is not accessible: {}'.format(
                exc.stderr.decode('utf8')))
        except OSError as exc:
            raise RuntimeError('Failed to execute git: {}'.format(
                str(exc)))
    # _download_git()

    def _download_web(self):
        """
        Download a repository from a web url
        """
        file_name = os.path.basename(urlsplit(self._params['source']).path)

        # determine how to extract the source file
        tar_flags = ''
        if file_name.endswith('tgz') or file_name.endswith('.tar.gz'):
            tar_flags = 'zxf'
        elif file_name.endswith('.tar.bz2'):
            tar_flags = 'jxf'
        # should never happen as it was validated by parse before
        if not tar_flags:
            raise RuntimeError('Unsupported source file format')

        self._logger.info(
            'downloading compressed file from %s', self._params['source'])

        try:
            resp = requests.get(
                self._params['source'], stream=True, verify=False)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ValueError(
                "Source url is not accessible: {} {}".format(
                    exc.response.status_code, exc.response.reason))

        # define a sane maximum size to avoid consuming all space from the
        # filesystem
        if (int(resp.headers['content-length']) >
                MAX_REPO_MB_SIZE * 1024 * 1024):
            raise RuntimeError('Source file exceeds max allowed size '
                               '({}MB)'.format(MAX_REPO_MB_SIZE))

        # download the file
        file_target_path = '{}/{}'.format(self._temp_dir.name, file_name)
        chunk_size = 10 * 1024
        with open(file_target_path, 'wb') as file_fd:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                file_fd.write(chunk)

        # extract file
        os.makedirs(self._repo_dir)
        try:
            subprocess.run(
                ['tar', tar_flags, file_target_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                cwd=self._repo_dir,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError('Failed to extract file: {}'.format(
                exc.stderr.decode('utf8')))
        except OSError as exc:
            raise RuntimeError('Failed to execute tar: {}'.format(
                str(exc)))

        # source file not needed anymore, free up disk space
        os.remove(file_target_path)
    # _download_web()

    @staticmethod
    def _get_resources(systems):
        """
        Return the map of resources used in this job.

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

            # auto-installation requested: use its machine for validation
            if system.get('autoinstall'):
                autoinstall_params = system.get('autoinstall').copy()
                autoinstall_params['system'] = system['name']
                if 'profile' in system:
                    autoinstall_params['profile'] = system['profile']

                try:
                    parsed_res = AutoInstallMachine.parse(autoinstall_params)
                except (SyntaxError, ValueError) as exc:
                    raise ValueError(
                        "Failed while validating install parameters for "
                        "system '{}': {}".format(system['name'], str(exc)))

                for item in parsed_res['resources']['shared']:
                    shared_res.add(item)
                for item in parsed_res['resources']['exclusive']:
                    exclusive_res.add(item)
            else:
                exclusive_res.add(system['name'])

                # the hypervisor hierarchy is a shared resource
                system_obj = system_obj.hypervisor_rel
                while system_obj != None:
                    shared_res.add(system_obj.name)
                    system_obj = system_obj.hypervisor_rel

        resources = {
            'shared': list(shared_res),
            'exclusive': list(exclusive_res)
        }
        return resources
    # _get_resources()

    def _stage_activate_systems(self):
        """
        Activate the systems used in the job. Any systems tagged for
        installation will be installed at this point.
        """
        # TODO: proper installation of systems
        self._logger.info('no systems tagged for installation')

        for system in self._params['systems']:
            # TODO: proper activation of systems
            self._logger.info('system %s activated', system['name'])
    # _stage_activate_systems()

    def _stage_create_inventory(self):
        """
        Fetch info from db and create inventory file for ansible
        """
        self._logger.info('creating inventory file')

        # create a mapping of all the groups specified by user and their
        # corresponding systems
        groups = {}
        for system in self._params['systems']:
            system_obj = System.query.filter_by(
                name=system['name']).one_or_none()
            # should not happen as it was validated by parse before
            if system_obj is None:
                raise RuntimeError("Db entry for system '{}' not "
                                   "found".format(system['name']))

            profile_name = system.get('profile')
            # profile was specified: use it
            if profile_name is not None:
                profile_obj = SystemProfile.query.filter_by(
                    name=profile_name, system=system['name']).one_or_none()
                if profile_obj is None:
                    raise RuntimeError(
                        'Profile {} of system {} not found'.format(
                            profile_name, system['name']))
            # no profile was specified: use default
            else:
                profile_obj = SystemProfile.query.join(
                    'system_rel'
                ).filter(
                    SystemProfile.default == bool(True)
                ).filter(
                    SystemProfile.system == system['name']
                ).one_or_none()
                if profile_obj is None:
                    raise RuntimeError(
                        'Default profile for system {} not available'.format(
                            system['name'])
                    )

            # add the system to all groups specified
            for group in system['groups']:
                entry = {
                    'name': system['name'],
                    'hostname': system_obj.hostname,
                    'user': profile_obj.credentials['user'],
                    'pass': profile_obj.credentials['passwd'],
                }
                groups.setdefault(group, []).append(entry)

        # write the inventory file
        inventory_file = '{}/{}'.format(self._repo_dir, INVENTORY_FILE_NAME)
        with open(inventory_file, 'w') as file_fd:
            # create each group section
            for group in groups:
                file_fd.write('[{}]\n'.format(group))
                # write the hosts beloging to this group
                for entry in groups[group]:
                    file_fd.write(
                        '{name} ansible_host={hostname} ansible_user={user} '
                        'ansible_ssh_pass={pass}\n'.format(**entry)
                    )
                file_fd.write('\n')
    # _stage_create_inventory()

    def _stage_download(self):
        """
        Download the ansible repository from the network
        """
        self._temp_dir = tempfile.TemporaryDirectory()
        self._repo_dir = '{}/src'.format(self._temp_dir.name)

        url_type = self._get_url_type(self._params['source'])

        if url_type == 'git':
            self._download_git()

        elif url_type == 'web':
            self._download_web()

        # should never happen as it was validated by parse before
        else:
            raise RuntimeError('Unsupported source url')

        # perform some sanity checks
        self._logger.info('validating repository content')
        playbook_path = '{}/{}'.format(
            self._repo_dir, self._params['playbook'])
        if not os.path.exists(playbook_path):
            raise ValueError("Specified playbook '{}' not found in "
                             "repository".format(self._params['playbook']))

    # _stage_download()

    def _stage_exec_playbook(self):
        """
        Run the ansible playbook specified by the user.
        """
        # TODO: use overlayfs and chroot to isolate environment for security
        # see
        # https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt

        ansible_cmd = 'ansible-playbook -i tessia-hosts {}'.format(
            self._params['playbook'])
        self._logger.info("executing: '%s'", ansible_cmd)

        process_env = os.environ.copy()
        process_env['ANSIBLE_SSH_PIPELINING'] = 'true'
        process_env['ANSIBLE_HOST_KEY_CHECKING'] = 'false'
        proc = subprocess.Popen(
            ansible_cmd.split(), cwd=self._repo_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=process_env, universal_newlines=True)
        # read from pipe in an non-blocking way to avoid hanging in ssh related
        # commands (i.e. git clone) due to stderr left open by ssh
        # controlpersist background process
        # (https://bugzilla.mindrot.org/show_bug.cgi?id=1988)
        os.set_blocking(proc.stdout.fileno(), False)
        while True:
            output_buffer = proc.stdout.readline()
            if not output_buffer:
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
                continue
            print(output_buffer, end='', flush=True)

        if proc.returncode != 0:
            raise RuntimeError('playbook execution failed')
    # _stage_exec_playbook()

    def cleanup(self):
        """
        Remove temp dir
        """
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None
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
        # make sure query attribute is available on the models by explicitly
        # connecting to db
        MANAGER.connect()
        try:
            obj_params = yaml.safe_load(params)
            validate(obj_params, REQUEST_SCHEMA)
        except Exception as exc:
            raise SyntaxError(
                "Invalid request parameters: {}".format(str(exc)))

        # resources used in this job
        used_resources = cls._get_resources(obj_params['systems'])

        # validate the source specified
        cls._assert_source(obj_params['source'])

        result = {
            'resources': used_resources,
            'description': MACHINE_DESCRIPTION.format(
                obj_params['playbook'], obj_params['source'])
        }
        return result
    # parse()

    def start(self):
        """
        Start the machine execution.
        """
        self._logger.info('new stage: download-source')
        self._stage_download()

        self._logger.info('new stage: create-inventory')
        self._stage_create_inventory()

        self._logger.info('new stage: activate-systems')
        self._stage_activate_systems()

        self._logger.info('new stage: execute-playbook')
        self._stage_exec_playbook()

        self._logger.info('new stage: cleanup')
        self.cleanup()

        self._logger.info('machine finished successfully')
        return 0
    # start()
# AnsibleMachine
