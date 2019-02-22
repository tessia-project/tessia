# Copyright 2019 IBM Corp.
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
"""0.0.10 (extend system states)

Revision ID: e00527baa3fe
Revises: 8dd090d66976
Create Date: 2019-02-22 14:51:53.908586

"""

# revision identifiers, used by Alembic.
revision = 'e00527baa3fe'
down_revision = '8dd090d66976'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import Column
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import Integer, String
from sqlalchemy.orm import sessionmaker

import sqlalchemy as sa

SESSION = sessionmaker()
BASE = declarative_base()

class SystemState(BASE):
    """An allowed system state"""

    __tablename__ = 'system_states'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<SystemState(name='{}', desc='{}')>".format(
            self.name, self.desc)
    # __repr__()
# SystemState

def upgrade():
    session = SESSION(bind=op.get_bind())

    st_obj = session.query(SystemState).filter_by(name='AVAILABLE').one()
    print("state before: {}".format(str(st_obj)))
    st_obj.desc = 'System can be used normally'
    session.add(st_obj)
    print("state after: {}".format(str(st_obj)))

    st_obj = session.query(SystemState).filter_by(name='LOCKED').one()
    print("state before: {}".format(str(st_obj)))
    st_obj.desc = 'System is protected by owner from inadvertent actions'
    session.add(st_obj)
    print("state after: {}".format(str(st_obj)))

    # DEBUG gets replaced by RESERVED
    st_obj = session.query(SystemState).filter_by(name='DEBUG').one()
    print("state before: {}".format(str(st_obj)))
    st_obj.name = 'RESERVED'
    st_obj.desc = 'System is reserved for a project/team and cannot be used'
    session.add(st_obj)
    print("state after: {}".format(str(st_obj)))

    # new state UNASSIGNED
    st_obj = SystemState(
        name='UNASSIGNED',
        desc='System does not belong to any user and cannot be used'
    )
    print("state new: {}".format(str(st_obj)))

    session.add(st_obj)
    session.commit()

def downgrade():
    # ATTENTION: before the downgrade there can be no systems in
    # UNASSIGNED state
    session = SESSION(bind=op.get_bind())

    # remove new UNASSIGNED state
    st_obj = session.query(SystemState).filter_by(name='UNASSIGNED').one()
    print("state before: {}".format(str(st_obj)))
    print("state after: (deleted)")
    session.delete(st_obj)

    st_obj = session.query(SystemState).filter_by(name='AVAILABLE').one()
    print("state before: {}".format(str(st_obj)))
    st_obj.desc = 'Available for use'
    session.add(st_obj)
    print("state after: {}".format(str(st_obj)))

    st_obj = session.query(SystemState).filter_by(name='LOCKED').one()
    print("state before: {}".format(str(st_obj)))
    st_obj.desc = 'Usage blocked'
    session.add(st_obj)
    print("state after: {}".format(str(st_obj)))

    # RESERVED becomes DEBUG again
    st_obj = session.query(SystemState).filter_by(name='RESERVED').one()
    print("state before: {}".format(str(st_obj)))
    st_obj.name = 'DEBUG'
    st_obj.desc = 'Temporarily disabled for debugging purposes'
    session.add(st_obj)
    print("state after: {}".format(str(st_obj)))
    session.commit()
