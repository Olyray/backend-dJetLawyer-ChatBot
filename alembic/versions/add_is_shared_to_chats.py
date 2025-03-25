"""add_is_shared_to_chats

Revision ID: d6e92f71bbc3
Revises: c76baef9faba
Create Date: 2023-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6e92f71bbc3'
down_revision = 'c76baef9faba'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_shared column to chats table with default value of False
    op.add_column('chats', sa.Column('is_shared', sa.Boolean(), nullable=True, server_default='false'))
    
    # Set any existing null values to False
    op.execute("UPDATE chats SET is_shared = false WHERE is_shared IS NULL")
    
    # Make the column not nullable
    op.alter_column('chats', 'is_shared', nullable=False)


def downgrade():
    # Remove the is_shared column
    op.drop_column('chats', 'is_shared') 