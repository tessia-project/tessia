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
"""0.0.7 add system field to system_ifaces

Revision ID: bc22c4d43961
Revises: 47d7e2a27f88
Create Date: 2019-01-07 15:47:53.676629

"""

# revision identifiers, used by Alembic.
revision = 'bc22c4d43961'
down_revision = '47d7e2a27f88'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import Column
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import ForeignKey
from sqlalchemy.types import Integer, String

import sqlalchemy as sa

SESSION = sessionmaker()
BASE = declarative_base()

class IpAddress(BASE):
    """An ip address for use by a system"""

    __tablename__ = 'ip_addresses'

    id = Column(Integer, primary_key=True)
    subnet_id = Column(
        Integer, ForeignKey('subnets.id'), index=True, nullable=False)
    address = Column(postgresql.INET, nullable=False)
    system_id = Column(Integer, ForeignKey('systems.id'), index=True)

    # relationships
    subnet_rel = relationship(
        'Subnet', uselist=False, lazy='joined', innerjoin=True)
# IpAddress

class Subnet(BASE):
    """A subnet part of a network zone"""

    __tablename__ = 'subnets'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
# Subnet

class System(BASE):
    """Represents a system which can provisioned, rebooted, etc."""

    __tablename__ = 'systems'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
# System

class SystemIface(BASE):
    """Represents a network interface associated to a system"""

    __tablename__ = 'system_ifaces'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    ip_address_id = Column(Integer, ForeignKey('ip_addresses.id'))
    system_id = Column(
        Integer, ForeignKey('systems.id'), index=True, nullable=False)

    # system relationship section
    system_rel = relationship(
        'System', uselist=False, lazy='joined', innerjoin=True)
# SystemIface

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ip_addresses', sa.Column('system_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_ip_addresses_system_id'), 'ip_addresses', ['system_id'], unique=False)
    op.create_foreign_key(op.f('fk_ip_addresses_system_id_systems'), 'ip_addresses', 'systems', ['system_id'], ['id'])
    # ### end Alembic commands ###

    # associate each ip address to its system
    session = SESSION(bind=op.get_bind())
    iface_query = session.query(SystemIface).filter(
        SystemIface.ip_address_id != None).all()

    for iface_obj in iface_query:
        ip_obj = session.query(IpAddress).filter_by(
            id=iface_obj.ip_address_id).one()
        human_ip = '{}/{}'.format(ip_obj.subnet_rel.name, ip_obj.address)
        if not ip_obj.system_id:
            ip_obj.system_id = iface_obj.system_id
            print('assigned ip <{}> to system <{}>'.format(
                human_ip, iface_obj.system_rel.name))
        # consistency check, two ifaces from different systems using the
        # same ip address: report error
        elif ip_obj.system_id != iface_obj.system_id:
            raise ValueError(
                'Inconsistent data; ip <{}> is in use by two different '
                'systems'.format(human_ip))

    session.commit()
# upgrade()


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(op.f('fk_ip_addresses_system_id_systems'), 'ip_addresses', type_='foreignkey')
    op.drop_index(op.f('ix_ip_addresses_system_id'), table_name='ip_addresses')
    op.drop_column('ip_addresses', 'system_id')
    # ### end Alembic commands ###
# downgrade()

