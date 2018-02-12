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
Auxiliary class used for managing the CI process
"""

#
# IMPORTS
#
from lib.image import DockerImage
from lib.image_server import DockerImageServer
from lib.util import Shell, build_image_map

import logging
import os
import signal
import tempfile
import time
import yaml

#
# CONSTANTS AND DEFINITIONS
#
COMPOSE_PROJECT_NAME = 'tessia'
MY_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath('{}/../../..'.format(MY_DIR))

#
# CODE
#
class Manager(object):
    """
    Coordinates the actions for each docker image
    """
    # supported stages - order is important because the list is used
    # when stage='all' is specified
    STAGES = ['build', 'unittest', 'clitest', 'push', 'cleanup']

    def __init__(self, stage, docker_tag, images=None, registry_url=None,
                 field_tests=None, img_passwd_file=None,
                 install_server_hostname=None, verbose=True, **stage_args):
        """
        Create the image objects and set necessary configuration parameters

        Args:
            stage (str): one of STAGES or 'all'
            docker_tag (str): which tag to use for building or finding images,
                              None means to use project's versioning scheme
            images (list): names of images to process, may only be specified
                           for stages build, push, unittest
            registry_url (str): a docker registry url to where images should
                                be pushed, if None then push stage is skipped
            field_tests (str): a path on the builder containing additional
                               tests for the client, as recognized by the
                               cli test runner
            img_passwd_file (str): path to file containing the root password
                                   of the auxiliar live-image
            install_server_hostname (str): used by clitest stage, custom
                hostname to use as install server for cases where the detected
                fqdn is not reachable by systems being installed during tests
            verbose (bool): whether to print output from commands
            stage_args (any): additional specific arguments to the stage

        Raises:
            RuntimeError: in case fqdn of builder cannot be determined
            ValueError: 1- if a wrong stage is specified, 2- if 'images' var is
                        specified but stage is not build or push, 3- if
                        liveimg password is missing when clitests is specified
        """
        self._logger = logging.getLogger(__name__)
        self._registry_url = registry_url
        self._field_tests = field_tests
        self._install_server_hostname = install_server_hostname
        if img_passwd_file:
            with open(img_passwd_file, 'r') as file_fd:
                self._img_passwd = file_fd.read().strip()
        else:
            self._img_passwd = None

        # string 'all' specified: run all stages
        if stage == 'all':
            self._stages = [
                getattr(self, '_stage_{}'.format(stg)) for stg in self.STAGES]
        elif stage == 'run':
            self._stages = [self._run]
        # invalid stage specified
        elif stage not in self.STAGES:
            raise ValueError("invalid stage '{}'".format(stage))
        # incompatible combination as other stages might fail if one of the
        # images is missing
        elif stage not in ('build', 'push', 'unittest') and images:
            raise ValueError(
                "images may not be specified for stage '{}'".format(stage))
        # one-stage run specified
        else:
            self._stages = [getattr(self, '_stage_{}'.format(stage))]
        # additional parameters specific to the stage
        self._stage_args = stage_args

        # used to execute commands on a local shell
        self._session = Shell(verbose)

        # field tests demand the live-image's password otherwise tests with
        # LPAR installations will fail as it won't be possible to use the
        # auxiliar disk to boot them
        if self._field_tests:
            if not self._img_passwd:
                raise ValueError('Field tests specified but no password '
                                 'provided for auxiliar live-image')

        # determine builder's fqdn
        ret_code, output = self._session.run('hostname --fqdn')
        if ret_code != 0:
            raise RuntimeError(
                "failed to determine system's FQDN: {}".format(output))
        self._fqdn = output.strip()

        # docker tag specified: use it
        if docker_tag:
            self._tag = docker_tag
        # determine the docker tag to be used
        else:
            self._tag = self._create_tag()
        self._logger.info('[init] tag for images is %s', self._tag)

        # create the image objects
        self._images = []
        # no image specified: use all
        if not images:
            images = build_image_map().keys()
        for name in images:
            # each image object gets it's own session so that parallel builds
            # can happen if threading is used
            session = Shell(verbose)
            self._images.append(self._new_image(name, self._tag, session))

        # set signal handlers to assure cleanup before quitting
        for catch_signal in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(catch_signal, self._stop_handler)
    # __init__()

    def _clitest_exec(self):
        """
        Execute the client based tests
        """
        # clear any coverage data and get the list of tests to execute
        ret_code, output = self._session.run(
            "docker exec --user admin tessia_cli_1 "
            "bash -c '/home/admin/cli/tests/runner erase && "
            "/home/admin/cli/tests/runner list --terse'")
        if ret_code != 0:
            raise RuntimeError(
                'failed to retrieve the list of tests')
        test_list = [(name, None) for name in output.split()]
        # call auxiliar method to run each test
        self._clitest_loop(test_list)

        # field tests section (uses real resources)
        if self._field_tests:
            ret_code, _ = self._session.run(
                "test -d {}".format(self._field_tests))
            if ret_code != 0:
                raise RuntimeError(
                    'specified field tests path not found or not a '
                    'directory: {}'.format(output))

            # copy the tests from builder to cli container
            target_test_dir = '/home/admin/field_tests'
            ret_code, output = self._session.run(
                "docker cp {} tessia_cli_1:{}"
                .format(self._field_tests, target_test_dir))
            if ret_code != 0:
                raise RuntimeError(
                    'failed to copy field tests to container: {}'.format(
                        output))

            # get the list of tests and execute them
            ret_code, output = self._session.run(
                "docker exec --user admin tessia_cli_1 "
                "bash -c '/home/admin/cli/tests/runner list --src={} --terse'"
                .format(target_test_dir))
            if ret_code != 0:
                raise RuntimeError(
                    'failed to retrieve the list of field tests: {}'.format(
                        output))
            test_list = [(name, target_test_dir) for name in output.split()]
            # call auxiliar method to run each test
            self._clitest_loop(test_list)

        # report coverage level
        self._session.run(
            'docker exec --user admin tessia_cli_1 '
            '/home/admin/cli/tests/runner report', stdout=True)
    # _clitest_exec()

    def _clitest_loop(self, test_list):
        """
        Auxiliar function to execute each client test and perform db
        cleanup by the end of it.

        Args:
            test_list (list): [(test_name, source_dir)]

        Raises:
            RuntimeError: in case any operation fails
        """
        # execute each test by calling the cli test runner
        for test, src_dir in test_list:
            test_param = '--name={}'.format(test)
            if src_dir:
                test_param += ' --src={}'.format(src_dir)

            self._logger.info('[clitest] starting test %s', test)
            # do not erase existing coverage data (so that results are
            # cumulative) and do not display report (it will be displayed after
            # all tests have finished)
            ret_code, _ = self._session.run(
                'docker exec --user admin tessia_cli_1 '
                '/home/admin/cli/tests/runner exec --cov-erase=no '
                '--cov-report=no --api-url=https://{}:5000 {}'
                .format(self._fqdn, test_param)
            )
            # test failed: stop testing
            if ret_code != 0:
                raise RuntimeError(
                    'test {} failed'.format(test))

            # clear the database in preparation for next test
            self._logger.info('[clitest] cleaning db for next test')
            ret_code, output = self._session.run(
                'docker-compose stop && '
                'docker-compose rm -vf db && '
                'docker volume rm tessia_db-data && '
                # no-recreate is important to keep previous coverage results in
                # cli container
                'docker-compose up --no-recreate -d'
            )
            if ret_code != 0:
                raise RuntimeError(
                    'failed to clean db after test: {}'.format(output))
    # _clitest_loop()

    def _compose_start(self, dev_mode=False, cli_test=False):
        """
        Bring up and configure the services by using docker-compose.

        Args:
            dev_mode (bool): if True, local git repository will be bind mounted
                             inside the container.
            cli_test (bool): if True, local cli folder will be bind mounted
                              inside the container.

        Raises:
            RuntimeError: if python package path determination fails
        """
        with open('tools/ci/docker/docker-compose.yaml', 'r') as file_fd:
            compose_cfg = yaml.safe_load(file_fd.read())

        # dev/test mode: mount bind git repo files from host in the container
        if dev_mode or cli_test:
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
            if dev_mode:
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
            # clitests requested: bind mount the cli folder
            else:
                compose_cfg['services']['cli']['volumes'] = [
                    '{}/cli:/home/admin/cli:ro'.format(REPO_DIR)]

        if self._img_passwd:
            (compose_cfg['services']['server']['environment']
             ['TESSIA_LIVE_IMG_PASSWD']) = self._img_passwd

        # create compose file
        with open('.docker-compose.yaml', 'w') as file_fd:
            file_fd.write(yaml.dump(compose_cfg, default_flow_style=False))
        # create compose's .env file
        with open('.env', 'w') as file_fd:
            file_fd.write(
                "COMPOSE_FILE=.docker-compose.yaml\n"
                "COMPOSE_PROJECT_NAME={}\n"
                "TESSIA_DOCKER_TAG={}\n"
                "TESSIA_SERVER_FQDN={}\n"
                .format(COMPOSE_PROJECT_NAME, self._tag, self._fqdn)
            )
        ret_code, output = self._session.run('docker-compose up -d')
        if ret_code != 0:
            raise RuntimeError(
                'failed to start services: {}'.format(output))

        # user-provided hostname for http install server: use it in place of
        # fqdn (for cases where fqdn is not reachable)
        if self._install_server_hostname:
            ret_code, output = self._session.run(
                'docker exec tessia_server_1 yamlman update '
                '/etc/tessia/server.yaml auto_install.url http://{}/static'
                .format(self._install_server_hostname)
            )
            if ret_code != 0:
                raise RuntimeError(
                    'failed to set custom install server hostname: {}'.format(
                        output))

        # current we have to use 'docker exec' directly due to the way
        # 'docker-compose exec' works, where it always tries to hijack the
        # shell's tty even when there isn't one allocated (which is the case
        # with gitlab-runner's ssh executor).
        # A possible alternative solution is to use gitlab's shell executor
        # instead and use orc itself to connect to the builder via ssh.

        # wait for api service to come up
        ret_code = 1
        timeout = time.time() + 60
        self._logger.info('waiting for api to come up (60 secs)')
        while ret_code != 0 and time.time() < timeout:
            ret_code, _ = self._session.run(
                "docker exec tessia_cli_1 bash -c '"
                "openssl s_client -connect {}:5000 "
                "< /dev/null &>/dev/null'".format(self._fqdn)
            )
            time.sleep(5)
        if ret_code != 0:
            raise RuntimeError('timed out while waiting for api')

        # download ssl certificate to client
        cmd = (
            'docker exec tessia_cli_1 bash -c \''
            'openssl s_client -showcerts -connect {}:5000 '
            '< /dev/null 2>/dev/null | '
            'sed -ne "/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p" '
            '> /etc/tessia-cli/ca.crt\''.format(self._fqdn)
        )
        ret_code, output = self._session.run(cmd)
        if ret_code != 0:
            raise RuntimeError(
                'failed to retrieve ssl cert: {}'.format(output))

        # dev/test mode: set the free authenticator in api
        if dev_mode or cli_test:
            ret_code, output = self._session.run(
                'docker exec tessia_server_1 yamlman update '
                '/etc/tessia/server.yaml auth.login_method free && '
                'docker exec tessia_server_1 supervisorctl restart tessia-api')
            if ret_code != 0:
                raise RuntimeError(
                    'failed to set authenticator config: {}'.format(output))

        # add auth token to admin user in client to make it ready for use
        # better hide token from logs
        ret_code, output = self._session.run(
            'docker exec tessia_server_1 tess-dbmanage get-token 2>/dev/null',
            stdout=False)
        if ret_code != 0:
            raise RuntimeError(
                "failed to fetch admin's authorization token: {}'"
                .format(output))
        cmd_env = os.environ.copy()
        cmd_env['db_token'] = output.strip()
        ret_code, output = self._session.run(
            'docker exec tessia_cli_1 bash -c "mkdir {0} &>/dev/null; '
            'echo $db_token > {0}/auth.key && chown -R admin. {0}"'
            .format('/home/admin/.tessia-cli'), env=cmd_env
        )
        if ret_code != 0:
            raise RuntimeError(
                "failed to create admin user's auth.key file: {}"
                .format(output))
    # _compose_start()

    def _compose_stop(self):
        """
        Stop services and remove docker associated entities (volumes, networks,
        etc.)
        """
        ret_code, output = self._session.run(
            'test -e .env && docker-compose stop && '
            'docker-compose rm -vf && '
            'rm -f .env .docker-compose.yaml && '
            'docker volume rm {proj_name}_db-data '
            '{proj_name}_server-etc {proj_name}_server-jobs && '
            'docker network rm {proj_name}_cli_net '
            '{proj_name}_db_net'.format(proj_name=COMPOSE_PROJECT_NAME)
        )
        if ret_code != 0:
            self._logger.warning(
                'failed to clean compose services: %s', output)
    # _compose_stop()

    def _create_tag(self):
        """
        Create a tag by using the project's versioning scheme

        Raises:
            RuntimeError: in case any git command fails

        Returns:
            str: created tag
        """
        # call version generator method
        cmd = (
            "cd {} && python3 -c 'from setup import gen_version; "
            "print(gen_version())'".format(REPO_DIR))
        _, stdout = self._session.run(
            cmd,
            error_msg="Failed to determine project's version for tag creation")

        # replace plus sign as it is not allowed by docker
        return stdout.replace('+', '-').strip()
    # _create_tag()

    def _run(self):
        """
        Start all the containers and keep them running until manually
        stopped.
        """
        for image_obj in self._images:
            if image_obj.is_avail():
                continue
            raise RuntimeError(
                'image {} not available. Maybe you need to build it first?'
                .format(image_obj.get_fullname()))

        self._logger.info('[run] starting services')
        try:
            self._compose_start(dev_mode=self._stage_args['devmode'],
                                cli_test=self._stage_args['clitests'])
        except Exception as exc:
            # clean up before dying
            self._logger.info('[run] cleaning compose services')
            try:
                self._compose_stop()
            except Exception as clean_exc:
                self._logger.warning('[run] failed to clean compose '
                                     'services: %s', str(clean_exc))
            raise exc

        # show the started containers to the user
        self._session.run('docker-compose ps', stdout=True)

        if self._stage_args['clitests']:
            self._logger.info('[run] clitests requested')
            try:
                self._clitest_exec()
            finally:
                self._logger.info('[clitest] cleaning compose services')
                # clean up before dying/finishing
                try:
                    self._compose_stop()
                except Exception as clean_exc:
                    self._logger.warning('[run] failed to clean compose '
                                         'services: %s', str(clean_exc))
    # _run()

    @staticmethod
    def _new_image(name, image_tag, session):
        """
        Simple factory function to create DockerImage objects.
        """
        if name == 'tessia-server':
            image_cls = DockerImageServer
        else:
            image_cls = DockerImage
        return image_cls(name, image_tag, session)
    # _new_image()

    def _stage_build(self):
        """
        Tell each image object to perform the build.
        """
        self._logger.info('new stage: build')

        with tempfile.TemporaryDirectory() as work_dir:
            # tell each image object to perform build
            for image_obj in self._images:
                image_obj.build(work_dir)
    # _stage_build()

    def _stage_cleanup(self):
        """
        Tell each image object to clean up (remove associated image and
        containers)
        """
        # delete dangling (unreachable) images, that helps keeping the disk
        # usage low as docker does not have a gc available.
        # By doing this before removing the actual images we assure that
        # the cache layers will be kept so they can be used for the next builds
        ret_code, output = self._session.run(
            'docker images -a -q -f "dangling=true"')
        if ret_code != 0:
            self._logger.warning(
                '[cleanup] failed to list dangling images: %s',
                output)
        else:
            dang_images = output.replace('\n', ' ').strip()
            # delete dangling images
            if dang_images:
                self._logger.info('[cleanup] deleting dangling images')
                ret_code, output = self._session.run(
                    'docker rmi {}'.format(dang_images)
                )
                if ret_code != 0:
                    self._logger.warning(
                        '[cleanup] failed to remove dangling images: %s',
                        output)

        # tell each image to remove its associated image and containers
        for image_obj in self._images:
            image_obj.cleanup()
    # _stage_cleanup

    def _stage_clitest(self):
        """
        Start the client based tests stage
        """
        self._logger.info('new stage: clitest')
        try:
            self._compose_start(cli_test=True)
            self._clitest_exec()
        finally:
            self._logger.info('[clitest] cleaning compose services')
            # clean up before dying/finishing
            try:
                self._compose_stop()
            except Exception as clean_exc:
                self._logger.warning(
                    '[clitest] failed to clean compose services: %s',
                    str(clean_exc))
    # _stage_clitest()

    def _stage_push(self):
        """
        Tell each image object to push its docker image to the registry.
        """
        self._logger.info('new stage: push')
        if not self._registry_url:
            self._logger.warning(
                '[push] registry url not specified; skipping')
            return

        for image in self._images:
            image.push(self._registry_url)
    # _stage_push()

    def _stage_unittest(self):
        """
        Tell each image object to execute unit tests.
        """
        self._logger.info('new stage: unittest')
        for image in self._images:
            image.unit_test()
    # _stage_unittest()

    def _stop_handler(self, signum, *args, **kwargs):
        """
        Signal handler to perform cleanup before dying
        """
        signame = signal.Signals(signum).name # pylint: disable=no-member
        self._logger.error(
            'Received signal %s, canceling process', signame)

        # raise exception and let it be caught for clean up
        raise RuntimeError('Received signal {}'.format(signame))
    # _stop_handler()

    def run(self):
        """
        Executes the CI process
        """
        for stage in self._stages:
            stage()

        self._logger.info('done')
    # run()
# Manager
