"""modify_sources_column_to_jsonb_array

Revision ID: ea706b87901d
Revises: 16478679379c
Create Date: 2024-09-05 19:09:15.592159

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ea706b87901d'
down_revision: Union[str, None] = '16478679379c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('messages', 'sources',
                    type_=postgresql.ARRAY(postgresql.JSONB),
                    postgresql_using='ARRAY[sources]::JSONB[]')


def downgrade() -> None:
    op.alter_column('messages', 'sources',
                    type_=postgresql.JSON,
                    postgresql_using='sources[1]')
