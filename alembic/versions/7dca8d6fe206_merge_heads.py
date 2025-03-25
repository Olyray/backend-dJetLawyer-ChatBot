"""merge heads

Revision ID: 7dca8d6fe206
Revises: d6e92f71bbc3, c9dadb8aec19
Create Date: 2025-03-17 19:43:20.445260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7dca8d6fe206'
down_revision: Union[str, None] = ('d6e92f71bbc3', 'c9dadb8aec19')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
