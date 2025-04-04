"""Add attachments table

Revision ID: add_attachments_table
Revises: c9dadb8aec19
Create Date: 2024-03-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_attachments_table'
down_revision: Union[str, None] = 'c9dadb8aec19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the attachments table
    op.create_table(
        'attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id'), nullable=True),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # Add index on message_id for faster lookups
    op.create_index(op.f('ix_attachments_message_id'), 'attachments', ['message_id'], unique=False)


def downgrade() -> None:
    # Drop the attachments table
    op.drop_index(op.f('ix_attachments_message_id'), table_name='attachments')
    op.drop_table('attachments') 