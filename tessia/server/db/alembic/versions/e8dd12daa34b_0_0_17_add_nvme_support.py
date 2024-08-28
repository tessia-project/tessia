# Copyright 2024 IBM Corp.
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

"""0.0.17 (add nvme support)

Revision ID: e8dd12daa34b
Revises: aaca19660fa7
Create Date: 2024-05-16 07:02:21.962707

"""

# revision identifiers, used by Alembic.
revision = 'e8dd12daa34b'
down_revision = 'aaca19660fa7'
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

class StorageServerType(BASE):
    """A type of storage server supported by the application"""

    __tablename__ = 'storage_server_types'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    desc = Column(String, nullable=False)

    def __repr__(self):
        """Object representation"""
        return "<StorageServerType(name='{}')>".format(self.name)
    # __repr__()
# StorageServerType

def upgrade():
    # add new NVME server and volume type
    session = SESSION(bind=op.get_bind())
    nvme_server = StorageServerType(
        name='NVME',
        desc='NVME storage server'
    )
    nvme_vol = VolumeType(
        name='NVME',
        desc='NVME disk type'
    )
    session.add(nvme_server)
    session.add(nvme_vol)
    session.commit()
# upgrade()

def downgrade():
    # remove NVME server and volume type
    session = SESSION(bind=op.get_bind())
    server_obj = session.query(StorageServerType).filter_by(name='NVME').one()
    session.delete(server_obj)
    vol_obj = session.query(VolumeType).filter_by(name='NVME').one()
    session.delete(vol_obj)
    session.commit()
# downgrade()
