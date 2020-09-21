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
Streaming JSON parser implementation

A streaming byte oriented JSON parser. Feed it a single byte at a time and
it will emit complete objects as it comes across them. Whitespace within and
between objects is ignored. This means it can parse newline delimited JSON.

Based on the answer https://stackoverflow.com/a/47638751/949044
"""

#
# IMPORTS
#
import math

#
# CONSTANTS AND DEFINITIONS
#
TRUE = [0x72, 0x75, 0x65]
FALSE = [0x61, 0x6c, 0x73, 0x65]
NULL = [0x75, 0x6c, 0x6c]


#
# CODE
#

def json_machine(emit, next_func=None):
    """
    Read JSON value

    Args:
        emit (callable): callback for parsed value
        next_func (callable): continuation function

    Returns:
        callable: parser state machine
    """

    def _value(byte_data):
        """
        Return new state machine depending on byte value
        """
        if not byte_data:
            return None

        if byte_data in (0x09, 0x0a, 0x0d, 0x20):
            return _value  # Ignore whitespace

        if byte_data == 0x22:  # "
            return string_machine(on_value)

        if byte_data == 0x2d or (0x30 <= byte_data <= 0x39):  # - or 0-9
            return number_machine(byte_data, on_number)

        if byte_data == 0x7b:  # :
            return object_machine(on_value)

        if byte_data == 0x5b:  # [
            return array_machine(on_value)

        if byte_data == 0x74:  # t
            return constant_machine(TRUE, True, on_value)

        if byte_data == 0x66:  # f
            return constant_machine(FALSE, False, on_value)

        if byte_data == 0x6e:  # n
            return constant_machine(NULL, None, on_value)

        if next_func == _value:  # pylint: disable=comparison-with-callable
            raise Exception("Unexpected character: " + hex(byte_data))

        return next_func(byte_data)

    def on_value(value):
        emit(value)
        return next_func

    def on_number(number, byte):
        emit(number)
        return _value(byte)

    next_func = next_func or _value
    return _value


def constant_machine(bytes_data, value, emit):
    """
    Parse a constant

    Args:
        bytes_data (bytes): expected constant
        value (str): collected value
        emit (callable): callback for parsed value

    Returns:
        callable: constant parsing state machine
    """
    i = 0
    length = len(bytes_data)

    def _constant(byte_data):
        nonlocal i
        if byte_data != bytes_data[i]:
            i += 1
            raise Exception("Expected {}, got {}".format(
                hex(bytes_data[i-1]), hex(byte_data)))

        i += 1
        if i < length:
            return _constant
        return emit(value)

    return _constant


def string_machine(emit):
    """
    Parse string

    Args:
        emit (callable): callback for parsed value

    Returns:
        callable: string parsing state machine
    """
    string = ""

    def _string(byte_data):
        nonlocal string

        if byte_data == 0x22:  # "
            return emit(string)

        if byte_data == 0x5c:  # \
            return _escaped_string

        if byte_data & 0x80:  # UTF-8 handling
            return utf8_machine(byte_data, on_char_code)

        if byte_data < 0x20:  # ASCII control character
            raise Exception(
                "Unexpected control character: " + hex(byte_data))

        string += chr(byte_data)
        return _string

    def _escaped_string(byte_data):
        nonlocal string

        if byte_data in (0x22, 0x5c, 0x2f):  # " \ /
            string += chr(byte_data)
            return _string

        if byte_data == 0x62:  # b
            string += "\b"
            return _string

        if byte_data == 0x66:  # f
            string += "\f"
            return _string

        if byte_data == 0x6e:  # n
            string += "\n"
            return _string

        if byte_data == 0x72:  # r
            string += "\r"
            return _string

        if byte_data == 0x74:  # t
            string += "\t"
            return _string

        if byte_data == 0x75:  # u
            return hex_machine(on_char_code)

        # other escaped character verbatim
        string += chr(byte_data)
        return _string

    def on_char_code(char_code):
        nonlocal string
        string += chr(char_code)
        return _string

    return _string


def utf8_machine(byte_data, emit):
    """
    State machine for UTF-8 decoding

    Args:
        byte_data (byte): byte to be parsed
        emit (callable): callback for parsed value (number)

    Returns:
        callable: utf-8 parsing state machine

    Raises:
        Exception: on invalid byte sequence
    """
    left = 0
    num = 0

    def _utf8(byte_data):
        nonlocal num, left
        if (byte_data & 0xc0) != 0x80:
            raise Exception(
                "Invalid byte in UTF-8 sequence: " + hex(byte_data))

        left = left - 1

        num |= (byte_data & 0x3f) << (left * 6)
        if left:
            return _utf8
        return emit(num)

    if 0xc0 <= byte_data < 0xe0:  # 2-byte UTF-8 Character
        left = 1
        num = (byte_data & 0x1f) << 6
        return _utf8

    if 0xe0 <= byte_data < 0xf0:  # 3-byte UTF-8 Character
        left = 2
        num = (byte_data & 0xf) << 12
        return _utf8

    if 0xf0 <= byte_data < 0xf8:  # 4-byte UTF-8 Character
        left = 3
        num = (byte_data & 0x07) << 18
        return _utf8

    raise Exception("Invalid byte in UTF-8 string: " + hex(byte_data))


def hex_machine(emit):
    """
    State machine for hex escaped characters in strings

    Args:
        emit (callable): callback for parsed value (number)

    Returns:
        callable: hex-parsing state machine
    """
    left = 4
    num = 0

    def _hex(byte_data):
        nonlocal num, left

        if 0x30 <= byte_data <= 0x39:       # 0-9
            i = byte_data - 0x30
        elif 0x61 <= byte_data <= 0x66:     # a-f
            i = byte_data - 0x57
        elif 0x41 <= byte_data <= 0x46:     # A-F
            i = byte_data - 0x37
        else:
            raise Exception(
                "Invalid hex char in string hex escape: " + hex(byte_data))

        left -= 1
        num |= i << (left * 4)

        if left:
            return _hex
        return emit(num)

    return _hex


def number_machine(byte_data, emit):
    """
    Parse number, discerning floats from integers

    Args:
        byte_data (byte): byte to be parsed
        emit (callable): callback for parsed value (number)

    Returns:
        callable: number parsing state machine
    """
    sign = 1
    integer = 0
    fract = 0
    fract_exp = None   # fract_exp is negative to denote fraction of 1
    esign = 1
    exponent = None

    def _done(byte_data):
        nonlocal exponent, esign, integer, sign, fract, fract_exp
        # value = (integer + fract * 10^fract_exp) * 10^exponent
        #       = integer * 10^exponent + fract * 10^(fract_exp + exponent)
        if exponent is not None:
            # float value
            exponent *= esign
            value = float(integer) * math.pow(10, exponent)
            if fract_exp:
                value += fract * math.pow(10, exponent + fract_exp)
        elif fract_exp is not None:
            # float value
            value = float(integer) + fract * math.pow(10, fract_exp)
        else:
            # no decimal point or exponent - integer value
            value = integer

        return emit(sign * value, byte_data)

    def _later(byte_data):
        if byte_data in (0x45, 0x65):  # E e
            return _esign

        return _done(byte_data)

    def _mid(byte_data):
        nonlocal fract_exp
        if byte_data == 0x2e:  # .
            fract_exp = 0
            return _fract

        return _later(byte_data)

    def _integer(byte_data):
        nonlocal integer
        if 0x30 <= byte_data <= 0x39:
            integer = integer * 10 + (byte_data - 0x30)
            return _integer

        return _mid(byte_data)

    def _start(byte_data):
        if byte_data == 0x30:
            return _mid

        if 0x30 < byte_data <= 0x39:
            return _integer(byte_data)

        raise Exception("Invalid number: " + hex(byte_data))

    def _fract(byte_data):
        nonlocal fract, fract_exp
        if 0x30 <= byte_data <= 0x39:
            fract = fract * 10 + (byte_data - 0x30)
            fract_exp -= 1
            return _fract

        return _later(byte_data)

    def _esign(byte_data):
        nonlocal esign, exponent

        exponent = 0
        if byte_data == 0x2b:  # +
            return _exponent

        if byte_data == 0x2d:  # -
            esign = -1
            return _exponent

        return _exponent(byte_data)

    def _exponent(byte_data):
        nonlocal exponent
        if 0x30 <= byte_data <= 0x39:
            exponent = exponent * 10 + (byte_data - 0x30)
            return _exponent

        return _done(byte_data)

    if byte_data == 0x2d:  # -
        sign = -1
        return _start

    return _start(byte_data)


def array_machine(emit):
    """
    Parse array (list)

    Args:
        emit (callable): callback for parsed value (list)

    Returns:
        callable: array parsing state machine
    """
    array_data = []

    def _array(byte_data):
        if byte_data == 0x5d:  # ]
            return emit(array_data)

        return json_machine(on_value, _comma)(byte_data)

    def on_value(value):
        array_data.append(value)

    def _comma(byte_data):
        if byte_data in (0x09, 0x0a, 0x0d, 0x20):
            return _comma  # Ignore whitespace

        if byte_data == 0x2c:  # ,
            return json_machine(on_value, _comma)

        if byte_data == 0x5d:  # ]
            return emit(array_data)

        raise Exception("Unexpected byte: " +
                        hex(byte_data) + " in array body")

    return _array


def object_machine(emit):
    """
    Parse object

    Args:
        emit (callable): callback for parsed value (dict)

    Returns:
        callable: object parsing state machine
    """
    object_data = {}
    key = None

    def _object(byte_data):
        if byte_data == 0x7d:  # }
            return emit(object_data)

        return _key(byte_data)

    def _key(byte_data):
        if byte_data in (0x09, 0x0a, 0x0d, 0x20):
            return _object  # Ignore whitespace

        if byte_data == 0x22:
            return string_machine(on_key)

        raise Exception("Unexpected byte: " + hex(byte_data))

    def on_key(result):
        nonlocal key
        key = result
        return _colon

    def _colon(byte_data):
        if byte_data in (0x09, 0x0a, 0x0d, 0x20):
            return _colon  # Ignore whitespace

        if byte_data == 0x3a:  # :
            return json_machine(on_value, _comma)

        raise Exception("Unexpected byte: " + hex(byte_data))

    def on_value(value):
        object_data[key] = value

    def _comma(byte_data):
        if byte_data in (0x09, 0x0a, 0x0d, 0x20):
            return _comma  # Ignore whitespace

        if byte_data == 0x2c:  # ,
            return _key

        if byte_data == 0x7d:  #
            return emit(object_data)

        raise Exception("Unexpected byte: " + hex(byte_data))

    return _object


class JsonStream():
    """
    Streaming JSON implementation

    Usage:
        for value in JsonStream(<read stream>):
            (do something with value)
    """

    def __init__(self, stream):
        self._stream = stream

    def __iter__(self):
        """
        Return iterator object
        """
        return JsonStreamIterator(self)

    def advance(self):
        """
        Read a character from stream

        Returns:
            Union[str, None]: character read or None if stream ended
        """
        value = self._stream.read(1)
        if not value:
            return None
        return value


class JsonStreamIterator():
    """
    Internal streaming JSON iterator

    Updates JSON parser state while reading stream and returns
    complete JSON objects
    """

    def __init__(self, json_stream):
        self._stream = json_stream
        self._state = json_machine(self._emit)
        self._data = None

    def __iter__(self):
        """
        Iterator object
        """
        return self

    def __next__(self):
        """
        Return next item
        """
        if not self._state:
            raise StopIteration

        while not self._data:
            # Request characters from stream until object is found
            read_char = self._stream.advance()
            if read_char is None:
                self._state = None
                raise StopIteration

            self._state = self._state(ord(read_char))

        result = self._data
        # make internal value unavailable
        self._data = None
        return result

    def _emit(self, value):
        """
        Callback for state machine that sets internal value to the parsed one
        """
        self._data = value
