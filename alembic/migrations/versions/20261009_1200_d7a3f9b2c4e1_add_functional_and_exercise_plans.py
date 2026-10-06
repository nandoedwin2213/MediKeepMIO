"""add functional assessments and exercise plans

Revision ID: d7a3f9b2c4e1
Revises: c5d1e8a2f3b6
Create Date: 2026-10-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd7a3f9b2c4e1'
down_revision = 'c5d1e8a2f3b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'functional_assessments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('assessed_at', sa.DateTime(), nullable=False),
        sa.Column('sit_to_stand_30s', sa.Integer(), nullable=True),
        sa.Column('grip_strength_kg', sa.Float(), nullable=True),
        sa.Column('gait_speed_m_s', sa.Float(), nullable=True),
        sa.Column('walk_test_m', sa.Float(), nullable=True),
        sa.Column('rpe', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_functional_assessments_patient_id', 'functional_assessments', ['patient_id'])
    op.create_index('ix_functional_assessments_assessed_at', 'functional_assessments', ['assessed_at'])

    op.create_table(
        'exercise_plans',
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
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_exercise_plans_patient_id', 'exercise_plans', ['patient_id'])


def downgrade() -> None:
    op.drop_index('ix_exercise_plans_patient_id', table_name='exercise_plans')
    op.drop_table('exercise_plans')
    op.drop_index('ix_functional_assessments_assessed_at', table_name='functional_assessments')
    op.drop_index('ix_functional_assessments_patient_id', table_name='functional_assessments')
    op.drop_table('functional_assessments')
