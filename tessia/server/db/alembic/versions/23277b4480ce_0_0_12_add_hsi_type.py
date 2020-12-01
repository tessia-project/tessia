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

# pylint: disable=all
"""0.0.12 (Add HSI interface type)

Revision ID: 23277b4480ce
Revises: 2fb5758b905b
Create Date: 2020-12-01 11:26:13.365358

"""

# revision identifiers, used by Alembic.
revision = '23277b4480ce'
down_revision = '2fb5758b905b'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import Column
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import Integer, String
from sqlalchemy.orm import Session

BASE = declarative_base()

class IfaceType(BASE):
    """A type of system network interface supported by the application"""

    __tablename__ = 'iface_types'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<IfaceType(name='{}')>".format(self.name)
    # __repr__()
# IfaceType

def upgrade():
    # add HSI interface type
    session = Session(bind=op.get_bind())
    hsi_iface_type = IfaceType(
        name='HSI',
        desc='Hipersockets'
    )
    # only add the new type if it is not present already
    if not session.query(IfaceType).filter_by(name='HSI').one_or_none():
        session.add(hsi_iface_type)
        session.commit()


def downgrade():
    # remove HSI interface type
    session = Session(bind=op.get_bind())
    hsi_iface_type = session.query(IfaceType).filter_by(name='HSI').one()
    session.delete(hsi_iface_type)
    session.commit()
