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
This module groups utility functions that are used in all the tests of the
install machine.
"""

#
# IMPORTS
#
from tessia_engine.db.models import OperatingSystem, SystemProfile, Template
from tests.unit.db.models import DbUnit

import json
import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
def setup_dbunit():
    """
    Called once for the setup of DbUnit.
    """
    # Load the database content specifically prepared for this
    # test.
    data_file = "{}/data.json".format(
        os.path.dirname(os.path.abspath(__file__)))

    with open(data_file, "r") as data_fd:
        data = data_fd.read()

    data_dict = json.loads(data)

    # Create a database using custom content,
    DbUnit.create_db(empty=True)
    DbUnit.create_entry(data_dict)

    return DbUnit
# setup_dbunit()

def get_os(os_name):
    """
    Return the OS type to be used for the installation

    Args:
        os_name (str): Name of the operating system used in the query.

    Raises:
        RuntimeError: in case the query fails to find an operating system.

    Returns:
        OperatingSystem: an instance of the OperatingSystem representing a
                         row in the table.
    """
    # os specified by user: override one defined in database and issue a
    # warning
    os_entry = OperatingSystem.query.filter_by(
        name=os_name).one_or_none()
    if os_entry is None:
        raise RuntimeError('OS {} not found'.format(
            os_name))

    return os_entry
    # _get_os()

def get_profile(profile_param):
    """
    Get a SystemProfile instance based on the profile_param
    passed in the request parameters. In case only the system name is
    provided, the default profile will be used.

    Args:
        profile_param (str): Identifier for a profile in the format
                                 <system_name>[/<profile_name>]

    Raises:
        RuntimeError: in case the profile does not exist of the format of
                      the profile_param is not as expected.

    Returns:
        SystemProfile: a SystemProfile instance.
    """
    if profile_param.find("/") != -1:
        system_name, profile_name = profile_param.split("/")
        profile_entry = SystemProfile.query.filter_by(
            name=profile_name, system=system_name).one_or_none()
        if profile_entry is None:
            raise RuntimeError("Profile not found.")
    else:
        raise RuntimeError("Incorrect format for profile_param.")

    return profile_entry
# get_profile()

def get_template(template_name):
    """
    Get a template entry in the database.

    Args:
        template_name (str): Name of the template.

    Raises:
        RuntimeError: in case the tamplete does not exist
                      in the database.

    Returns:
        Template: an instance of a Template.
    """
    template_entry = Template.query.filter_by(
        name=template_name).one_or_none()
    if template_entry is None:
        raise RuntimeError('Template {} not found'.format(
            template_name))

    return template_entry
# _get_template()
