# Copyright 2017, 2018 IBM Corp.
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
from copy import deepcopy
from jsonschema import validate
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import System
from tessia.server.db.models import SystemProfile
from tessia.server.state_machines.base import BaseMachine
from tessia.server.state_machines.ansible.env_docker import EnvDocker
from tessia.server.state_machines.autoinstall.machine import AutoInstallMachine
from urllib.parse import urlsplit, urlunsplit

import logging
import os
import re
import requests
import shutil
import tempfile
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
# max number of commits for cloning
MAX_GIT_CLONE_DEPTH = '10'
# regex pattern to be used for name fields
NAME_PATTERN = r'^\w+[\w\s\.\-]+$'
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
        'vars': {
            # dictionary with key:value pairs
            'type': 'object'
        },
        'groups': {
            'type': 'object'
        },
        'systems': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'pattern': NAME_PATTERN
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
                    'vars': {
                        'type': 'object'
                    }
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
        'secrets': {
            # dictionary with key:value pairs, values can only be strings
            'type': 'object',
            'additionalProperties': {
                'type': ['string', 'number']
            }
        },
        "verbosity": {
            "type": "string",
            "enum": list(BaseMachine._LOG_LEVELS),
        },
        "galaxy_req": {
            "type": "string"
        },
        'preexec_script': {
            'oneOf': [
                {
                    'type': 'string'
                },
                {
                    'type': 'object',
                    'properties': {
                        'path': {
                            'type': 'string',
                        },
                        'args': {
                            'type': 'array',
                            'items': {
                                'type': 'string'
                            }
                        },
                        'env': {
                            'type': 'object',
                            'additionalProperties': {
                                'type': 'string'
                            }
                        }
                    },
                    'required': ['path']
                }
            ]
        },
        'shared': {
            'type': 'boolean'
        }
    },
    'required': [
        'playbook',
        'source',
        'systems'
    ],
    'additionalProperties': False
}

