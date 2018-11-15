# Copyright 2018 IBM Corp.
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

# pylint: disable=all
"""0.0.6 credentials refactor

Revision ID: 47d7e2a27f88
Revises: e78afd9ff2f0
Create Date: 2018-11-16 09:06:36.055983

"""

# revision identifiers, used by Alembic.
revision = '47d7e2a27f88'
down_revision = 'e78afd9ff2f0'
branch_labels = None
depends_on = None

from alembic import op
from copy import deepcopy
from sqlalchemy import Column
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import sessionmaker
from sqlalchemy.types import Integer, String

import sqlalchemy as sa

SESSION = sessionmaker()
BASE = declarative_base()

class SystemProfile(BASE):
    """A system activation profile"""
    __tablename__ = 'system_profiles'

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True, nullable=False)
    credentials = Column(postgresql.JSONB)
# SystemProfile

def upgrade():
    # migrate credentials to new format
    session = SESSION(bind=op.get_bind())
    for prof_obj in session.query(SystemProfile).all():
        orig_cred = prof_obj.credentials
        if not orig_cred:
            print("prof_id={} credentials empty, ignoring".format(prof_obj.id))
            continue
        new_cred = {}
        new_cred['admin-user'] = orig_cred['user']
        new_cred['admin-password'] = orig_cred['passwd']
        if orig_cred.get('host_zvm', {}).get('passwd'):
            new_cred['zvm-password'] = orig_cred['host_zvm']['passwd']
        if orig_cred.get('host_zvm', {}).get('byuser'):
            new_cred['zvm-logonby'] = orig_cred['host_zvm']['byuser']
        prof_obj.credentials = new_cred
        session.add(prof_obj)

        orig_cred = deepcopy(orig_cred)
        if orig_cred.get('passwd'):
            orig_cred['passwd'] = '****'
        if orig_cred.get('host_zvm', {}).get('passwd'):
            orig_cred['host_zvm']['passwd'] = '****'
        new_cred = deepcopy(new_cred)
        if new_cred.get('admin-password'):
            new_cred['admin-password'] = '****'
        if new_cred.get('zvm-password'):
            new_cred['zvm-password'] = '****'
        print("prof_id={} before=<{}> after=<{}>".format(
            prof_obj.id, orig_cred, new_cred))
    session.commit()

def downgrade():
    # revert credentials to old format
    session = SESSION(bind=op.get_bind())
    for prof_obj in session.query(SystemProfile).all():
        orig_cred = prof_obj.credentials
        if not orig_cred:
            print("prof_id={} credentials empty, ignoring".format(prof_obj.id))
            continue
        old_cred = {}
        old_cred['user'] = orig_cred['admin-user']
        old_cred['passwd'] = orig_cred['admin-password']
        if orig_cred.get('zvm-password'):
            old_cred.setdefault('host_zvm', {})['passwd'] = (
                orig_cred['zvm-password'])
        if orig_cred.get('zvm-logonby'):
            old_cred.setdefault('host_zvm', {})['byuser'] = (
                orig_cred['zvm-logonby'])
        prof_obj.credentials = old_cred
        session.add(prof_obj)

        orig_cred = deepcopy(orig_cred)
        if orig_cred.get('admin-password'):
            orig_cred['admin-password'] = '****'
        if orig_cred.get('zvm-password'):
            orig_cred['zvm-password'] = '****'
        old_cred = deepcopy(old_cred)
        if old_cred.get('passwd'):
            old_cred['passwd'] = '****'
        if old_cred.get('host_zvm', {}).get('passwd'):
            old_cred['host_zvm']['passwd'] = '****'

        print("prof_id={} before=<{}> after=<{}>".format(
            prof_obj.id, orig_cred, old_cred))
    session.commit()
