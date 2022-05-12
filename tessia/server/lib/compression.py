# Copyright 2022 IBM Corp.
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
Implement GZIP compression for Flask responses.
"""

#
# IMPORTS
#
from struct import pack
import time
import zlib

#
# CONSTANTS AND DEFINITIONS
#
CHUNK_SIZE = 24 * 1024


#
# CODE
#


class BufferedStream:
    """
    Simple queue buffer
    """

    def __init__(self):
        self._chunks = []
        self._size = 0
    # __init__()

    def needs_refill(self, required_size: int) -> bool:
        """Check if buffer needs to be refilled"""
        return self._size < required_size
    # needs_refill()

    def read(self, num_bytes: int = -1) -> bytes:
        """
        Retrieve data from buffer

        Args:
            num_bytes (int): number of bytes to read (-1 denotes all)

        Returns:
            bytes: data from buffer
        """
        if len(self._chunks) == 0 or num_bytes == 0:
            return b''

        if 0 < num_bytes < self._size:
            for index, chunk in enumerate(self._chunks):
                chunk_len = len(chunk)
                if chunk_len < num_bytes:
                    num_bytes -= chunk_len
                else:
                    result = b''.join(self._chunks[:index]) + chunk[:num_bytes]
                    self._chunks = self._chunks[index:]
                    self._chunks[0] = self._chunks[0][num_bytes:]
                    self._size -= len(result)
                    return result
        # if negative count requested or more than there is - return all
        result = b''.join(self._chunks)
        self._chunks.clear()
        self._size = 0
        return result
    # read()

    def write(self, data: bytes):
        """Add data to buffer"""
        if len(data) > 0:
            self._chunks.append(data)
            self._size += len(data)
    # write()

# BufferedStream


class GzipStreamWrapper:
    """Gzip-compressed stream from a readable stream"""

    def __init__(self, input_file, mtime=None, filename: str = None):
        """Initialize the stream"""
        self._input = input_file
        self._spill = BufferedStream()
        self._zlib = zlib.compressobj(
            level=1, method=zlib.DEFLATED, wbits=-zlib.MAX_WBITS)
        self._crc = zlib.crc32(b'')
        self._read_size = 0

        if not mtime:
            mtime = time.time()
        # write gzip header: magic, compression method, flags, mtime, filename
        self._spill.write(
            pack('<3sBL2s', b'\x1f\x8b\x08', 0x08 if filename else 0,
                 int(mtime), b'\x02\xff')
            + (filename.encode('latin-1') + b'\x00' if filename else b''))
    # __init__()

    def read(self, size=-1):
        """Read data from input and compress it"""
        while self._input and (size < 0 or self._spill.needs_refill(size)):
            chunk = self._input.read(CHUNK_SIZE)
            if chunk is None or len(chunk) == 0:
                # end of file: flush compressor
                self._spill.write(self._zlib.flush(zlib.Z_SYNC_FLUSH))
                # write gzip footer: empty block, crc32, size
                self._spill.write(pack(
                    '<BBLL', 0x03, 0, self._crc,
                    self._read_size & 0xffffffff))
                # reset input, so no more footers are sent
                self._input = None
                break
            # compress chunk fo data
            self._spill.write(self._zlib.compress(chunk))
            self._crc = zlib.crc32(chunk, self._crc)
            self._read_size += len(chunk)
        return self._spill.read(size)
    # read()

# GzipStreamWrapper
