"""add nutrition plans and diet preferences

Revision ID: e8b4c1d6a2f7
Revises: d7a3f9b2c4e1
Create Date: 2026-10-10 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = 'e8b4c1d6a2f7'
down_revision = 'd7a3f9b2c4e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'metabolic_profiles', sa.Column('diet_pattern', sa.String(20), nullable=True)
    )
    op.add_column(
        'metabolic_profiles', sa.Column('food_intolerances', sa.Text(), nullable=True)
    )
    op.add_column(
        'metabolic_profiles', sa.Column('food_dislikes', sa.Text(), nullable=True)
    )
    op.add_column(
        'metabolic_profiles', sa.Column('meals_per_day', sa.Integer(), nullable=True)
    )
    op.create_table(
        'nutrition_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('plan', sa.JSON(), nullable=False),
        sa.Column('rationale', sa.JSON(), nullable=True),
        sa.Column('generator_version', sa.String(30), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True
        ),
        sa.Column(
            'approved_by_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id'),
            nullable=True,
        ),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(
        'ix_nutrition_plans_patient_id', 'nutrition_plans', ['patient_id']
    )


def downgrade() -> None:
    op.drop_index('ix_nutrition_plans_patient_id', table_name='nutrition_plans')
    op.drop_table('nutrition_plans')
    for column in ('meals_per_day', 'food_dislikes', 'food_intolerances', 'diet_pattern'):
        op.drop_column('metabolic_profiles', column)
