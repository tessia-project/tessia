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

"""0.0.16 (update repo url unique)

Revision ID: aaca19660fa7
Revises: b090f8f1f8b4
Create Date: 2021-05-12 22:22:32.981626

"""

# revision identifiers, used by Alembic.
revision = 'aaca19660fa7'
down_revision = 'b090f8f1f8b4'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('uq_repositories_url', 'repositories', type_='unique')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint('uq_repositories_url', 'repositories', ['url'])
    # ### end Alembic commands ###
