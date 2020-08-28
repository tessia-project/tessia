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
from tessia.server.config import CONF
from tessia.server.db import types
from tessia.server.db.feeder import db_insert
from tessia.server.db.connection import MANAGER
from tessia.server.db.models import BASE
from tessia.server.db.models import User, UserKey

import argparse
import logging
import io
import json
import os
import sqlalchemy
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

    Raises:
        alembic exceptions
    """
    cfg = get_alembic_cfg()
    if args.script_path:
        cfg.set_main_option("script_location", args.script_path)

    command.revision(cfg, message=args.message,
                     autogenerate=True)
# create_rev()


def downgrade_db(args):
    """
    Downgrade (migrate) an existing db schema to a previous revision

    Args:
        args (argparse.Namespace): namespace expected to contain args.revision
                                   and args.sql

    Raises:
        alembic exceptions
    """
    command.downgrade(get_alembic_cfg(), args.revision, sql=args.sql)
# downgrade_db()


def feed_db(args):
    """
    Insert data provided by a json file to the database
    """
    with open(args.filename, 'r') as json_data:
        db_insert(json.loads(json_data.read()))
# feed_db()


def get_alembic_cfg(stdout=sys.stdout):
    """
    Return alembic's config object after filling it with the correct database
    url retrieve from engine's configuration.

    Args:
        stdout (io.TextIOBase): stream to use as the stdout by alembic module

    Returns:
        alembic.config.Config: object

    Raises:
        RuntimeError: if db configuration is missing from engine's config file
    """
    try:
        db_url = CONF.get_config().get('db')['url']
    except (TypeError, KeyError):
        raise RuntimeError('No database configuration found')

    alembic_cfg = Config(ALEMBIC_CFG, stdout=stdout)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    return alembic_cfg
# get_alembic_cfg()


def get_token(_):
    """
    Return the authorization token of the admin user so that the sysadmin
    can have initial access to the tool.
    """
    try:
        obj = MANAGER.session.query(UserKey).join(
            'user_rel').filter(User.login == 'admin').one()
    except (sqlalchemy.exc.ProgrammingError,
            sqlalchemy.orm.exc.NoResultFound,
            sqlalchemy.orm.exc.MultipleResultsFound):
        print('error: db not initialized', file=sys.stderr)
        sys.exit(2)

    print('admin:{0.key_id}:{0.key_secret}'.format(obj))
# get_token()


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

    try:
        args.func(args)
    # db connection failed: report error and return specific exit code 3
    except sqlalchemy.exc.OperationalError as exc:
        print('error: {}'.format(str(exc)), file=sys.stderr)
        sys.exit(3)

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
        None: in case parsing fails

    Raises:
        None
    """
    # create the argument parser object and feed it with the possible options
    parser = argparse.ArgumentParser(
        description='Manage engine database creation and migrations'
    )

    subparsers = parser.add_subparsers()

    # current: output the current db revision
    current_parser = subparsers.add_parser(
        'current', help='show current db revision')
    current_parser.set_defaults(func=current)

    # downgrade: downgrade existing schema to a previous revision
    downgrade_parser = subparsers.add_parser(
        'downgrade', help='downgrade db schema to previous revision')
    downgrade_parser.add_argument('revision', help='revision id')
    downgrade_parser.add_argument(
        '-s', '--sql', help='sql output only (offline mode)',
        required=False, action='store_true')
    downgrade_parser.set_defaults(func=downgrade_db)

    # feed: add data to database
    feed_parser = subparsers.add_parser(
        'feed', help='insert data from a file in the database')
    feed_parser.add_argument('filename', help='json file containing data')
    feed_parser.set_defaults(func=feed_db)

    # get-token: return the initial token of the admin user,
    # this is used in a new deployment to provide initial access
    # to the tool
    get_token_parser = subparsers.add_parser(
        'get-token', help="return the admin user's token")
    get_token_parser.set_defaults(func=get_token)

    # init: initialize a new database
    init_parser = subparsers.add_parser(
        'init', help='create all tables and content for a new db')
    init_parser.set_defaults(func=init_db)

    # reset: drop all tables from models and reset revisions
    reset_parser = subparsers.add_parser(
        'reset', help='drop tables from db and optionally delete revisions')
    reset_parser.add_argument(
        '-r', '--revisions', help='delete revisions too',
        required=False, action='store_true')
    reset_parser.add_argument(
        '-y', '--yes', help='answer yes to confirmation question',
        required=False, action='store_true')
    reset_parser.set_defaults(func=reset_db)

    # upgrade: upgrade existing schema to a newer revision
    upgrade_parser = subparsers.add_parser(
        'upgrade', help='upgrade db schema to a newer revision')
    upgrade_parser.add_argument('revision', help='revision id')
    upgrade_parser.add_argument(
        '-s', '--sql', help='sql output only (offline mode)',
        required=False, action='store_true')
    upgrade_parser.set_defaults(func=upgrade_db)

    # revision related commands

    # rev-create: create a new revision (migration) file
    create_parser = subparsers.add_parser(
        'rev-create', help='create a new revision (migration) script')
    create_parser.add_argument('message', help='commit message')
    create_parser.add_argument('--script_path', help='custom script path',
                               required=False)
    create_parser.set_defaults(func=create_rev)

    # rev-list: list existing schema revisions
    list_parser = subparsers.add_parser(
        'rev-list', help='list available db revisions')
    list_parser.add_argument(
        '-v', '--verbose', help='verbose output',
        required=False, action='store_true')
    list_parser.set_defaults(func=list_revs)

    # rev-show: show information about a revision
    show_parser = subparsers.add_parser(
        'rev-show', help='show information about a revision')
    show_parser.add_argument(
        'revision', help="revision id (use 'current' for current db revision")
    show_parser.set_defaults(func=show_rev)

    # parser error can occur here to inform user of wrong options provided
    parsed_args = parser.parse_args()

    # no subcommand entered: show help usage
    if not hasattr(parsed_args, 'func'):
        parser.print_help()
        return None

    return parsed_args
# parse_cmdline()


def reset_db(args):
    """
    Drop all tables, and reset migration table. Optionally remove existing
    revisions (migration files).

    Args:
        args (argparse.Namespace): namespace expected to contain args.yes
                                   and args.revisions

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

    # alembic table might be pointing to a revision that does not exist, clean
    # it to avoid errors in the stamp step.
    if sa_engine.has_table('alembic_version'):
        sa_engine.execute('delete from alembic_version')

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

# reset_db()


def show_rev(args):
    """
    Show details on the revision specified

    Args:
        args (argparse.Namespace): namespace expected to contain args.revision

    Raises:
        alembic exceptions
    """
    if args.revision == 'current':
        command.current(get_alembic_cfg(), verbose=True)
        return

    command.show(get_alembic_cfg(), args.revision)
# show_rev()


def current(_):
    """
    Show the current database revision

    Args:
        _ (argparse.Namespace): not used

    Raises:
        alembic exceptions
    """
    mem_stdout = io.StringIO()
    command.current(get_alembic_cfg(stdout=mem_stdout))
    mem_stdout.seek(0)
    output = mem_stdout.read().strip()
    if not output:
        print('error: db not initialized', file=sys.stderr)
        sys.exit(2)
    print(output)
# current()


def upgrade_db(args):
    """
    Upgrade (migrate) an existing db schema to a newer revision

    Args:
        args (argparse.Namespace): namespace expected to contain args.revision
                                   and args.sql

    Raises:
        alembic exceptions
    """
    command.upgrade(get_alembic_cfg(), args.revision, sql=args.sql)
# upgrade_db()


if __name__ == '__main__':
    sys.exit(main())
