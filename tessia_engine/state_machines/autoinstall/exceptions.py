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
Module containing the exceptions used by the post_install_verif module.
"""

#
# IMPORTS
#

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class Misconfiguration(BaseException):
    """
    Error caused when parameters received from a remote instance
    do not match the specified one.
    """
    def __init__(self, name_param, need_param, get_param):

        self.name_param = name_param
        self.need_param = need_param
        self.get_param = get_param

        super().__init__()
    # __init__()

    def __str__(self):
        """
        String representation for this error
        """
        msg_param_incorrect = "Incorrect '{}' configuration:" \
                              " should be '{}', but actual is '{}'".\
            format(self.name_param, self.need_param, self.get_param)

        msg_param_missed = "Incorrect configuration: {} '{}' is missed".\
            format(self.name_param, self.need_param)

        if self.get_param is None:
            msg = msg_param_missed
        else:
            msg = msg_param_incorrect
        return msg
    # __str__()
# Misconfiguration
