"""merge multiple heads

Revision ID: 8218252fef45
Revises: 7dca8d6fe206, add_attachments_table
Create Date: 2025-04-04 18:46:42.817016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8218252fef45'
down_revision: Union[str, None] = ('7dca8d6fe206', 'add_attachments_table')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
