# Copyright 2020 IBM Corp.
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

"""0.0.13 (Add scheduler index)

Revision ID: 23056fcccb9d
Revises: 23277b4480ce
Create Date: 2020-12-09 20:55:34.272548

"""

# revision identifiers, used by Alembic.
revision = '23056fcccb9d'
down_revision = '23277b4480ce'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index('ix_scheduler_jobs_state_partial', 'scheduler_jobs', ['state'], 
        postgresql_where=sa.text("((state)::text = ANY ((ARRAY['WAITING'::character varying, 'RUNNING'::character varying, 'CLEANINGUP'::character varying])::text[]))"))

def downgrade():
    op.drop_index('ix_scheduler_jobs_state_partial', 'scheduler_jobs')
