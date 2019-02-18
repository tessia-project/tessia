# Copyright 2019 IBM Corp.
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
Auxiliary class used to manage docker compose
"""

#
# IMPORTS
#
from enum import Enum
from lib.selinux import is_selinux_enforced

import ipaddress
import logging
import os
import time
import yaml
import uuid

#
# CONSTANTS AND DEFINITIONS
#
class OpMode(Enum):
    """
    Class representing possible compose operation modes
    """
    DEV = 0
    CLITEST = 1
    FIELDTEST = 2
    NORMAL = 3
    UNITTEST = 4
# OpMode

MY_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath('{}/../../..'.format(MY_DIR))

#
# CODE
#

class ComposeInstance():
    """
    Controls the life cycle of a compose instance
    """
    def __init__(self, session, mode, images, tag, fqdn, img_pwd,
                 custom_cli_net, custom_db_net, install_server_hostname):
        """
        Constructor

        Args:
            session (Shell): shell object to execute commands
            mode (OpMode): operation mode, defines content of compose file
            images (list): list of Image objects
            tag (str): which tag to use for building or finding images,
            fqdn (str): host's fully qualified domain name
            img_pwd (str): live-image password used by field tests
            custom_cli_net (str): subnet in cidr notation to be used in
                                  docker compose definition of cli container
            custom_db_net (str): subnet in cidr notation to be used in
                                 docker compose definition of db container
            install_server_hostname (str): used by clitest stage, custom
                hostname to use as install server for cases where the detected
                fqdn is not reachable by systems being installed during tests

        Raises:
            ValueError: in case an invalid mode is provided
        """
        self._logger = logging.getLogger(__name__)

        self._images = images
        self._img_pwd = img_pwd
        self._fqdn = fqdn
        if mode not in OpMode:
            raise ValueError('mode {} is invalid'.format(mode))
        self._mode = mode
        self._tag = tag
        self._session = session
        self._custom_cli_net = custom_cli_net
        self._custom_db_net = custom_db_net
        self._install_server_hostname = install_server_hostname

        # used when compose is running in non-persistent mode (without .env
        # file)
        self._env_vars = None
        # set by prepare() when compose file gets created
        self._prepared = False
    # __init__()

    @staticmethod
    def _parse_ip_range(ip_range):
        """
        Check that the ip range provided is valid by creating an IPvXNetwork
        python object out of it.

        Args:
            ip_range (str): ip address range, valid notations:
                            CIDR: e.g. 192.168.178.0/24
                            dotted decimal notation: e.g.
                                192.168.178.0/255.255.255.0

        Returns:
            str: parsed ip_address range

        Raises:
            ValueError: When ip address range is invalid.
        """
        range_obj = ipaddress.ip_network(ip_range)
        return str(range_obj)
    # _parse_ip_range()

    def do_ps(self):
        """
        Print the started containers
        """
        self._session.run('docker-compose ps', stdout=True)
    # do_ps()

    def prepare(self, persistent=False):
        """
        Configure the services via docker-compose.

        Args:
            persistent (bool): whether to create a .env file

        Raises:
            RuntimeError: if python package path determination fails
        """
        with open('tools/ci/docker/docker-compose.yaml', 'r') as file_fd:
            compose_cfg = yaml.safe_load(file_fd.read())

        # IMPORTANT: define soon which mode is used so that in case of
        # error the stop method will know how to clean up correctly

        # non persistent: use env variables for commands
        if not persistent:
            unique_suffix = str(uuid.uuid4()).replace('-', '')
            comp_file = '.docker-compose-{}.yaml'.format(unique_suffix)
            self._env_vars = os.environ.copy()
            self._env_vars.update({
                "COMPOSE_FILE": comp_file,
                "COMPOSE_PROJECT_NAME": "tessia_{}".format(unique_suffix),
                "TESSIA_DOCKER_TAG": self._tag,
                "TESSIA_SERVER_FQDN": self._fqdn,
            })
        # persistent mode: create compose and .env files
        else:
            comp_file = '.docker-compose.yaml'
            self._env_vars = None

        # dev/test mode: mount bind git repo files from host in the container
        if self._mode in (OpMode.DEV, OpMode.CLITEST, OpMode.FIELDTEST,
                          OpMode.UNITTEST):
            # determine the path of the python packages
            pkg_paths = {}
            docker_cmd = (
                'docker run --rm -t --entrypoint python3 tessia-{}:{} '
                '-c "import tessia; print(tessia.__path__[0])"')
            for image in ['server', 'cli']:
                ret_code, output = self._session.run(
                    docker_cmd.format(image, self._tag))
                if ret_code != 0:
                    raise RuntimeError(
                        "failed to determine tessia's python package path in "
                        "image {}: {}".format(image, output))
                pkg_paths[image] = output.strip()

            # devmode: bind mount all folders
            if self._mode == OpMode.DEV:
                if is_selinux_enforced():
                    compose_cfg['services']['server']['security_opt'] = [
                        'label:disable']
                    compose_cfg['services']['cli']['security_opt'] = [
                        'label:disable']
                compose_cfg['services']['server']['volumes'] += [
                    '{}/tessia/server:{}/server:ro'.format(
                        REPO_DIR, pkg_paths['server']),
                    '{}:/root/tessia:ro'.format(REPO_DIR)
                ]
                compose_cfg['services']['cli']['volumes'] = [
                    '{}/cli/tessia/cli:{}/cli:ro'.format(
                        REPO_DIR, pkg_paths['cli']),
                    '{}/cli:/home/admin/cli:ro'.format(REPO_DIR)
                ]

            # unittest requested: bind mount the server folder
            elif self._mode == OpMode.UNITTEST:
                if is_selinux_enforced():
                    compose_cfg['services']['server']['security_opt'] = [
                        'label:disable']
                compose_cfg['services']['server']['volumes'] += [
                    '{}/tessia/server:{}/server:ro'.format(
                        REPO_DIR, pkg_paths['server']),
                    '{}:/root/tessia:ro'.format(REPO_DIR)
                ]

            # clitests requested: bind mount the cli folder
            elif self._mode in (OpMode.CLITEST, OpMode.FIELDTEST):
                if is_selinux_enforced():
                    compose_cfg['services']['cli']['security_opt'] = [
                        'label:disable']
                compose_cfg['services']['cli']['volumes'] = [
                    '{}/cli:/home/admin/cli:ro'.format(REPO_DIR)]

        # static or unit tests: do not expose ports
        if self._mode in (OpMode.CLITEST, OpMode.UNITTEST):
            compose_cfg['services']['server'].pop('ports')

        # set custom subnet for tessia_cli_net
        if self._custom_cli_net:
            parsed_ip_range = self._parse_ip_range(self._custom_cli_net)
            compose_cfg['networks']['cli_net'] = {}
            compose_cfg['networks']['cli_net']['ipam'] = {
                'driver': 'default', 'config': [{'subnet': parsed_ip_range}]
            }

        # set custom subnet for tessia_db_net
        if self._custom_db_net:
            parsed_ip_range = self._parse_ip_range(self._custom_db_net)
            compose_cfg['networks']['db_net'] = {}
            compose_cfg['networks']['db_net']['ipam'] = {
                'driver': 'default', 'config': [{'subnet': parsed_ip_range}]
            }

        if self._img_pwd:
            (compose_cfg['services']['server']['environment']
             ['TESSIA_LIVE_IMG_PASSWD']) = self._img_pwd

        # create compose file
        with open(comp_file, 'w') as file_fd:
            file_fd.write(yaml.dump(compose_cfg, default_flow_style=False))

        # non persistent: use env variables for commands, nothing more to do
        if not persistent:
            self._prepared = True
            return

        # persistent mode: create .env file
        with open('.env', 'w') as file_fd:
            file_fd.write(
                "COMPOSE_FILE={}\n"
                "COMPOSE_PROJECT_NAME=tessia\n"
                "TESSIA_DOCKER_TAG={}\n"
                "TESSIA_SERVER_FQDN={}\n"
                .format(comp_file, self._tag, self._fqdn)
            )
        self._prepared = True
    # prepare()

    def start(self):
        """
        Start the services by using docker-compose.
        """
        if not self._prepared:
            raise RuntimeError('You need to call prepare() before start()')

        ret_code, output = self._session.run(
            'docker-compose down -v && docker-compose up -d',
            env=self._env_vars)
        if ret_code != 0:
            raise RuntimeError(
                'failed to start services: {}'.format(output))

        # store the id of each started container
        for service in ['server', 'cli']:
            image_obj = self._images['tessia-{}'.format(service)]
            ret_code, output = self._session.run(
                'docker-compose ps -q {}'.format(service), env=self._env_vars)
            if ret_code != 0:
                raise RuntimeError(
                    'failed to get container name for service {}: {}'.format(
                        service, output))
            if len(output.strip().splitlines()) > 1:
                raise RuntimeError(
                    'Multiple containers found for service {}. Use '
                    'COMPOSE_PROJECT_NAME if you want to run parallel '
                    'instances.'.format(service))
            image_obj.container_name = output.strip()
        server_id = self._images['tessia-server'].container_name
        client_id = self._images['tessia-cli'].container_name

        # user-provided hostname for http install server: use it in place of
        # fqdn (for cases where fqdn is not reachable)
        if self._install_server_hostname:
            ret_code, output = self._session.run(
                'docker exec {} yamlman update '
                '/etc/tessia/server.yaml auto_install.url http://{}/static'
                .format(server_id, self._install_server_hostname)
            )
            if ret_code != 0:
                raise RuntimeError(
                    'failed to set custom install server hostname: {}'.format(
                        output))

        # use 'docker exec' so that we can address containers by their id
        # wait for api service to come up
        ret_code = 1
        timeout = time.time() + 60
        self._logger.info('waiting for api to come up (60 secs)')
        while ret_code != 0 and time.time() < timeout:
            ret_code, _ = self._session.run(
                "docker exec {} bash -c '"
                "openssl s_client -connect {}:5000 "
                "< /dev/null &>/dev/null'".format(client_id, self._fqdn)
            )
            time.sleep(5)
        if ret_code != 0:
            raise RuntimeError('timed out while waiting for api')

        # download ssl certificate to client
        cmd = (
            'docker exec {} bash -c \''
            'openssl s_client -showcerts -connect {}:5000 '
            '< /dev/null 2>/dev/null | '
            'sed -ne "/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p" '
            '> /etc/tessia-cli/ca.crt\''.format(client_id, self._fqdn)
        )
        ret_code, output = self._session.run(cmd)
        if ret_code != 0:
            raise RuntimeError(
                'failed to retrieve ssl cert: {}'.format(output))

        # dev/test mode: set the free authenticator in api
        if self._mode in (OpMode.DEV, OpMode.CLITEST, OpMode.FIELDTEST):
            ret_code, output = self._session.run(
                'docker exec {0} yamlman update '
                '/etc/tessia/server.yaml auth.login_method free && '
                'docker exec {0} supervisorctl restart tessia-api'
                .format(server_id))
            if ret_code != 0:
                raise RuntimeError(
                    'failed to set authenticator config: {}'.format(output))

        # add auth token to admin user in client to make it ready for use
        # better hide token from logs
        ret_code, output = self._session.run(
            'docker exec {} tess-dbmanage get-token 2>/dev/null'
            .format(server_id), stdout=False)
        if ret_code != 0:
            raise RuntimeError(
                "failed to fetch admin's authorization token: {}'"
                .format(output))
        cmd_env = os.environ.copy()
        cmd_env['db_token'] = output.strip()
        ret_code, output = self._session.run(
            'docker exec {0} bash -c "umask 077; mkdir {1} &>/dev/null; '
            'echo $db_token > {1}/auth.key && chown -R admin. {1}"'
            .format(client_id, '/home/admin/.tessia-cli'), env=cmd_env
        )
        if ret_code != 0:
            raise RuntimeError(
                "failed to create admin user's auth.key file: {}"
                .format(output))
    # start()

    def run(self, service, entrypoint=None, cmd=None):
        """
        Execute docker-compose run

        Returns:
            tuple: (exit_code, output)
        """
        # -T avoids broken terminal output
        run_cmd = 'docker-compose run -T --rm'
        if entrypoint:
            run_cmd += ' --entrypoint {}'.format(entrypoint)
        run_cmd += ' {}'.format(service)
        if cmd:
            run_cmd += ' {}'.format(cmd)
        return self._session.run(run_cmd, env=self._env_vars)
    # run()

    def stop(self):
        """
        Stop services and remove docker associated entities (volumes, networks,
        etc.)
        """
        # persistent mode: rely on existing .env file
        if not self._env_vars:
            if not os.path.exists('.env'):
                self._logger.warning(
                    'failed to clean compose services: no .env file found')
                return
            ret_code, output = self._session.run(
                'test -e .env && docker-compose down -v && '
                'rm -f .env .docker-compose.yaml')
        # non persistent mode: use env variables
        else:
            ret_code, output = self._session.run(
                'docker-compose down -v && rm -f "{}"'
                .format(self._env_vars['COMPOSE_FILE']),
                env=self._env_vars)
        if ret_code != 0:
            self._logger.warning(
                'failed to clean compose services: %s', output)
    # stop()
# ComposeInstance
