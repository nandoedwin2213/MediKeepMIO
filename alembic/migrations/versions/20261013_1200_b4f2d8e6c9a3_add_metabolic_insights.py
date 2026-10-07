"""add metabolic insights

Revision ID: b4f2d8e6c9a3
Revises: a3e9c5d7f2b1
Create Date: 2026-10-13 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = 'b4f2d8e6c9a3'
down_revision = 'a3e9c5d7f2b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'metabolic_insights',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('engine_version', sa.String(30), nullable=True),
        sa.Column(
            'created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True
        ),
        sa.Column(
            'approved_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True
        ),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(
        'ix_metabolic_insights_patient_id', 'metabolic_insights', ['patient_id']
    )


def downgrade() -> None:
    op.drop_index('ix_metabolic_insights_patient_id', table_name='metabolic_insights')
    op.drop_table('metabolic_insights')
