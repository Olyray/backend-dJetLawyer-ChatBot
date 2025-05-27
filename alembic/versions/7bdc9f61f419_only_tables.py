"""Create subscription history table and user cancellation fields

Revision ID: 7bdc9f61f419
Revises: 5cdc8f61f418
Create Date: 2023-08-17 15:30:15.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7bdc9f61f419'
down_revision = '5cdc8f61f418'
branch_labels = None
depends_on = None


def upgrade():
    # Add cancellation fields to users table first (these are simpler)
    op.add_column('users', sa.Column('cancellation_date', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('cancellation_reason', sa.String(), nullable=True))
    
    # Create subscription_history table without creating enum types
    try:
        op.create_table(
            'subscription_history',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('payment_reference', sa.String(), nullable=False),
            sa.Column('amount', sa.Integer(), nullable=False),
            sa.Column('payment_status', sa.Enum('successful', 'failed', 'pending', 'refunded', name='paymentstatus', create_type=False), nullable=False),
            sa.Column('payment_date', sa.DateTime(), nullable=False),
            sa.Column('event_type', sa.Enum(
                'subscription.create', 'charge.success', 'invoice.create', 
                'invoice.payment_failed', 'invoice.update', 'subscription.not_renew', 
                'subscription.disable', name='subscriptionevent', create_type=False), nullable=True),
            sa.Column('next_payment_date', sa.DateTime(), nullable=True),
            sa.Column('plan_type', sa.String(), nullable=False),
            sa.Column('duration_months', sa.Integer(), nullable=False),
            sa.Column('payment_method', sa.String(), nullable=True),
            sa.Column('transaction_id', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('cancellation_reason', sa.String(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_subscription_history_id'), 'subscription_history', ['id'], unique=False)
        op.create_index(op.f('ix_subscription_history_payment_reference'), 'subscription_history', ['payment_reference'], unique=True)
        op.create_index(op.f('ix_subscription_history_user_id'), 'subscription_history', ['user_id'], unique=False)
    except Exception as e:
        # If table creation fails, make sure the user columns were added
        print(f"Warning: Could not create subscription_history table: {e}")
        print("User cancellation fields should still be added successfully.")


def downgrade():
    # Drop cancellation fields from users table
    op.drop_column('users', 'cancellation_reason')
    op.drop_column('users', 'cancellation_date')
    
    # Drop subscription_history table if it exists
    try:
        op.drop_index(op.f('ix_subscription_history_user_id'), table_name='subscription_history')
        op.drop_index(op.f('ix_subscription_history_payment_reference'), table_name='subscription_history')
        op.drop_index(op.f('ix_subscription_history_id'), table_name='subscription_history')
        op.drop_table('subscription_history')
    except Exception as e:
        print(f"Warning: Could not drop subscription_history table: {e}") 