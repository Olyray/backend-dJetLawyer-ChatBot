"""change source from json to json array

Revision ID: 08cbf769582c
Revises: ea706b87901d
Create Date: 2024-09-05 19:14:34.412386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '08cbf769582c'
down_revision: Union[str, None] = 'ea706b87901d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # MODIFIED: Added migration to change 'sources' column type
    op.alter_column('messages', 'sources',
                    type_=postgresql.ARRAY(postgresql.JSONB),
                    postgresql_using='ARRAY[sources]::JSONB[]')

def downgrade():
    # MODIFIED: Added downgrade operation to revert changes
    op.alter_column('messages', 'sources',
                    type_=postgresql.JSON,
                    postgresql_using='sources[1]')
