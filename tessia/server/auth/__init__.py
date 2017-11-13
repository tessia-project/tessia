# Copyright 2016, 2017 IBM Corp.
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
Dynamically load the authentication modules contained in this package
"""

#
# IMPORTS
#
from importlib.machinery import SourceFileLoader
from tessia.server.config import CONF

import os

#
# CONSTANTS AND DEFINITIONS
#
ALLOWED_MANAGERS = ['free', 'ldap']

#
# CODE
#
class Loader(object):
    """
    Helper class to handle loading of the authentication manager.
    The module is loaded upon first call to get_manager and cached so that it
    doesn't need to be loaded on every call. If the module's user want to force
    a reload they can set MANAGER back to None.
    """
    MANAGER = None

    @classmethod
    def get_manager(cls):
        """
        Load the apropriate login manager based on configuration file

        Args:
            None

        Returns:
            BaseLoginmanager: specialized instance

        Raises:
            RuntimeError: in case config option is missing or invalid method
                          specified
        """
        # module already loaded: return it
        if cls.MANAGER is not None:
            return cls.MANAGER
        try:
            login_method = CONF.get_config()['auth']['login_method']
        except (TypeError, KeyError):
            raise RuntimeError("Missing config option 'auth.login_method'")

        if login_method not in ALLOWED_MANAGERS:
            raise RuntimeError(
                "Login method '{}' not supported".format(login_method))

        my_dir = os.path.dirname(os.path.abspath(__file__))
        module_path = '{}/{}.py'.format(my_dir, login_method)
        module_name = '{}.{}'.format(__name__, login_method)

        # syntax error could occur here
        module = SourceFileLoader(module_name, module_path).load_module()

        cls.MANAGER = module.MANAGER()
        return cls.MANAGER
    # get_manager()
# Loader

def get_manager():
    """
    Convenient exposer of Loader.get_manager method

    Args:
        None

    Returns:
        BaseLoginmanager: specialized instance

    Raises:
        None
    """
    return Loader.get_manager()
