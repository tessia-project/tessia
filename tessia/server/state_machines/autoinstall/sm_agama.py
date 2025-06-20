# Copyright 2025 IBM Corp.
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
Machine for auto installation of Agama installer based operating systems
"""

#
# IMPORTS
#
from tessia.server.state_machines.autoinstall.plat_base import PlatBase
from tessia.server.state_machines.autoinstall.sm_base import SmBase
from tessia.server.state_machines.autoinstall.sm_base import TEMPLATES_DIR
from tessia.server.state_machines.autoinstall.model import \
    AutoinstallMachineModel

import json
import logging
import os
from time import sleep, time

import jinja2
import yaml

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class SmAgama(SmBase):
    """
    State machine for Agama installer
    """

    # the type of linux distribution supported
    DISTRO_TYPE = "agama"

    def __init__(
        self,
        model: AutoinstallMachineModel,
        platform: PlatBase,
        *args,
        **kwargs,
    ):
        """
        Constructor
        """
        self._json_data = {}
        super().__init__(model, platform, *args, **kwargs)
        self._logger = logging.getLogger(__name__)

    # __init__()

    def _render_installer_cmdline(self):
        """
        Returns installer kernel command line from the template
        """
        # try to find a template specific to this OS version
        template_filename = 'agama.cmdline.jinja'
        with open(TEMPLATES_DIR + template_filename, "r") as template_file:
            template_content = template_file.read()

        self._logger.debug(
            "Using agama installer cmdline template for "
            "OS %s of type '%s'", self._os.name, self._os.type)

        template_obj = jinja2.Template(template_content)
        return template_obj.render(config=self._info).strip()

    def _fetch_lines_until_end(self, shell, line_offset):
        """
        Fetch logs from journalctl for the Agama service.
        """
        cmd_read_log = (
            "journalctl -u agama --no-pager | "
            "tail -n +{line_offset} | head -n 100"
        )
        ret, out = shell.run(cmd_read_log.format(line_offset=line_offset))
        if ret == 0 and out:
            self._logger.debug("Agama Logs = %s", out)
            return out
        return False

    def create_autofile(self):
        """
        Fill the template and create the autofile in the target location
        """
        self._remove_autofile()
        template = jinja2.Template(self._template.content)
        self._logger.info(
            "autotemplate will be used: '%s'", self._template.name
        )

        autofile_content = template.render(config=self._info)

        with open(self._autofile_path, "w", encoding="utf-8") as autofile:
            yaml_dict = yaml.safe_load(autofile_content)
            json_string = json.dumps(yaml_dict, indent=4)
            json_data = json.loads(json_string)
            if json_data.get("user", {}).get("fullName", "").strip() == "root":
                json_data.pop("user", None)
            else:
                json_data["root"] = {}
            autofile.write(json.dumps(json_data))
            self._json_data = json.dumps(json_data, indent=4)

        with open(
            os.path.join(
                self._work_dir, os.path.basename(self._autofile_path)
            ),
            "w",
            encoding="utf-8",
        ) as autofile:
            autofile.write(json.dumps(json_data))

    def target_reboot(self):
        if isinstance(
            self._profile.hypervisor, AutoinstallMachineModel.KvmHypervisor
        ):
            self._logger.info("Rebooting into installed system")
            super().target_reboot()
            return

        self._logger.info("Kexec'ing into installed system")
        ssh_client, shell = self._get_ssh_conn()
        try:
            shell.run("reboot", timeout=1)
        except OSError:
            pass

        shell.close()
        ssh_client.logoff()
        sleep(5)
        self._logger.info(
            "Setting boot device to: %s", self._profile.get_boot_device()
        )
        self._platform.set_boot_device(self._profile.get_boot_device())

    @staticmethod
    def execute_agama_config(ssh_shell, json_config):
        """
        Sends the 'agama config load' command to the remote SSH shell,
        followed by the JSON configuration.
        """
        ssh_shell._write("agama config load\n")
        ssh_shell._write(json_config + "\n")
        ssh_shell._write("\x04")  # ctrl+D for EOF
        ssh_shell._read()

    def generate_answers_json(self):
        """
        Generate the answers.json content based on storage type and multipath.
        """
        answer_value = "no"

        for svol in self._info.get("svols", []):
            if (
                svol.get("type") == "FCP"
                and svol.get("is_root")
                and svol.get("specs", {}).get("multipath")
            ):
                answer_value = "yes"
                break

        answers = {
            "answers": [
                {"answer": answer_value, "class": "storage.activate_multipath"}
            ]
        }
        self._logger.info("Generated answers.json: %s", answers)
        return json.dumps(answers, indent=4)

    def wait_install(self):
        frequency_check = 10
        install_done_phrase = "Install phase done"
        ssh_client, shell = self._get_ssh_conn()

        self._logger.info(
            "Creating answers.json file before configuration load"
        )

        answers_path = "/root/answers.json"
        answers_json = self.generate_answers_json()
        shell._write(f"cat > {answers_path}\n")
        shell._write(answers_json + "\n")
        shell._write("\x04")
        shell._read()
        shell.run(f"agama questions answers {answers_path}")

        self._logger.info(
            "Performing agama config load with the required json"
        )

        self.execute_agama_config(shell, self._json_data)

        # Fetch and log Agama config
        ret, agama_config = shell.run("agama config show")

        if ret != 0:
            self._logger.warning("Failed to fetch Agama config show.")
        else:
            self._logger.info(
                "After Updating Agama Configuration:\n%s", agama_config
            )

        ret, _ = shell.run("agama install &")
        if ret != 0:
            raise RuntimeError(
                f"Agama install exited with status code {ret},"
                "terminating the Agama installation"
            )

        # Performs consecutive calls to tail to extract the end of the file
        max_wait_install = 3600
        timeout_installation = time() + max_wait_install
        success = False
        line_offset = 1

        while time() <= timeout_installation:
            log_output = self._fetch_lines_until_end(shell, line_offset)
            if log_output:
                if install_done_phrase in log_output:
                    self._logger.info(
                        "Agama installation completed successfully!"
                    )
                    success = True
                    break

                sleep(frequency_check)
                line_offset += 100
            else:
                raise RuntimeError(
                    "Terminating installation: "
                    "Could not fetch Agama Install Logs"
                )

        shell.close()
        ssh_client.logoff()
        if not success:
            raise TimeoutError(
                "Installation Timeout: The installation process is taking long"
            )
