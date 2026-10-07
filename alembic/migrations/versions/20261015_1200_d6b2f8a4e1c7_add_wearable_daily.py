"""add wearable daily summaries

Revision ID: d6b2f8a4e1c7
Revises: c5a1e7f3d9b2
Create Date: 2026-10-15 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = 'd6b2f8a4e1c7'
down_revision = 'c5a1e7f3d9b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'wearable_daily',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('source', sa.String(30), nullable=False),
        sa.Column('steps', sa.Integer(), nullable=True),
        sa.Column('exercise_minutes', sa.Integer(), nullable=True),
        sa.Column('active_kcal', sa.Integer(), nullable=True),
        sa.Column('sleep_hours', sa.Float(), nullable=True),
        sa.Column('resting_hr', sa.Float(), nullable=True),
        sa.Column('avg_hr', sa.Float(), nullable=True),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column(
            'created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('patient_id', 'day', 'source', name='uq_wearable_day_source'),
    )
    op.create_index('ix_wearable_daily_patient_id', 'wearable_daily', ['patient_id'])
    op.create_index('ix_wearable_daily_day', 'wearable_daily', ['day'])


def downgrade() -> None:
    op.drop_index('ix_wearable_daily_day', table_name='wearable_daily')
    op.drop_index('ix_wearable_daily_patient_id', table_name='wearable_daily')
    op.drop_table('wearable_daily')
