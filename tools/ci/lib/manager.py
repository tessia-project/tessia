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
from lib.image_cli import DockerImageCli
from lib.image_engine import DockerImageEngine
from lib.session import Session
from lib.util import Shell
from urllib.parse import urlsplit

import logging
import os
import re
import requests
import signal
import tempfile
import yaml

#
# CONSTANTS AND DEFINITIONS
#
# local based configuration used when no config url is provided
LOCAL_CFG = {
    'builders': [
        {
            'hostname': 'localhost',
            'user': None,
            'passwd': None,
        }
    ],
    'zones': [
        {
            'name': 'local',
            'controller': {
                'hostname': 'localhost',
                'user': None,
                'passwd': None,
            },
            'type': 'test'
        }
    ]
}
MY_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath('{}/../../..'.format(MY_DIR))

#
# CODE
#
class Manager(object):
    """
    Coordinates the actions for each docker image
    """
    def __init__(self, images, config_url, prod_tag, cleanup=True,
                 verbose=False):
        """
        Create the image objects and fetch necessary configuration data

        Args:
            images (list): names of images to process
            config_url (str): location where CI config is available
            prod_tag (str): if not None means to build in production mode for
                            the specified git tag
            cleanup (bool): if False do not remove work dir after
                             failing/finishing
            verbose (bool): whether to print output from commands

        Raises:
            RuntimeError: in case a work dir cannot be prepared on builder
        """
        self._logger = logging.getLogger(__name__)
        # used to execute commands on a local shell
        self._shell = Shell(verbose)

        # section to determine build type (production/testing)
        if prod_tag is None:
            self._build_type = 'test'
            self._logger.info('[init] going to perform a test build')
        else:
            self._build_type = 'production'
            self._logger.info('[init] going to perform a production build')

        # section to determine build mode
        # no url: local mode
        if config_url is None:
            self._logger.info(
                '[init] no config url set: local build mode')
            self._config = LOCAL_CFG
            # for local mode there is no distinction between zone types so set
            # the local zone to what the user chose to do
            for zone in self._config['zones']:
                zone['type'] = self._build_type
        else:
            self._logger.info(
                '[init] fetching build configuration from %s', config_url)
            # fetch config from url
            self._config = self._fetch_conf(config_url)

        # today we just use the first available builder in the list but
        # this could be improved to use some smart policy
        self._builder = self._config['builders'][0]
        self._logger.info(
            '[init] using builder %s', self._builder['hostname'])

        # open the connection to the builder
        self._session = Session(
            self._builder['hostname'], self._builder['user'],
            self._builder['passwd'], verbose)

        # open connections to the zone controllers
        self._controllers = self._open_controllers(
            self._config['zones'],
            self._build_type,
            verbose)

        # determine the name of the git repository - used when
        # copying it to the staging/work directory
        cmd = 'cd {} && git remote get-url origin'.format(REPO_DIR)
        _, stdout = self._shell.run(
            cmd, error_msg='Failed to determine git repo name')
        self._repo_name = stdout.strip().split('/')[-1][:-4]
        self._logger.info('[init] detected git repo name is %s',
                          self._repo_name)

        # create the image objects
        self._images = []
        image_tag = self._process_tag(prod_tag)
        self._logger.info('[init] detected tag for images is %s', image_tag)
        for name in images:
            # each image object gets it's own session to the builder, this
            # could be used later to speed up builds by doing parallel builds
            session = Session(
                self._builder['hostname'], self._builder['user'],
                self._builder['passwd'], verbose)
            self._images.append(self._new_image(name, image_tag, session))

        self._cleanup_flag = cleanup

        # work dir is created when build process starts
        self._work_dir = None

        # set signal handlers to assure cleanup before quitting
        for catch_signal in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(catch_signal, self._stop_handler)
    # __init__()

    def _create_work_dir(self):
        """
        Create a temp directory on the builder to use as a staging area for
        building activities.
        """
        # create work dir on builder
        ret_code, output = self._session.run('mktemp -p /tmp -d')
        if ret_code != 0:
            raise RuntimeError(
                'Failed to create work directory on builder: {}'.format(
                    output))
        self._work_dir = output.strip()
    # _create_work_dir()

    def _del_work_dir(self):
        """
        Remove the work directory from the builder
        """
        # work dir does not exist: nothing to do
        if self._work_dir is None:
            return
        self._logger.info('[image-build] cleaning up work directory')
        # be extra cautious before deleting
        if not self._work_dir.startswith('/tmp/'):
            self._logger.warning(
                '[image-build] unexpected work directory name, skipped '
                'dir removal')
            return
        self._session.run('rm -rf {}'.format(self._work_dir))
        # mark work dir as non existent (prevents repeating the operation if
        # the signal handler is called past this point)
        self._work_dir = None
    # _del_work_dir()

    @staticmethod
    def _fetch_conf(cfg_url):
        """
        Download the file specified by the url and return its contents.
        """
        parsed_url = urlsplit(cfg_url)
        if parsed_url.scheme == 'file':
            with open(parsed_url.path, 'r') as file_fd:
                file_content = file_fd.read()
        elif parsed_url.scheme in ['http', 'https']:
            response = requests.get(cfg_url)
            if response.status_code == 400:
                raise FileNotFoundError()
            file_content = response.text
        else:
            raise RuntimeError(
                'Unsupported url scheme {}'.format(parsed_url.scheme))

        # TODO: validate against a schema
        return yaml.load(file_content)
    # _fetch_conf()

    def _new_image(self, name, image_tag, session):
        """
        Simple factory function to create DockerImage objects.
        """
        if name == 'tessia-engine':
            image_cls = DockerImageEngine
        elif name == 'tessia-cli':
            image_cls = DockerImageCli
        else:
            image_cls = DockerImage
        return image_cls(name, image_tag, self._build_type == 'production',
                         session, self._repo_name)
    # _new_image()

    def _open_controllers(self, zones, build_type, verbose):
        """
        Receives a list of zones and open a session to each of its
        controllers.

        Args:
            zones (list): dict of zones to use
            build_type (str): production, testing
            verbose (bool): to be passed as argument to the Session object

        Returns:
            list: [{'hostname': 'controller_hostname', 'session': Session}]

        Raises:
            RuntimeError: in case no suitable controller is found in zones list
        """
        controllers = []
        for zone in zones:
            # zone type is not target of this build: skip
            if zone['type'] != build_type:
                continue
            controller = zone['controller']
            self._logger.info(
                '[init] deploying to zone %s using controller %s',
                zone['name'],
                controller['hostname'])
            session = Session(
                controller['hostname'], controller['user'],
                controller['passwd'], verbose)
            controllers.append(
                {'hostname': controller['hostname'], 'session': session})
        if len(controllers) == 0:
            raise RuntimeError(
                "No controller available for the chosen build "
                "type '{}'".format(build_type))

        return controllers
    # _open_controllers()

    def _process_tag(self, prod_tag=None):
        """
        Validate the passed tag or calculate one by checking the branch name
        and HEAD commit's checksum of the git repository.

        Args:
            prod_tag (str): tag to validate, if None means to calculate one

        Raises:
            RuntimeError: in case any git command fails
            ValueError: in case a tag is provided but not found in git repo

        Returns:
            str: validated/calculated tag
        """
        # tag specified: validate it
        if prod_tag is not None:
            # specify the tag in the command to check if it exists
            cmd = "cd {} && git show -s --oneline {}".format(
                REPO_DIR, prod_tag)
            # an exception is raised in case tag is not found
            self._shell.run(
                cmd,
                error_msg='Specified tag {} not found in git repo'.format(
                    prod_tag))
            return prod_tag

        # determine on which branch we are
        cmd = "cd {} && git status -b --porcelain".format(REPO_DIR)
        _, stdout = self._shell.run(
            cmd, error_msg='Failed to determine current git branch')
        cur_branch = None
        for line in stdout.splitlines():
            if line.startswith('## '):
                cur_branch = line.split('...')[0][3:]
                break
        # failed to find line containing branch name in output: abort
        if cur_branch is None:
            raise RuntimeError(
                'Current git branch not found in output: \n'
                'cmd: {}\noutput: {}\n'.format(cmd, stdout))
        # replace any characters not accepted by docker as a tag
        cur_branch = re.sub('[^A-Za-z0-9]', '_', cur_branch)

        # determine the sha of the HEAD commit
        cmd = "cd {} && git show -s --oneline".format(REPO_DIR)
        _, stdout = self._shell.run(
            cmd, error_msg='Failed to determine sha of HEAD commit')
        head_sha = stdout.strip().split()[0]

        return '{}-{}'.format(cur_branch, head_sha)
    # _process_tag()

    def _send_repo(self):
        """
        Prepare the work directory so that the build process can happen.
        Basically that means copying the git repository to it.
        """
        # create a bundle of the git repository and send it to the work
        # directory on the builder
        with tempfile.TemporaryDirectory(prefix='tessia-build-') as tmp_dir:
            bundle_path = '{}/{}.git'.format(tmp_dir, self._repo_name)
            cmd = "cd {} && git bundle create {} HEAD".format(
                REPO_DIR, bundle_path)
            self._logger.info('[image-build] creating bundle of git repo')
            self._shell.run(cmd, error_msg='Failed to create git bundle')
            # send the bundle to the work dir
            self._logger.info('[image-build] sending git bundle to builder')
            self._session.send(bundle_path, self._work_dir)
    # _send_repo()

    def _state_build_images(self):
        """
        Tell each image object to perform the build.
        """
        self._logger.info('new state: image-build')
        try:
            # create work dir on builder
            self._create_work_dir()

            # copy git repository to builder
            self._send_repo()

            for image in self._images:
                image.build(self._work_dir)
        except Exception as exc:
            # clean up before dying
            try:
                self._del_work_dir()
            except Exception as clean_exc:
                self._logger.warning(
                    '[image-build] failed to delete work dir: %s',
                    str(clean_exc))
            raise exc

        self._del_work_dir()
    # _state_build_images()

    def _state_cleanup(self):
        """
        Perform housekeeping and tell each image object to clean up (remove
        associated image and containers)
        """
        if not self._cleanup_flag:
            return
        self._logger.info('new state: clean-up')
        # delete dangling (unreachable) images, that helps keeping the disk
        # usage low as docker does not have a gc available.
        # By doing this before removing the actual images we assure that
        # the cache layers will be kept so they can be used for the next builds
        ret_code, output = self._session.run(
            'docker images -a -q -f "dangling=true"')
        if ret_code != 0:
            self._logger.warning(
                '[clean-up] failed to list dangling images: %s',
                output)
        else:
            dang_images = output.replace('\n', ' ').strip()
            # delete dangling images
            if len(dang_images) > 0:
                ret_code, output = self._session.run(
                    'docker rmi {}'.format(dang_images)
                )
                if ret_code != 0:
                    self._logger.warning(
                        '[clean-up] failed to remove dangling images: %s',
                        output)

        # tell each image to remove its associated image and containers
        for image in self._images:
            image.cleanup()
    # _state_cleanup()

    def _state_lint_check(self):
        """
        Tell each image object to execute lint verification.
        """
        self._logger.info('new state: lint-check')
        for image in self._images:
            image.lint()
    # _state_lint_check()

    def _state_inttest_run(self):
        """
        Tell each image object to execute integration tests.
        """
        self._logger.info('new state: inttest-run')
        for image in self._images:
            image.int_test()
    # _state_inttest_run()

    def _state_unittest_run(self):
        """
        Tell each image object to execute unit tests.
        """
        self._logger.info('new state: unittest-run')
        for image in self._images:
            image.unit_test()
    # _state_unittest_run()

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
        try:
            self._state_build_images()
            self._state_lint_check()
            self._state_unittest_run()
            self._state_inttest_run()
        except Exception as exc:
            self._logger.error('exception caught; canceling process')
            # clean up before dying
            try:
                self._state_cleanup()
            except Exception as clean_exc:
                self._logger.warning(
                    'cleanup failed: %s', str(clean_exc))
            raise exc

        self._state_cleanup()
        self._logger.info('done')
    # run()
# Manager
