# Copyright 2021 IBM Corp.
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

"""0.0.15 add HMC health checking (canary)

Revision ID: b090f8f1f8b4
Revises: 973ee45934d2
Create Date: 2021-04-23 08:46:16.721391

"""

# revision identifiers, used by Alembic.
revision = 'b090f8f1f8b4'
down_revision = '973ee45934d2'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('hmc_canary',
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('cpc_status', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('last_update', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('name', name=op.f('pk_hmc_canary')),
    sa.UniqueConstraint('name', name=op.f('uq_hmc_canary_name'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('hmc_canary')
    # ### end Alembic commands ###
