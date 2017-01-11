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
Utilities for printing content to console
"""

#
# IMPORTS
#
import click
import datetime
import subprocess
import sys

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class _Pager(object):
    """
    Class representing a Pager (i.e. less) that can receive input to be
    presented to the user.
    """
    instance = 0

    def __init__(self):
        """
        Constructor, determines whether pager can be used or not
        """
        # pager already created: cannot have two pagers at the same time
        if self.instance > 0:
            raise RuntimeError(
                'Cannot have more than one instance of pager')
        self.instance += 1

        # the process object
        self.proc = None

        # standard streams
        stdin = click.get_binary_stream('stdin')
        stdout = click.get_binary_stream('stdout')

        has_pager = True
        # not connected to a terminal: do not use a pager
        if not stdin.isatty() or not stdout.isatty():
            has_pager = False
        # we are on a terminal: check if less is available
        else:
            try:
                subprocess.run(
                    'less', shell=True, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, check=True)
            # less not available: skip pager usage
            except subprocess.CalledProcessError:
                has_pager = False

        # less is available: start the process
        if has_pager:
            self.proc = subprocess.Popen(
                'less -FRXL', shell=True, stdin=subprocess.PIPE)
            self.stream = self.proc.stdin
        # no pager capability: just send content directly to stdout
        else:
            self.stream = stdout
    # __init__()

    def write(self, content):
        """Write content to the pager"""
        content = content.encode(sys.getdefaultencoding(), 'replace')
        self.stream.write(content)
    # write()

    def close(self):
        """Close the pager"""
        if self.proc is not None:
            self.stream.close()
            while True:
                try:
                    self.proc.wait()
                # ignore Ctrl+C otherwise pager will turn into orphaned
                # process
                except KeyboardInterrupt:
                    continue

                # pager finished
                break
            # remove process object as it's dead
            self.proc = None
    # close()
# _Pager

def call_pager():
    """
    Convenient wrapper to call Pager class
    """
    return _Pager()
# call_pager()

def print_items(fields, model, format_map, items):
    """
    Receive a list of items and format them for printing.

    Args:
        fields (list): list of resource's fields to be printed
        model (potion_client.Resource): the resource's model
        format_map (dict): mapping between model attributes and functions to
                           format their value
        items (list): the resource items to be printed

    Raises:
        None

    Returns:
        None
    """
    if len(items) == 0:
        return
    if format_map is None:
        format_map = {}

    # prepare the headers with information from schema
    headers = []
    for attr in fields:
        field = getattr(model, attr)
        # __doc__ comes from the attribute 'description' in the schema
        headers.append(field.__doc__)

    # prepare each item and print it
    for item in items:
        values = []
        for attr in fields:
            format_function = format_map.get(attr)
            # a formatting function was defined for this attribute: call it
            if format_function is not None:
                value = format_function(getattr(item, attr))
            else:
                value = getattr(item, attr)
            values.append(value)
        print_hor_table(headers, [values])
# print_items()

def print_hor_table(headers, rows):
    """
    Print to the screen one or more items in horizontal orientation.

    Args:
        headers (list): in format (header1, header2, header3)
        rows (list): in format [(entry1_1, entry1_2, entry1_3),
                     (entry2_1, entry2_2, entry2_3)]

    Returns:
        None

    Raises:
        None
    """
    # determine the biggest field name size for proper formatting
    trunc_width = 0
    for field in headers:
        if len(field) > trunc_width:
            trunc_width = len(field)

    output = ''
    # process each entry and add to output
    for i in range(0, len(rows)):
        entry = rows[i]
        for j in range(0, len(entry)):
            header = headers[j]
            field_value = entry[j]
            # treat field_value, could be of different types
            if field_value is None:
                field_value = ''
            elif isinstance(field_value, datetime.datetime):
                # TODO: allow user-defined date format from config file
                field_value = field_value.strftime("%Y-%m-%d %H:%M:%S")
            else:
                field_value = str(field_value)

            output += '\n{} : '.format(header.ljust(trunc_width))

            # first line of content
            lines = field_value.strip().split('\n')
            output += lines[0]

            # different handling for next lines
            for i in range(1, len(lines)):
                # white spaces to align content
                spaces = ' ' * (trunc_width+3)
                output += '\n{}{}'.format(spaces, lines[i].strip())
        output += '\n'

    click.echo(output)
# print_hor_table()

def print_ver_table(headers, entries):
    """
    Print to the screen one or more items in vertical (traditional)
    orientation.

    Args:
        headers (list): in format (header1, header2, header3)
        entries (list): in format [(entry1_1, entry1_2, entry1_3),
                     (entry2_1, entry2_2, entry2_3)]

    Returns:
        None

    Raises:
        None
    """
    # start a pager in a subprocess to control output
    pager = call_pager()

    # flag to make the header be printed only once in the loop
    print_header = True
    # which entry we are currently working on
    entry_index = 0
    while True:
        # the rows to be printed on each iteration
        rows = []
        # use this variable to avoid the need to compute the size of the
        # rows list
        rows_qty = 0
        # there is no other way to get this info other than acessing a
        # protected attribute :(
        per_page = entries._per_page # pylint: disable=protected-access

        # on each iteration we work with a number of entries that do not exceed
        # the number of already fetched entries. That way we make sure not to
        # waste time going to the server while the user is waiting for output.
        while rows_qty < per_page:
            try:
                entry = entries[entry_index]
            except IndexError:
                break

            # add the row containing the fields' values
            rows.append([getattr(entry, field) for field in headers])
            entry_index += 1
            rows_qty += 1
        # no rows processed: no more entries to print
        if rows_qty == 0:
            break
        rows_qty = 0

        # determine biggest width for each column
        cols_width = [(len(header) + 2) for header in headers]
        for row in rows:
            for i in range(0, len(row)):
                field_value = row[i]
                # treat field_value, could be of different types
                if field_value is None:
                    field_value = ''
                elif isinstance(field_value, datetime.datetime):
                    # TODO: allow user-defined date format from config file
                    field_value = field_value.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    field_value = str(field_value)
                row[i] = field_value

                row_width = len(row[i]) + 2
                if row_width > cols_width[i]:
                    cols_width[i] = row_width

        output = ''
        # first iteration: print header
        if print_header is True:
            output_cols = []
            output_sep = []
            for i in range(0, len(headers)):
                output_cols.append(headers[i].center(cols_width[i]))
                sep = '-' * cols_width[i]
                output_sep.append(sep)
            output = '\n' + '|'.join(output_cols)
            output += '\n'
            output += '+'.join(output_sep)
            print_header = False

        # print rows
        for row in rows:
            output_row = []
            for i in range(0, len(row)):
                output_value = ' {}'.format(row[i])
                output_row.append(output_value.ljust(cols_width[i]))

            output += '\n{}'.format('|'.join(output_row))
        # send the rows to the pager's stdin
        pager.write(output)

    # kill pager's process
    pager.close()
# print_ver_table()
