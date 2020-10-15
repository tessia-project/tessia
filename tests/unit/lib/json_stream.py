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
Unit test for JsonStream class
"""

#
# IMPORTS
#
from io import StringIO
from itertools import islice
from tessia.server.lib.json_stream import JsonStream
from unittest import TestCase


#
# CONSTANTS AND DEFINITIONS
#


class TestJsonStream(TestCase):
    """
    Unit test for JsonStream class
    """

    def test_decode_multiple(self):
        """
        Test decode several objects
        """
        encoded = '''{"item":1}\n
        {"item": 2}#'''
        stream = StringIO(encoded)
        items = list(islice(JsonStream(stream), 2))
        self.assertDictEqual(items[0], {"item": 1})
        self.assertDictEqual(items[1], {"item": 2})
        self.assertEqual(stream.read(1), '#')

        json_iterator = JsonStream(stream).__iter__()
        with self.assertRaises(StopIteration):
            next(json_iterator)
        for _ in json_iterator:
            assert False
    # test_decode_multiple()

    def test_decode_values(self):
        """
        Test decode json object

        In order:
        2,3,4-byte UTF-8 sequences
        Escape symbols and generic escapes
        Numbers and floating point representations
        Booleans, unicode sequences
        Empty values and spaces
        """
        encoded = '''[["\xc5\xb0nicode\xe2\x80\xafstring \xf0\x9f\x91\x8c",\n
        "escaped\\b\\r\\n\\t\\f\\"\\/\\\\\\string"]\n,
        {"int": -13, "float": 0.2e+8, "epsilon": 6.25E-02, "identity": 1e0},\n
        {"boolean":true, "false": false, "string": "\\"quoted\\"\\u0020value"},
        {"compound": {"nested": {"object": {}}, "\\u216F\\u216c": [2050]}},
        {"none value" : null , "empty array" :[ ] , "none" : [] },
        {}
        ]'''
        stream = StringIO(encoded)

        for value in JsonStream(stream):
            self.assertEqual(
                value[0], ['Űnicode\u202fstring \U0001f44c',
                           'escaped\b\r\n\t\f"/\\string']
            )
            self.assertDictEqual(
                value[1], {"int": -13, "float": 0.2e8,
                           "epsilon": 6.25e-2, "identity": 1.0}
            )
            self.assertDictEqual(
                value[2], {"boolean": True, "false": False,
                           "string": '"quoted" value'}
            )
            self.assertDictEqual(
                value[3], {"compound": {"nested": {
                    "object": {}}, "\u216f\u216c": [2050]}}
            )
            self.assertDictEqual(
                value[4], {"none value": None, "empty array": [], "none": []}
            )
            self.assertDictEqual(
                value[5], {}
            )
    # test_decode_values()

    def test_empty(self):
        """Test empty stream"""
        stream = StringIO("\0")
        for value in JsonStream(stream):
            self.assertIsNone(value)

        stream = StringIO("")
        for value in JsonStream(stream):
            self.assertIsNone(value)
    # test_empty()

    def test_fail(self):
        """Test wrong characters in the stream"""
        data = [
            ('!', 'Unexpected character: 0x21'),
            ('truth', 'Expected 0x65, got 0x74'),
            ('"a\nb"', 'Unexpected control character: 0xa'),
            ('"\xfe\xff\xff\xff\xff"', 'Invalid byte in UTF-8 string: 0xfe'),
            ('"\xef\xff\x00\x00"', 'Invalid byte in UTF-8 sequence: 0xff'),
            ('"\\u2f2g"', 'Invalid hex char in string hex escape: 0x67'),
            ('[!23]', 'Unexpected byte: 0x21 in array body'),
            ('[23!]', 'Unexpected byte: 0x21 in array body'),
            ('[23,!]', 'Unexpected byte: 0x21 in array body'),
            ('{!"a"}', 'Unexpected byte: 0x21'),
            ('{"a"!}', 'Unexpected byte: 0x21'),
            ('{"a":!}', 'Unexpected byte: 0x21'),
        ]
        for string, message in data:
            stream = StringIO(string)
            with self.assertRaises(Exception) as exc:
                for _ in JsonStream(stream):
                    pass
            self.assertIn(message, str(exc.exception))
    # test_fail()

    def test_number(self):
        """Test numeric representation"""
        data = """{
            "i.1": 1000,
            "i.2": 0,
            "i.3": -0,
            "i.4": -41,
            "f.1": 42.0,
            "f.2": 43e5,
            "f.3": -44e-0,
            "f.4": -45.e2
        }"""
        types = {'i': int, 'f': float}
        stream = StringIO(data)
        for cases in JsonStream(stream):
            self.assertEqual(len(cases.keys()), 8)
            for key, value in cases.items():
                _type = types[key[0]]
                self.assertIsInstance(value, _type)
    # test_number()
