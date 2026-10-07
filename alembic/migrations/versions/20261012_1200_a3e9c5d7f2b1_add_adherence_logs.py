"""add adherence logs

Revision ID: a3e9c5d7f2b1
Revises: f1c7d3e9b5a8
Create Date: 2026-10-12 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = 'a3e9c5d7f2b1'
down_revision = 'f1c7d3e9b5a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'adherence_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('log_date', sa.Date(), nullable=False),
        sa.Column('item', sa.String(30), nullable=False),
        sa.Column('done', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('source', sa.String(20), nullable=False, server_default='patient'),
        sa.Column(
            'created_by_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            'patient_id', 'log_date', 'item', name='uq_adherence_patient_date_item'
        ),
    )
    op.create_index(
        'ix_adherence_logs_patient_id', 'adherence_logs', ['patient_id']
    )
    op.create_index('ix_adherence_logs_log_date', 'adherence_logs', ['log_date'])


def downgrade() -> None:
    op.drop_index('ix_adherence_logs_log_date', table_name='adherence_logs')
    op.drop_index('ix_adherence_logs_patient_id', table_name='adherence_logs')
    op.drop_table('adherence_logs')
