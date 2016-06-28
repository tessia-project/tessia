#!/usr/bin/env python3
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
Module to provide command utilites to handle database creation and migrations
"""

#
# IMPORTS
#
from alembic.config import Config
from alembic import command
from tessia_engine.config import CONF
from tessia_engine.db import types
from tessia_engine.db.feeder import db_insert
from tessia_engine.db.connection import MANAGER
from tessia_engine.db.models import BASE

import argparse
import logging
import json
import os
import sys

#
# CONSTANTS AND DEFINITIONS
#
MY_DIR = os.path.dirname(os.path.abspath(__file__))
ALEMBIC_CFG = '{}/alembic/alembic.ini'.format(MY_DIR)

#
# CODE
#
def create_rev(args):
    """
    Create a new revision (migration) script by comparing existing schema in
    database and metadata from sqlalchemy declarative_base

    Args:
        args (argparse.Namespace): namespace expected to contain args.message

    Returns:
        None

    Raises:
        alembic exceptions
    """
    command.revision(get_alembic_cfg(), message=args.message,
                     autogenerate=True)
# create_rev()

def downgrade(args):
    """
    Downgrade (migrate) an existing db schema to a previous revision

    Args:
        args (argparse.Namespace): namespace expected to contain args.revision
                                   and args.sql

    Returns:
        None

    Raises:
        alembic exceptions
    """
    command.downgrade(get_alembic_cfg(), args.revision, sql=args.sql)
# downgrade()

def feed_db(args):
    """
    Insert data provided by a json file to the database
    """
    with open(args.filename, 'r') as json_data:
        db_insert(json.loads(json_data.read()))
# feed_db()

def get_alembic_cfg():
    """
    Return alembic's config object after filling it with the correct database
    url retrieve from engine's configuration.

    Args:
        None

    Returns:
        alembic.config.Config: object

    Raises:
        RuntimeError: if db configuration is missing from engine's config file
    """
    try:
        db_url = CONF.get_config()['db']['url']
    except KeyError:
        raise RuntimeError('No database configuration found')

    alembic_cfg = Config(ALEMBIC_CFG)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    return alembic_cfg
# get_alembic_cfg()

def init_db(_):
    """
    Init the database by creating all models, stamping it with 'head' and
    adding the necessary application entries
    """
    BASE.metadata.create_all(MANAGER.engine)

    # stamp versioning table with newest revision
    command.stamp(get_alembic_cfg(), 'head')

    types.create_all()
# init_db()

def list_revs(args):
    """
    List the available revisions for migration

    Args:
        args (argparse.Namespace): namespace expected to contain args.verbose

    Returns:
        None

    Raises:
        alembic exceptions
    """
    command.history(get_alembic_cfg(), verbose=args.verbose)
# list_revs()

def main():
    """
    Entry point, calls cmdline parser and executes appropriate db action.

    Args:
        None

    Returns:
        int: 0 on db action success, 1 if wrong parameters were provided

    Raises:
        None
    """
    args = parse_cmdline()
    if args is None:
        return 1

    args.func(args)

    return 0
# main()

def parse_cmdline():
    """
    Parse command line arguments with argparse and return resulting object

    Args:
        None

    Returns:
        argparse.Namespace: namespace as returned by
                            ArgumentParser.parse_args()

    Raises:
        None
    """
    # create the argument parser object and feed it with the possible options
    parser = argparse.ArgumentParser(
        description='Manage engine database creation and migrations'
    )

    subparsers = parser.add_subparsers()

    # create: create a new revision (migration) file
    create_parser = subparsers.add_parser(
        'create-rev', help='create a new revision (migration) script')
    create_parser.add_argument('message', help='commit message')
    create_parser.set_defaults(func=create_rev)

    # downgrade: downgrade existing schema to a previous revision
    downgrade_parser = subparsers.add_parser(
        'downgrade', help='downgrade db schema to previous revision')
    downgrade_parser.add_argument('revision', help='revision id')
    downgrade_parser.add_argument(
        '-s', '--sql', help='sql output only (offline mode)',
        required=False, action='store_true')
    downgrade_parser.set_defaults(func=downgrade)

    # feed-db: add data to database
    feed_parser = subparsers.add_parser(
        'feed-db', help='insert data from file to database')
    feed_parser.add_argument('filename', help='json file containing data')
    feed_parser.set_defaults(func=feed_db)

    # init-db: initialize a brand new database
    init_parser = subparsers.add_parser(
        'init-db', help='create all tables and content for a new db')
    init_parser.set_defaults(func=init_db)

    # list: list existing schema revisions
    list_parser = subparsers.add_parser(
        'list', help='list available db revisions')
    list_parser.add_argument(
        '-v', '--verbose', help='verbose output',
        required=False, action='store_true')
    list_parser.set_defaults(func=list_revs)

    # reset: drop all tables from models and reset revisions
    reset_parser = subparsers.add_parser(
        'reset', help='drop tables from db and optionally delete revisions')
    reset_parser.add_argument(
        '-r', '--revisions', help='delete revisions too',
        required=False, action='store_true')
    reset_parser.add_argument(
        '-y', '--yes', help='answer yes to confirmation question',
        required=False, action='store_true')
    reset_parser.set_defaults(func=reset)

    # show: show information about a revision
    show_parser = subparsers.add_parser(
        'show', help='show information about a revision')
    show_parser.add_argument(
        'revision', help="revision id (use 'current' for current db revision")
    show_parser.set_defaults(func=show)

    # upgrade: upgrade existing schema to a newer revision
    upgrade_parser = subparsers.add_parser(
        'upgrade', help='upgrade db schema to a newer revision')
    upgrade_parser.add_argument('revision', help='revision id')
    upgrade_parser.add_argument(
        '-s', '--sql', help='sql output only (offline mode)',
        required=False, action='store_true')
    upgrade_parser.set_defaults(func=upgrade)

    # parser error can occur here to inform user of wrong options provided
    parsed_args = parser.parse_args()

    # no subcommand entered: show help usage
    if not hasattr(parsed_args, 'func'):
        parser.print_help()
        return

    return parsed_args
# parse_cmdline()

def reset(args):
    """
    Drop all tables, and reset migration table. Optionally remove existing
    revisions (migration files).

    Args:
        args (argparse.Namespace): namespace expected to contain args.yes
                                   and args.revisions

    Returns:
        None

    Raises:
        sqlalchemy or alembic exceptions
    """
    # get the sqlalchemy object used by our application
    sa_engine = MANAGER.engine

    # logger object
    logger = logging.getLogger()

    # user requested to drop all schema tables: confirm operation
    if not args.yes:
        option = None
        msg = 'This will drop the tables from the database'
        if args.revisions:
            msg += ' and remove all migration files'
        msg += ', are you sure? '
        print(msg, end='')
        while True:
            option = input('[Y/n]: ').strip()
            if option in ('Y', 'n'):
                break

            print("Please type 'Y' or 'n'. ", end='')
        if option == 'n':
            print('Canceled.')
            return

    BASE.metadata.drop_all(sa_engine)

    # stamp versioning table with base (empty) revision
    command.stamp(get_alembic_cfg(), 'base')

    # no request to remove revisions: nothing more to do
    if not args.revisions:
        return

    # list and remove migration files
    versions_dir = '{}/alembic/versions'.format(MY_DIR)
    try:
        migration_files = [entry for entry in os.listdir(versions_dir)
                           if entry.endswith('.py')]
    except FileNotFoundError:
        logger.warning('versions dir not found, no migration files deleted')
    else:
        for file_path in migration_files:
            logger.info('Removing migration file %s', file_path)
            os.remove('{}/{}'.format(versions_dir, file_path))

# reset()

def show(args):
    """
    Show details on the revision specified

    Args:
        args (argparse.Namespace): namespace expected to contain args.revision

    Returns:
        None

    Raises:
        alembic exceptions
    """
    if args.revision == 'current':
        command.current(get_alembic_cfg(), verbose=True)
        return

    command.show(get_alembic_cfg(), args.revision)
# show()

def upgrade(args):
    """
    Upgrade (migrate) an existing db schema to a newer revision

    Args:
        args (argparse.Namespace): namespace expected to contain args.revision
                                   and args.sql

    Returns:
        None

    Raises:
        alembic exceptions
    """
    command.upgrade(get_alembic_cfg(), args.revision, sql=args.sql)
# upgrade()

if __name__ == '__main__':
    sys.exit(main())
