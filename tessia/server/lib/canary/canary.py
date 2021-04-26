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
Module that periodically checks the HMC availability and CPC status
"""

#
# IMPORTS
#
from tessia.server.config import CONF
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import HmcCanary
from tessia.server.db.models import System
from tessia.server.db.models import SystemType
from tessia.server.db.models import SystemProfile

import logging
import requests
import time
import urllib3

#
# CONSTANTS AND DEFINITIONS
#

HMC_API_PORT = "6794"
MIN_LOOP_TIMEOUT = 60

#
# CODE
#


class Canary:
    """
    Canary class for HMC's availability and CPC's status checking.
    """
    def __init__(self):
        """
        Constructor.
        """
        self._logger = logging.getLogger(__name__)
        MANAGER.connect()
        self.hmc_to_check = []
        self.check_on = True
        self.waiting_time = MIN_LOOP_TIMEOUT

    @property
    def waiting_time(self):
        """
        Getting a waiting period between checks.

        Returns:
            int: a waiting period between checks (in seconds)
        """
        return self._waiting_time

    @waiting_time.setter
    def waiting_time(self, value):
        """
        Setting a waiting period between checks.

        Args:
            value(int): a waiting period between checks (in seconds)

        Raises:
            RuntimeError: in case the value type is incorrect
        """
        if not isinstance(value, int):
            raise RuntimeError("Parameter 'waiting_time' must be int")
        if value < MIN_LOOP_TIMEOUT:
            self._logger.warning("Provided 'waiting_time' option is less "
                                 "than the allowed value. The default "
                                 "one will be used.")
            value = MIN_LOOP_TIMEOUT
        self._waiting_time = value

    @property
    def check_on(self):
        """
        Getting information about activating checks.

        Returns:
            bool: status of activation of checks
        """
        return self._check_on

    @check_on.setter
    def check_on(self, value):
        """
        Setting information about activating checks.

        Args:
            value(bool): status of activation of checks

        Raises:
            RuntimeError: in case the value type is incorrect
        """
        if not isinstance(value, bool):
            raise RuntimeError("Canary option 'check_on' must be boolean")
        self._check_on = value
    # __init__()

    def loop(self):
        """
        The main loop in which all the logic is implemented.
        """
        self._logger.info("Canary is running...")
        self.configuration()

        while True:
            if not self.check_on:
                break
            self.get_hmc_list()
            self.check()
            self.clear_hmc_db()
            self.update_db()
            time.sleep(self._waiting_time)
    # loop()

    def configuration(self):
        """
        Reading Canary-service configuration file.
        """
        canary_config = CONF.get_config().get("canary")
        if not canary_config:
            raise RuntimeError("No Canary-service configuration provided")
        try:
            self.check_on = canary_config['check_on']
        except KeyError:
            self._logger.warning("The parameter 'check_on' is not "
                                 "defined. The default value will "
                                 "be used.")

        self._logger.info("The parameter 'check_on' is "
                          "set to %s", self.check_on)

        try:
            self.waiting_time = canary_config['waiting_time']
        except KeyError:
            self._logger.warning("The parameter 'waiting_time' is "
                                 "not defined. The default value "
                                 "will be used.")

        self._logger.info("The parameter 'waiting_time' is "
                          "set to  to %s", self.waiting_time)

        if not canary_config.get('insecure_warnings', False):
            urllib3.disable_warnings(
                        urllib3.exceptions.InsecureRequestWarning)
    # configuration()

    def get_hmc_list(self):
        """
        Getting an up-to-date and complete HMC list.
        """
        self.hmc_to_check = []
        type_for_cpc = SystemType.query.filter_by(name='CPC').one()
        cpc_obj_list = System.query.filter_by(type_id=type_for_cpc.id).all()
        if not cpc_obj_list:
            self._logger.info("There are no HMC to check.")
        else:
            for cpc_obj in cpc_obj_list:
                if cpc_obj.hostname not in \
                        [hmc['hostname'] for hmc in self.hmc_to_check]:
                    prof = SystemProfile.query.join(
                        'system_rel'
                    ).filter(
                        SystemProfile.default == bool(True)
                    ).filter(
                        SystemProfile.system == cpc_obj.name
                    ).one_or_none()
                    if prof and prof.credentials['admin-user'] and \
                        prof.credentials['admin-password']:
                        self.hmc_to_check.append(
                            {'hostname': cpc_obj.hostname,
                             'user': prof.credentials['admin-user'],
                             'password': prof.credentials['admin-password']})
    # get_hmc_list()


    def check(self):
        """
        Performs a direct HMC availability check.
        """
        for hmc in self.hmc_to_check:
            cpcs_status = []
            hmc['cpc'] = cpcs_status
            hmc['status'] = "NOT AVAILABLE"

            with requests.Session() as ses:
                url = "".join(["https://", hmc['hostname'], ":", HMC_API_PORT,
                               "/api/sessions"])
                try:
                    resp = ses.post(
                        url,
                        verify=False,
                        json={
                            'password': hmc['password'],
                            'userid': hmc['user']})
                except requests.exceptions.ConnectionError:
                    continue

                if resp.status_code == 200:
                    hmc['status'] = "AVAILABLE"
                else:
                    continue

                session_data = resp.json()
                headers = {'x-api-session': session_data['api-session']}
                url = "".join(["https://", hmc['hostname'], ":", HMC_API_PORT,
                               "/api/cpcs"])

                resp = ses.get(url, headers=headers, verify=False)
                session_data = resp.json()
                for cpc in session_data['cpcs']:
                    cpcs_status.append({
                        'name': cpc['name'],
                        'status': cpc['status']})
                hmc['cpc'] = cpcs_status

                url = "".join(["https://", hmc['hostname'], ":", HMC_API_PORT,
                               "/api/session/this-session"])

                resp = ses.delete(url, headers=headers, verify=False)
                if resp.status_code != 204:
                    self._logger.info(
                        "When closing the session, "
                        "an unexpected %s code was "
                        "received.", resp.status_code)
   # check()

    def update_db(self):
        """
        Filling the database with new data.
        The table was cleared in one of the previous steps.
        """
        entries = []
        for hmc in self.hmc_to_check:
            entry = HmcCanary()
            entry.name = hmc['hostname']
            entry.status = hmc['status']
            entry.cpc_status = hmc['cpc']
            entries.append(entry)
        MANAGER.session.add_all(entries)
        MANAGER.session.commit()
    # update_db()

    @staticmethod
    def clear_hmc_db():
        """
        Clearing the database of data from the previous check.

        We use deletion instead of updating, because this avoids
        additional checks for the relevance of the HMC list.
        """
        MANAGER.session.query(HmcCanary).delete()
        MANAGER.session.commit()
    # clear_hmc_db()
