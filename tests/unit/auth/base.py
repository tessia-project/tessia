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
Unit test for auth base module and package initializer (__init__.py)
"""

#
# IMPORTS
#
from tessia.server import auth
from tessia.server.auth.base import BaseLoginManager
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#


class TestAuthPackageAndBase(TestCase):
    """
    Unit test for the package constructor.
    """

    def setUp(self):
        """
        Executed before the start of each test method. Creates a fake module to
        be loaded during the tests.
        """
        # force a reload in case another test already loaded something
        auth.Loader.MANAGER = None

        self.patcher_config = patch.object(auth, 'CONF')
        self.mock_config = self.patcher_config.start()

        # create a temp directory where we can store our fake module
        self.module_dir = TemporaryDirectory() # pylint: disable=consider-using-with

        # write the contents of the fake module
        fake_mod_name = 'test'
        with open('{}/{}.py'.format(self.module_dir.name, fake_mod_name),
                  'w') as module_fd:
            module_fd.write('class A: pass\nMANAGER = A')
        self.mock_config.get_config.return_value = {
            'auth': {'login_method': fake_mod_name}
        }
        auth.ALLOWED_MANAGERS = [fake_mod_name]
        # mock the directory where our target is so that it points to the
        # temp directory
        self.patcher_dirname = patch.object(auth, 'os')
        mock_os = self.patcher_dirname.start()
        self.mock_dirname = mock_os.path.dirname
        self.mock_dirname.return_value = self.module_dir.name
    # setUp()

    def tearDown(self):
        """
        Executed at the end of each test method. Disables the patches applied
        and remove temporary directory used to create the fake module.
        """
        self.patcher_config.stop()
        self.patcher_dirname.stop()
        self.module_dir.cleanup()
    # tearDown()

    def test_import_invalid_config(self):
        """
        Test if the package fails to import in case configuration is wrong

        Args:
            None

        Raises:
            AssertionError: if class instantiates fails to raise exception
        """
        # configuration has no auth section
        self.mock_config.get_config.return_value = {}
        with self.assertRaisesRegex(
                RuntimeError, "Missing config option 'auth.login_method'"):
            auth.get_manager()

        # configuration has auth section but no login_method option
        self.mock_config.get_config.return_value = {'auth': None}
        with self.assertRaisesRegex(
                RuntimeError, "Missing config option 'auth.login_method'"):
            auth.get_manager()

        # configuration has auth section but invalid login_method option
        self.mock_config.get_config.return_value = {
            'auth': {'login_method': 'foo'}
        }
        with self.assertRaisesRegex(
                RuntimeError, "Login method 'foo' not supported"):
            auth.get_manager()
    # test_import_invalid_config()

    def test_import_valid_config(self):
        """
        Test if the package fails to import in case configuration is wrong

        Raises:
            AssertionError: if class instantiates fails to raise exception
        """
        # since all preparation was done by setup we just execute and
        # validate behavior
        manager = auth.get_manager()
        self.assertEqual(manager.__class__.__name__, 'A')

        # test if caching works
        new_manager = auth.get_manager()
        self.assertIs(manager, new_manager)
    # test_import_valid_config()

    def test_base_auth_abstract_usage(self):
        """
        Verify if the base class fails when we try to instantiate it.
        """
        # pylint:disable=abstract-class-instantiated
        self.assertRaises(TypeError, BaseLoginManager)

        # since the class is abstract we need to define a concrete class to be
        # able to instantiate it
        class Child(BaseLoginManager):
            """Concrete class"""

            def authenticate(self, *args, **kwargs):
                super().authenticate(*args, **kwargs)

        child = Child()
        self.assertRaises(
            NotImplementedError, child.authenticate, 'foouser', 'foopwd')
    # test_base_auth_abstract_usage()

# TestAuthPackageAndBase
