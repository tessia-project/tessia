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
"""0.0.4 mac address is nullable

Revision ID: c69735da444e
Revises: 4f32ee5b2d29
Create Date: 2018-04-18 16:50:39.618174

"""

# revision identifiers, used by Alembic.
revision = 'c69735da444e'
down_revision = '4f32ee5b2d29'
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

import os
import sqlalchemy as sa

SESSION = sessionmaker()
BASE = declarative_base()

class System(BASE):
    __tablename__ = 'systems'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    ifaces_rel = relationship('SystemIface', cascade='delete')
# System

class SystemIface(BASE):
    __tablename__ = 'system_ifaces'

    id = Column(Integer, primary_key=True)
    mac_address = Column(postgresql.MACADDR)
    name = Column(String, nullable=False)
    # system relationship section
    system_id = Column(
        Integer, ForeignKey('systems.id'), index=True, nullable=False)
    system_rel = relationship(
        'System', uselist=False, lazy='joined', innerjoin=True)
# SystemIface

class Template(BASE):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    content = Column(String, nullable=False)
    desc = Column(String)
# Template

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('system_ifaces', 'mac_address',
               existing_type=postgresql.MACADDR(),
               nullable=True)
    # ### end Alembic commands ###

    # data migration - all dummy addresses are converted to null
    session = SESSION(bind=op.get_bind())
    for iface_obj in session.query(SystemIface).filter_by(
        mac_address='ff:ff:ff:ff:ff:ff').all():
        print('{}/{}: setting mac to null'.format(
            iface_obj.system_rel.name, iface_obj.name))
        iface_obj.mac_address = None

    # update templates to new content
    templates_dir = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../../templates/")
    update_templates = ['rhel7-default', 'sles12-default', 'ubuntu16-default']
    for template in update_templates:
        temp_obj = session.query(Template).filter_by(name=template).one()
        template_path = '{}.jinja'.format(template)
        with open(templates_dir + '/' + template_path, "r") as template_file:
            temp_obj.content = template_file.read()

    session.commit()
# upgrade()

def downgrade():
    # data migration - all null addresses are converted back to dummy
    old_mac = 'ff:ff:ff:ff:ff:ff'
    session = SESSION(bind=op.get_bind())
    for iface_obj in session.query(SystemIface).filter_by(
        mac_address=None).all():
        print('{}/{}: setting mac to {}'.format(
            iface_obj.system_rel.name, iface_obj.name, old_mac))
        iface_obj.mac_address = old_mac
    session.commit()

    print('warning: template content must be rolled back manually')

    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('system_ifaces', 'mac_address',
               existing_type=postgresql.MACADDR(),
               nullable=False)
    # ### end Alembic commands ###
# downgrade()
