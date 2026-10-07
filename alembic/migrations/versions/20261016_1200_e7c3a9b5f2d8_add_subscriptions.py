"""add PayPhone subscriptions

Revision ID: e7c3a9b5f2d8
Revises: d6b2f8a4e1c7
Create Date: 2026-10-16 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = 'e7c3a9b5f2d8'
down_revision = 'd6b2f8a4e1c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('plan', sa.String(30), nullable=False),
        sa.Column('months', sa.Integer(), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('client_transaction_id', sa.String(64), nullable=False),
        sa.Column('provider_transaction_id', sa.String(64), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=True),
        sa.Column('period_end', sa.DateTime(), nullable=True),
        sa.Column('provider_response', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('client_transaction_id', name='uq_subscription_client_tx'),
    )
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('ix_subscriptions_status', 'subscriptions', ['status'])
    op.create_index('ix_subscriptions_period_end', 'subscriptions', ['period_end'])


def downgrade() -> None:
    op.drop_index('ix_subscriptions_period_end', table_name='subscriptions')
    op.drop_index('ix_subscriptions_status', table_name='subscriptions')
    op.drop_index('ix_subscriptions_user_id', table_name='subscriptions')
    op.drop_table('subscriptions')
