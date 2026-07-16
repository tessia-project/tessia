# Copyright 2026 IBM Corp.
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

"""0.0.18 (add cpu_type and cpu_mode to system profiles)

Revision ID: f3a1b2c4d5e6
Revises: e8dd12daa34b
Create Date: 2026-07-16 16:10:11.748092

"""

# revision identifiers, used by Alembic.
revision = 'f3a1b2c4d5e6'
down_revision = 'e8dd12daa34b'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'system_profiles',
        sa.Column('cpu_type', sa.String(), nullable=True))
    op.add_column(
        'system_profiles',
        sa.Column('cpu_mode', sa.String(), nullable=True))
# upgrade()


def downgrade():
    op.drop_column('system_profiles', 'cpu_mode')
    op.drop_column('system_profiles', 'cpu_type')
# downgrade()
