# Copyright 2020 IBM Corp.
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
Machine for auto installation of debian based operating systems.
"""

#
# IMPORTS
#
from enum import Enum
from secrets import token_urlsafe
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel
from tessia.server.config import Config
from tessia.server.state_machines.autoinstall.sm_base import SmBase
from tessia.server.state_machines.autoinstall.sm_base import TEMPLATES_DIR
from time import monotonic, sleep
from urllib.parse import urlparse

import jinja2
import json
import logging
import os
import requests

#
# CONSTANTS AND DEFINITIONS
#
EventMarker = Enum('EventMarker', 'NONE SUCCESS FAIL')

#
# CODE
#


class LogEvent:
    """
    Event parsed from event stream
    """

    def __init__(self, event_string):
        """
        Constructor

        Arguments:
            event_string (str): string describing event
        """
        self._name = ''
        self._result = ''
        self._origin = ''
        self._type = ''
        self._description = ''

        # binary/raw events, only metadata is logged
        if event_string.startswith('binary:'):
            self._name = 'binary'
            self._str = event_string[7:]
            return

        try:
            event_object = json.loads(event_string)
        except json.JSONDecodeError:
            self._str = 'Undecodeable event: {}'.format(event_string)
            return

        self._name = event_object.get("name", "?name?")
        self._origin = event_object.get("origin", "?origin?")
        self._result = event_object.get("result", "START")

        if self._origin == 'watchdog':
            self._str = "File {} {}".format(
                self._name,
                "retrieved" if self._result == 'SUCCESS' else "not present")
        else:
            self._type = event_object.get("event_type", "")
            self._description = event_object.get("description", "")
            if self._description:
                self._description = ": " + self._description

            self._str = "{} {} {}".format(
                self._result, self._name, self._description)
    # __init__()

    def __str__(self):
        """
        Return string definition of an event
        """
        return self._str
    # __str__()
# LogEvent()


class LogWatcher:
    """
    Installation state detector
    """

    def __init__(self, end_time):
        """
        Constructor

        Arguments:
            end_time (number): when to stop watching
        """
        self._end_watch = end_time

        self._success = False
        self._failure = False
    # __init__()

    @staticmethod
    def _is_success_trigger(event):
        """
        Detect success from event. May be overridden
        """
        return (event._name in (
                "subiquity/Reboot",
                "subiquity/Reboot/reboot")
                and event._result == "SUCCESS"
                and event._type == "finish")
    # _is_success_trigger()

    @staticmethod
    def _is_failure_trigger(event):
        """
        Detect failure from event. May be overridden
        """
        return (event._name.startswith("subiquity/Error")
                and "/var/crash" in event._description
                and not "server_request_fail" in event._description)

    def process(self, event, current_time):
        """
        Find out if it is failure or success

        Arguments:
            event (LogEvent): a set of values from log
            current_time (number): current time

        Returns:
            EventMarker: what does the event signify

        """
        if self._is_success_trigger(event):
            self._success = True
            return EventMarker.SUCCESS

        if self._is_failure_trigger(event):
            self._failure = True
            # we want to exit the loop now, but we should
            # wait for additional watchdog messages to come
            self._end_watch = current_time + 10
            return EventMarker.FAIL

        return EventMarker.NONE

    @property
    def success(self):
        """
        Has detector found successful state
        """
        return self._success

    @property
    def failure(self):
        """
        Has detector found failure state
        """
        return self._failure

    def should_stop(self, current_time):
        """
        Should detector stop running
        """
        return self.success or (current_time > self._end_watch)


class LogWatcherUbuntu2010(LogWatcher):
    """
    Installation state detector for Ubuntu 20.10
    """

    def _is_success_trigger(self, event):
        """
        Detect success from event. May be overridden
        """
        return (event._name == "subiquity/Reboot/apply_autoinstall_config"
                and event._result == "SUCCESS"
                and event._type == "finish")
    # _is_success_trigger()


class LogWatcherUbuntu2204andHigher(LogWatcher):
    """
    Installation state detector for Ubuntu 22.04 and higher
    """

    def _is_success_trigger(self, event):
        """
        Detect success from event. May be overridden
        """
        return (event._name == "subiquity/Shutdown/copy_logs_to_target"
                and event._result == "SUCCESS"
                and event._type == "finish")
    # _is_success_trigger()

class SmSubiquityInstaller(SmBase):
    """
    State machine for SubiquityInstaller installer
    """
    # the type of linux distribution supported
    DISTRO_TYPE = 'subiquity'

    def __init__(self, model: AutoinstallMachineModel,
                 platform: PlatBase, *args, **kwargs):
        """
        Constructor
        """
        super().__init__(model, platform, *args, **kwargs)
        self._logger = logging.getLogger(__name__)

        # get communication settings from config
        autoinstall_config = Config.get_config().get("auto_install")
        if not autoinstall_config:
            raise RuntimeError('No auto_install configuration provided')
        webhook_config = Config.get_config().get("installer-webhook")
        if not webhook_config:
            raise RuntimeError('No installer-webhook configuration provided')
        # expect webhook control in the same container
        self._webhook_control = "http://localhost:{}".format(
            webhook_config['control_port'])
        # webhook log address should be accessible to target system
        hostname = urlparse(autoinstall_config["url"]).hostname
        self._webhook_logger = "http://{}:{}/log/".format(
            hostname, webhook_config['webhook_port'])

        self._session_secret = token_urlsafe()
        self._session_id = "{}-{}".format(
            self._profile.system_name, self._profile.profile_name)

        # use a common requests session during the whole install process
        self._session = requests.Session()
    # __init__()

    @staticmethod
    def _add_systemd_osname(iface):
        """
        Determine and add a key to the iface dict representing the kernel
        device name used by the installer for the given network interface

        Args:
            iface (dict): network interface information dict
        """
        ccwgroup = iface['attributes']["ccwgroup"].split(",")
        # The control read device number is used to create a predictable
        # device name for OSA network interfaces (for details see
        # https://www.freedesktop.org/wiki/Software/systemd/
        # PredictableNetworkInterfaceNames/)
        iface["systemd_osname"] = (
            "enc{}".format(ccwgroup[0].lstrip('.0'))
        )
    # _add_systemd_osname()

    def _create_webhook_session(self):
        """
        Register a new session on the webhook
        Webhook will verify token on incoming requests using our secret
        """
        self._logger.info("Creating webhook session %s", self._session_id)
        data = {
            "id": self._session_id,
            "log_path": os.getcwd(),
            # Timeout after last message received by webhook, after which
            # session is considered "hanging" and therefore removed.
            # There is an installation step, which downloads security updates,
            # during which the system reports nothing, so this timeout
            # is somewhat large. At the same time, installer keeps an eye on
            # crashes, so larger values should not present an issue
            # of a failed installation hanging for too long.
            "timeout": 1200,
            "secret": self._session_secret
        }
        http_result = self._session.post(self._webhook_control + "/session",
                                         json=data)
        if http_result.status_code != 201:
            raise RuntimeError('Installation could not be started:' +
                               ' failed to open webhook session')

    def _read_events(self):
        """
        Query events stream from webhook
        """
        max_wait_install = 3600
        timeout_installation = monotonic() + max_wait_install

        if self._model.operating_system.major == 2010:
            # Use different marker for Ubuntu 20.10
            watcher = LogWatcherUbuntu2010(timeout_installation)
        elif self._model.operating_system.major >= 2204:
            # Use different marker for Ubuntu 22.04
            watcher = LogWatcherUbuntu2204andHigher(timeout_installation)
        else:
            watcher = LogWatcher(timeout_installation)

        frequency_check = 2.5
        last_event = 0

        watchdog_events = []

        while not watcher.should_stop(monotonic()):
            session_logs = self._session.get(
                "{}/session/{}/logs".format(self._webhook_control,
                                            self._session_id),
                params={"start": last_event, "end": 0})
            if session_logs.status_code != 200:
                raise RuntimeError("Could not read installation logs")

            # We receive a number of log events that were captured by webhook.
            # These include text messages from subiquity, and file metadata
            # from installer watchdog
            events = session_logs.json()
            last_event += len(events)
            for event_string in events:
                log_event = LogEvent(event_string)
                if log_event._origin == 'watchdog':
                    watchdog_events.append(log_event)
                else:
                    self._logger.info("%s", str(log_event))

                marker = watcher.process(log_event, monotonic())
                if marker == EventMarker.FAIL:
                    self._logger.fatal("Detected installation failure")

            sleep(frequency_check)

        if not watcher.success:
            if watcher.failure:
                # dump what we know
                for event in watchdog_events:
                    self._logger.debug("%s", str(event))
                raise RuntimeError('Installation could not be completed')

            # no failure detected, but no success either
            raise TimeoutError('Installation Timeout: The installation'
                               ' process is taking too long')

    # _read_events()

    def _render_installer_cmdline(self):
        """
        Returns installer kernel command line from the template
        """
        # try to find a template specific to this OS version
        template_filename = 'subiquity.cmdline.jinja'
        with open(TEMPLATES_DIR + template_filename, "r") as template_file:
            template_content = template_file.read()

        self._logger.debug(
            "Using subiquity installer cmdline template for "
            "OS %s of type '%s'", self._os.name, self._os.type)

        template_obj = jinja2.Template(template_content)
        return template_obj.render(config=self._info).strip()

    @staticmethod
    def _convert_fs(fs_name):
        """
        Convert the filesystem name to a name valid for parted.

        Args:
            fs_name (str): filesystem name

        Returns:
            str: the filesystem name adapted for parted
        """
        # adapt fs name for parted
        if fs_name in ('ext2', 'ext3', 'ext4'):
            fs_name = 'ext2'
        elif fs_name == 'swap':
            fs_name = 'linux-swap'

        return fs_name
    # _convert_fs()

    def cleanup(self):
        """
        Called upon job cancellation or end. Deletes the autofile if it exists.

        Do not call this method directly but indirectly from machine.py to make
        sure that the cleaning_up variable is set.
        """
        http_result = self._session.delete("{}/session/{}".format(
            self._webhook_control, self._session_id))
        if http_result.status_code != 200:
            self._logger.debug("Webhook session %s not removed: %s",
                               self._session_id, http_result.text)
        else:
            self._logger.debug("Removed webhook session %s: %s",
                               self._session_id, http_result.text)
        self._session.close()

        super().cleanup()
    # cleanup()

    def fill_template_vars(self):
        """
        See SmBase for docstring.
        """
        # collect repos, volumes, ifaces
        super().fill_template_vars()

        # Gather the device numbers of the disks and the paths
        # (denov, wwpn, lun).
        for svol in self._info["svols"]:
            try:
                svol["part_table"]["type"]
            except (TypeError, KeyError):
                continue

            part_table = svol['part_table']

            if part_table["type"] == "msdos":
                part_table["table"].sort(
                    key=lambda x: 0 if x['type'] == 'primary' else 1
                )
                # This will accumulate the size until now
                size = 0
                for i in range(len(part_table["table"])):
                    part = part_table["table"][i]
                    if part['type'] == 'logical':
                        part_table["table"].insert(
                            i, {
                                'type': 'extended',
                                "size": (svol['size'] - size),
                                'fs': "",
                                'mo': None,
                                'mp': None
                            })
                        break
                    size += part['size']

            ref_size = 1
            part_index = 1

            for part in part_table["table"]:
                part['start'] = ref_size
                # In case the partition table is not msdos
                part.setdefault('type', '')
                # There is only primary/extended/logical partitions for msdos
                # msdos part table.
                if part_table['type'] != 'msdos':
                    part['type'] = ''
                part['end'] = ref_size + part['size']
                part['parted_fs'] = self._convert_fs(part['fs'])
                part['device'] = (svol['system_attributes']['device']
                                  + '-part{}'.format(part_index))
                # multipath partitions follow a different rule to name the
                # devices
                if (svol['type'] == 'FCP' and svol['specs']['multipath']
                        and self._info['system_type'] != 'KVM'):
                    part['device'] = (
                        "/dev/disk/by-id/dm-uuid-part{}-mpath-{}".format(
                            part_index, svol['specs']['wwid']))

                if part['type'] == 'extended':
                    ref_size += 1
                    part_index = 5
                else:
                    ref_size += part['size']
                    part_index += 1

            if svol['is_root']:
                self._info['root_disk'] = svol

        # Gather the device numbers of the OSA interfaces.
        for iface in self._info["ifaces"] + [self._info['gw_iface']]:
            if iface["type"] == "OSA":
                self._add_systemd_osname(iface)

        # It is easier to get the following information here than in the
        # template.
        for repo in self._info['repos']:
            # install repository url: no parsing needed
            if repo['os'] and repo['install_image']:
                iso_url = urlparse(repo['install_image'])
                # handle both complete URLs and relative ones
                if iso_url.scheme:
                    repo['iso_path'] = repo['install_image']
                else:
                    repo['iso_path'] = "{repo}/{iso}".format(
                        repo=repo['url'], iso=repo['install_image'])
                continue
            if repo['os']:
                # repository contains OS, but no install_image
                # required for Subiquity
                raise ValueError(
                    "Subiquity installer requires 'install_image' set "
                    "in repository {}".format(repo['name']))
            # otherwise ubuntu has everything in /dists/
            try:
                root_path, comps = repo['url'].split('/dists/', 1)
            except ValueError:
                raise ValueError(
                    "Repository URL <{}>  is in invalid format, no '/dists/' "
                    "component found".format(repo['url'])) from None
            repo['apt_url'] = '{} {}'.format(
                root_path, comps.replace('/', ' ')).rstrip()

        # Add webhook information
        # TODO: encode token with a secret instead of just passing secret
        self._info['webhook'] = {
            "endpoint": self._webhook_logger,
            "key": self._session_id,
            "token": self._session_secret
        }
    # fill_template_vars()

    def create_autofile(self):
        """
        Fill the template and create the autofile in the target location
        """
        self._logger.info("generating autofile")
        self._remove_autofile()
        template = jinja2.Template(self._template.content)
        self._logger.info(
            "autotemplate will be used: '%s'", self._template.name)

        autofile_content = template.render(config=self._info)

        # Subiquity requires a directory to be present, we pass that
        # as the autofile location. In the directory a file named
        # 'user-data' must be located.
        try:
            os.mkdir(self._autofile_path)
        except FileExistsError:
            # that's fine, it's a directory, even though it should
            # not exist after _remove_autofile
            pass

        # Write the autofile for usage during installation
        # by the distro installer.
        with open(self._autofile_path + "/user-data", "w") as autofile:
            autofile.write(autofile_content)
        with open(self._autofile_path + "/meta-data", "w") as autofile:
            autofile.write("")
        # Write the autofile in the directory that the state machine
        # is executed.
        autofile_in_jobdir = os.path.join(
            self._work_dir, os.path.basename(self._autofile_path))

        try:
            with open(autofile_in_jobdir, "w") as autofile:
                autofile.write(autofile_content)
        except IsADirectoryError:
            # if for some reason we store template files as is, in a directory,
            # use 'user-data' name in that directory
            with open(os.path.join(autofile_in_jobdir, 'user-data'),
                      "w") as autofile:
                autofile.write(autofile_content)
    # create_autofile()

    def target_reboot(self):
        """
        Skip reboot step, it is done automatically
        """
        self._logger.info("waiting for system to reboot")
        self._platform.set_boot_device(self._profile.get_boot_device())
    # target_reboot()

    def wait_install(self):
        """
        Waits for the installation.

        Creates a session on webhook and listens to logs.
        """
        self._create_webhook_session()
        self._read_events()

    # wait_install()
# SmDebianInstaller