# A file where the temporary directory path is stored
TEMP_DIR_FILE = ".temp_dir"

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
        super().__init__(params)

        # make sure query attribute is available on the models by explicitly
        # connecting to db
        MANAGER.connect()

        # validate params and store them
        parsed_params = self.parse(params)
        self._params = parsed_params['params']
        self._params['repo_info'] = parsed_params['repo_info']

        # apply custom log level if specified
        self._log_config(self._params.get('verbosity'))
        self._logger = logging.getLogger(__name__)

        self._env = EnvDocker()
        # work directory (to be created in create config stage)
        # dir where repo is extracted (to be created in create config stage)
        self._temp_dir = None
    # __init__()

    @staticmethod
    def _get_url_type(parsed_url):
        """
        Return a string representing the type of the url provided.

        Args:
            parsed_url (urllib.parse.SplitResult): result of urlsplit

        Returns:
            str: web, git or unknown
        """
        http_protocols = ['http', 'https']

        if parsed_url.scheme == 'git' or (
                parsed_url.scheme in http_protocols and
                (parsed_url.path.endswith('.git') or
                 '.git@' in parsed_url.path)):
            return 'git'

        if parsed_url.scheme in http_protocols:
            return 'web'

        return 'unknown'
    # _get_url_type()

    @classmethod
    def _parse_source(cls, source_url):
        """
        Parse and validate the passed ansible repository url.

        Args:
            source_url (str): repository network url

        Raises:
            ValueError: if validation of parameters fails
            RuntimeError: if subprocess execution fails

        Returns:
            dict: a dictionary containing the parsed information
        """
        # parse url into components
        parsed_url = urlsplit(source_url)
        if not parsed_url.netloc:
            raise ValueError("Invalid URL '{}'".format(source_url))

        repo = {
            'url': source_url,
            'git_branch': 'master',
            'git_commit': 'HEAD',
            'type': cls._get_url_type(parsed_url),
            'url_obs': cls._url_obfuscate(parsed_url),
            'url_parsed': parsed_url,
        }

        # git source: use git command to verify it
        if repo['type'] == 'git':
            git_url = repo['url']
            # parse git revision info (branch, commit/tag)
            try:
                _, git_rev = parsed_url.path.rsplit('@', 1)
                git_url = parsed_url.geturl().replace('@' + git_rev, '')
                repo['git_branch'] = git_rev
                repo['git_branch'], repo['git_commit'] = git_rev.rsplit(':', 1)
            except ValueError:
                # user did not specify additional git revision info,
                # use default values
                pass
            else:
                # user specified empty branch: set default value
                if not repo['git_branch']:
                    repo['git_branch'] = 'master'

            process_env = os.environ.copy()
            process_env['GIT_SSL_NO_VERIFY'] = 'true'
            try:
                subprocess.run(
                    ['git', 'ls-remote', git_url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    env=process_env,
                    check=True,
                    universal_newlines=True
                )
            except subprocess.CalledProcessError as exc:
                # re-raise and suppress context, which has unscreened repo url
                raise ValueError('Source url is not accessible: {} {}'.format(
                    str(exc).replace(git_url, repo['url_obs']),
                    exc.stderr.replace(
                        git_url, repo['url_obs']))) from None
            except OSError as exc:
                # re-raise and suppress context, which has unscreened repo url
                raise RuntimeError('Failed to execute git: {}'.format(
                    str(exc).replace(git_url, repo['url_obs']))) from None

        # http source: use the requests lib to verify it
        elif repo['type'] == 'web':
            file_name = os.path.basename(parsed_url.path)
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
            except requests.exceptions.HTTPError as exc:
                raise ValueError(
                    "Source url is not accessible: {} {}".format(
                        exc.response.status_code, exc.response.reason))
            except requests.exceptions.RequestException as exc:
                raise ValueError(
                    "Source url is not accessible: {}".format(str(exc)))

        else:
            raise ValueError('Unsupported source url specified')

        return repo
    # _parse_source()

    @staticmethod
    def _url_obfuscate(parsed_url):
        """
        Obfuscate sensitive information (i.e. user and password) from the
        repository URL.

        Args:
            parsed_url (urllib.parse.SplitResult): result of urlsplit

        Returns:
            str: url with obfuscated user credentials
        """
        try:
            _, host_name = parsed_url.netloc.rsplit('@', 1)
        except ValueError:
            return parsed_url.geturl()
        repo_parts = [*parsed_url]
        repo_parts[1] = '{}@{}'.format('****', host_name)

        return urlunsplit(repo_parts)
    # _url_obfuscate()

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
                autoinstall_params = deepcopy(system['autoinstall'])
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
                while system_obj is not None:
                    shared_res.add(system_obj.name)
                    system_obj = system_obj.hypervisor_rel

        # remove potential duplication of resources marked as shared and
        # exclusive at the same time
        shared_res -= exclusive_res

        resources = {
            'shared': list(shared_res),
            'exclusive': list(exclusive_res)
        }
        return resources
    # _get_resources()

    def _stage_build_environment(self):
        """
        Build the run environment to execute the playbook in.
        """
        self._env.build()
    # _stage_build_environment()

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

    def _stage_create_config(self):
        """
        Fetch info from db and create inventory file for ansible.

        Creates an ansible.cfg file which is used during ansible-playbook
        execution. Creates an inventory file (tessia-hosts) which is referenced
        in the ansible.cfg file. Creates the folder structure and files to
        overwrite default variables.
        """
        self._logger.info('creating inventory file')

        # There's a slight chance that an empty temp dir is not cleaned up if
        # a signal interrupts the execution between dir creation and storing
        # its name in the file, but it is still better to use the standard lib
        # to securely create the dir than generating a random name, avoiding
        # race conditions, permissions, etc. if creating it manually.
        with open(TEMP_DIR_FILE, 'w') as temp_dir_file:
            self._temp_dir = tempfile.mkdtemp()
            temp_dir_file.write(self._temp_dir)

        # create folders for the playbook and inventory specific variables
        playbook_dir = os.path.join(self._temp_dir, "playbook")
        os.makedirs(playbook_dir)

        group_vars_folder = os.path.join(self._temp_dir, "group_vars")
        group_vars_all_folder = os.path.join(group_vars_folder, "all")
        os.makedirs(group_vars_all_folder)

        host_vars_folder = os.path.join(self._temp_dir, "host_vars")
        os.makedirs(host_vars_folder)

        # create a mapping of all the groups specified by user and their
        # corresponding systems and create system specific variable files
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
                profile_obj = SystemProfile.query.join(
                    'system_rel'
                ).filter(
                    SystemProfile.name == profile_name
                ).filter(
                    System.name == system['name']
                ).one_or_none()
                if profile_obj is None:
                    raise ValueError(
                        'Profile {} of system {} not found'.format(
                            profile_name, system['name']))
            # no profile was specified: use default
            else:
                profile_obj = SystemProfile.query.join(
                    'system_rel'
                ).filter(
                    SystemProfile.default == bool(True)
                ).filter(
                    System.name == system['name']
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
                    'user': profile_obj.credentials['admin-user'],
                    'pass': profile_obj.credentials['admin-password'],
                }
                groups.setdefault(group, []).append(entry)

            # create system specific variable file
            if 'vars' in system:
                host_vars_file = os.path.join(host_vars_folder,
                                              system['name'] + ".yml")
                with open(host_vars_file, 'w') as file_fd:
                    yaml.dump(system['vars'], file_fd,
                              default_flow_style=False)
                if system['name'] != system_obj.hostname:
                    host_vars_file = os.path.join(host_vars_folder,
                                                  system_obj.hostname + ".yml")
                    with open(host_vars_file, 'w') as file_fd:
                        yaml.dump(system['vars'], file_fd,
                                default_flow_style=False)

        if 'groups' in self._params:
            for group_name, group_dict in self._params['groups'].items():
                # print a warning when no system is in the specified group
                # note: every system is in the group 'all' and every system
                #       with just the group 'all' is in the group 'ungrouped'
                if (group_name not in groups
                        and group_name not in ['all', 'ungrouped']):
                    raise ValueError('no system has group {} assigned'
                                     .format(group_name))

                # write to file
                if 'vars' in group_dict:
                    if group_name == 'all':
                        # all variables defined here overwrites all_1.yml
                        group_vars_file = os.path.join(group_vars_all_folder,
                                                       "all_2.yml")
                    else:
                        group_vars_file = os.path.join(group_vars_folder,
                                                       group_name + ".yml")
                    with open(group_vars_file, 'w') as file_fd:
                        yaml.dump(group_dict['vars'], file_fd,
                                  default_flow_style=False)

        # write the inventory file
        inventory_file = os.path.join(self._temp_dir, INVENTORY_FILE_NAME)
        with open(inventory_file, 'w') as file_fd:
            # create each group section
            for group_name, group_contents in groups.items():
                file_fd.write('[{}]\n'.format(group_name))
                # write the hosts belonging to this group
                for entry in group_contents:
                    file_fd.write(
                        '{hostname} ansible_host={hostname} '
                        'ansible_user={user} '
                        'ansible_ssh_pass={pass}\n'.format(**entry)
                    )
                file_fd.write('\n')

        self._logger.info('creating config file')

        # write the config file
        inventory_file = os.path.join("..", INVENTORY_FILE_NAME)
        config_content = ("[defaults]\n"
                          "inventory = {inv_file}\n"
                          "\n"
                          "host_key_checking = False\n"
                          "\n"
                          "[ssh_connection]\n"
                          "pipelining = True")\
            .format(inv_file=inventory_file)
        config_file = os.path.join(playbook_dir, "ansible.cfg")
        with open(config_file, 'w') as file_fd:
            file_fd.write(config_content)

        # write the group vars all file
        if 'vars' in self._params:
            group_vars_all_file = os.path.join(group_vars_all_folder,
                                               "all_1.yml")
            with open(group_vars_all_file, 'w') as file_fd:
                yaml.dump(self._params['vars'], file_fd,
                          default_flow_style=False)
    # _stage_create_config()

    def _stage_exec_playbook(self):
        """
        Run the ansible playbook/galaxy specified by the user.
        """
        self._logger.info("executing playbook/galaxy")

        ret_code = self._env.run(
            self._params['repo_info']['url'],
            self._temp_dir, self._params['playbook'],
            self._params.get('galaxy_req'),
            self._params.get('preexec_script'))
        if ret_code != 0:
            raise RuntimeError('playbook execution failed')
    # _stage_exec_playbook()

    @staticmethod
    def _url_decorate_auth(url, variables):
        """
        Replace authentication data from url with a variable.
        Variable value is stored in a provided dictionary.

        Args:
            url (str): url, which may contain authentication data
            variables (dict): dictionary to store variable (by ref)

        Returns:
            str: updated url
        """
        try:
            parsed_url = urlsplit(url)
        except ValueError:
            # any exception means nothing is there
            return url

        try:
            auth_data, hostname = parsed_url.netloc.rsplit('@', 1)
        except ValueError:
            # not enough values to unpack - no auth data present
            return url

        try:
            user, password = auth_data.split(':', 1)
        except ValueError:
            # not enough values to unpack - no password present
            return url

        variables['token'] = password

        # create a new url with replaced password
        repo_parts = [*parsed_url]
        repo_parts[1] = '{}:{}@{}'.format(user, '${token}', hostname)
        return urlunsplit(repo_parts)

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
            # validate that each group object is a dict and sanitize group_name
            # characters which might e.g. exploit the path ('..', '/', '.')
            for group_name, group_dict in obj_params.get('groups', {}).items():
                if not isinstance(group_dict, dict):
                    raise SyntaxError('group {} has invalid definition'
                                      .format(group_name))
                if not re.match(NAME_PATTERN, group_name):
                    raise SyntaxError('group_name {} is invalid'
                                      .format(group_name))
        except Exception as exc:
            raise SyntaxError(
                "Invalid request parameters: {}".format(str(exc)))

        # resources used in this job
        used_resources = cls._get_resources(obj_params['systems'])
        if obj_params.get('shared'):
            used_resources['shared'].extend(used_resources['exclusive'])
            used_resources['exclusive'] = []

        # validate the source specified
        repo_info = cls._parse_source(obj_params['source'])

        result = {
            'resources': used_resources,
            'description': MACHINE_DESCRIPTION.format(
                obj_params['playbook'], repo_info['url_obs']),
            # not for scheduler, useful for machine inner workings
            'params': obj_params,
            'repo_info': repo_info,
        }

        return result
    # parse()

    @classmethod
    def prefilter(cls, params):
        """
        Parse state machine parmfile and remove secrets to avoid storing them
        in the database.

        Args:
            params (str): state machine parameters

        Returns:
            Tuple[str, any]: state machine parameters and supplementary data

        Raises:
            SyntaxError: if content is in wrong format.
        """
        try:
            obj_params = yaml.safe_load(params)
            validate(obj_params, REQUEST_SCHEMA)
        except Exception as exc:
            raise SyntaxError(
                "Invalid request parameters: {}".format(str(exc)))

        # only process secrets that are a dictionary entry in params
        if not isinstance(obj_params, dict):
            return (params, None)

        secrets = obj_params.pop('secrets', {})

        # automatically replace authentication data in source url,
        # as long as there are no other secrets.
        # If a user provides their own secret data, they should have replaced
        # passwords in the urls as well
        if 'source' in obj_params and not secrets:
            obj_params['source'] = cls._url_decorate_auth(
                obj_params['source'], secrets)

        return (yaml.dump(obj_params, default_flow_style=False), secrets)
    # prefilter()

    @classmethod
    def recombine(cls, params, extra_vars=None):
        """
        Method used to inject data separated in preprocessing stage
        back into parameters.

        It parses the yaml text and performs replacements on keys and values
        in the yaml stream.

        Args:
            params (str): state machine parameters
            extra_vars (dict): secret variables

        Returns:
            str: final machine parameters

        Raises:
            SyntaxError: invalid parmfile
        """
        if not extra_vars or not isinstance(extra_vars, dict):
            return params

        # only process parmfile if we have data to set
        event_stream = []
        match_vars = {'${{{}}}'.format(var): value
                      for (var, value) in extra_vars.items()}
        # regex pattern that can match all vars
        pattern = re.compile(
            '|'.join([re.escape(k) for k in match_vars.keys()]),
            re.M)
        try:
            for event in yaml.parse(params):
                # process only scalar events, i.e. simple keys and values
                if isinstance(event, yaml.ScalarEvent):
                    # Processing rules:
                    # - if a match is only part of value, replace it inline
                    # - if a match is the value, replace it *and* set
                    #   implicity to (False, True), i.e. display some tag.
                    # Setting explicit tags on variable replacement will keep
                    # yaml parser from doing implicit type conversions

                    # Python 3.8 will have this one-lined, PEP-0572
                    full_match = pattern.fullmatch(event.value)
                    if full_match is not None:
                        # complete match, replace and set to non-implicit
                        event.value = str(match_vars[full_match[0]])
                        event.implicit = (False, True)
                    else:
                        # concurrent replace (might match nothing)
                        event.value = pattern.sub(
                            lambda re_match: match_vars[re_match[0]],
                            str(event.value))

                # add the event, processed or not, to the stream
                event_stream.append(event)

        except yaml.parser.ParserError as exc:
            raise SyntaxError("Invalid request parameters") from exc

        # reassemble yaml file
        return yaml.emit(event_stream)
    # recombine()

    def cleanup(self):
        """
        Remove temp dir
        """
        # When the job is canceled during a cleanup the routine
        # is not executed again by the scheduler.
        self.cleaning_up = True

        self._logger.info('performing cleanup')

        # cleanup the run environment
        self._env.cleanup()

        if self._temp_dir is not None:
            dir_path = self._temp_dir
        else:
            # When the job was canceled the self._temp_dir variable does not
            # contain the actual directory anymore.
            # Therefore the path was saved to a file (TEMP_DIR_FILE).
            # The path to TEMP_DIR was stored in a file.
            # When the folder exists gracefully remove folder.
            try:
                with open(TEMP_DIR_FILE, 'r') as temp_dir_file:
                    dir_path = temp_dir_file.read().strip()
            except OSError:
                self._logger.debug("no temporary directory to delete")
                return

        # make sure we are deleting a temp folder
        if (os.path.isdir(dir_path) and
                os.path.dirname(dir_path) == tempfile.gettempdir()):
            shutil.rmtree(dir_path)
    # cleanup()

    def start(self):
        """
        Start the machine execution.
        """
        self._logger.info('new stage: build-environment')
        self._stage_build_environment()

        self._logger.info('new stage: create-config')
        self._stage_create_config()

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
