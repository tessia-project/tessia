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
Unit test for Mediator class
"""

#
# IMPORTS
#
from tessia.server.lib.mediator import MEDIATOR
from time import sleep
from unittest import TestCase

import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#

class TestMediator(TestCase):
    """
    Unit test for the Mediator library
    """

    @classmethod
    def setUpClass(cls):
        """
        Called once before any test in this test class run.
        """
        url = os.environ.get('TESSIA_MEDIATOR_URI')
        if not url:
            raise RuntimeError('env variable TESSIA_MEDIATOR_URI not set')

        # switch to test database
        MEDIATOR._mediator_uri = url.replace('/0', '/1')
        cls._mediator = MEDIATOR
    # setUpClass(cls):

    def setUp(self):
        """
        Called before each test
        """
        self._mediator._flushdb()
    # setUp()

    def test_decode(self):
        """
        Test decode binary strings and objects
        """
        self.assertEqual('string', self._mediator._decode(b'string'))
        self.assertEqual(['a', 'string', 'list'],
                         self._mediator._decode([b'a', b'string', b'list']))
        self.assertEqual(
            {'dict':'object', 'decodes': 'well'},
            self._mediator._decode({b'dict': b'object', b'decodes': b'well'}))
    # test_decode()

    def test_set_get(self):
        """
        Test decode binary strings and objects
        """
        string_value = "string_value"
        dict_value = {"this": "is", "a": "dictionary"}
        list_value = ["store", "lists", "this", "simple", "way"]
        self._mediator.set("a string", string_value)
        self._mediator.set("a dict", dict_value)
        self._mediator.set("a list", list_value)
        self.assertEqual(string_value, self._mediator.get("a string"))
        self.assertEqual(dict_value, self._mediator.get("a dict"))
        self.assertEqual(list_value, self._mediator.get("a list"))

        # test update list
        list_value = ['update ' + x for x in list_value]
        self.assertNotEqual(list_value, self._mediator.get("a list"))
        self._mediator.set("a list", list_value)
        self.assertEqual(list_value, self._mediator.get("a list"))

        # test update dict
        dict_value['a'] = 'updated dictionary'
        dict_value['b'] = 'new value'
        dict_value.pop('this')
        self.assertNotEqual(list_value, self._mediator.get("a dict"))
        self._mediator.set("a dict", dict_value)
        self.assertEqual(dict_value, self._mediator.get("a dict"))
    # test_set_get()

    def test_expire(self):
        """
        Test expiring values
        """
        string_value = "string_value"
        dict_value = {"this": "is", "a": "dictionary"}
        list_value = ["store", "lists", "this", "simple", "way"]
        self._mediator.set("a string", string_value, expire=1)
        self._mediator.set("a dict", dict_value, expire=1)
        self._mediator.set("a list", list_value, expire=1)
        self.assertEqual(string_value, self._mediator.get("a string"))
        self.assertEqual(dict_value, self._mediator.get("a dict"))
        self.assertEqual(list_value, self._mediator.get("a list"))
        sleep(1.5)
        self.assertEqual(None, self._mediator.get("a string"))
        self.assertEqual(None, self._mediator.get("a dict"))
        self.assertEqual(None, self._mediator.get("a list"))

    # test_expire()
