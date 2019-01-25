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
"""0.0.8 add hpav volume type

Revision ID: 8dd090d66976
Revises: bc22c4d43961
Create Date: 2019-02-04 15:00:04.482431

"""

# revision identifiers, used by Alembic.
revision = '8dd090d66976'
down_revision = 'bc22c4d43961'
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

class VolumeType(BASE):
    """A type of volume supported by the application"""

    __tablename__ = 'volume_types'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<VolumeType(name='{}')>".format(self.name)
    # __repr__()

# VolumeType

def upgrade():
    # add new HPAV volume type
    session = SESSION(bind=op.get_bind())
    hpav_obj = VolumeType(
        name='HPAV',
        desc='HPAV alias for DASD disks'
    )
    session.add(hpav_obj)
    session.commit()
# upgrade()

def downgrade():
    # remove HPAV volume type
    session = SESSION(bind=op.get_bind())
    vol_obj = session.query(VolumeType).filter_by(name='HPAV').one()
    session.delete(vol_obj)
    session.commit()

# downgrade()
