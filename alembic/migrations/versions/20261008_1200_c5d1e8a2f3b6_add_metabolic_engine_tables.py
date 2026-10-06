"""add metabolic engine tables and hip circumference

Revision ID: c5d1e8a2f3b6
Revises: 4b8e2f7a1c90
Create Date: 2026-10-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c5d1e8a2f3b6'
down_revision = '4b8e2f7a1c90'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vitals', sa.Column('hip_circumference', sa.Float(), nullable=True))

    op.create_table(
        'metabolic_engine_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(
        'ix_metabolic_engine_configs_version', 'metabolic_engine_configs', ['version'], unique=True
    )

    op.create_table(
        'metabolic_assessments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('assessed_at', sa.DateTime(), nullable=False),
        sa.Column('algorithm_version', sa.String(20), nullable=False),
        sa.Column('config_version', sa.Integer(), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('metabolic_syndrome_status', sa.String(20), nullable=True),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('source', sa.String(20), nullable=False, server_default='auto'),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )
    op.create_index('ix_metabolic_assessments_patient_id', 'metabolic_assessments', ['patient_id'])
    op.create_index('ix_metabolic_assessments_assessed_at', 'metabolic_assessments', ['assessed_at'])

    op.create_table(
        'metabolic_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('has_diabetes', sa.Boolean(), nullable=True),
        sa.Column('has_prediabetes', sa.Boolean(), nullable=True),
        sa.Column('has_hypertension', sa.Boolean(), nullable=True),
        sa.Column('has_dyslipidemia', sa.Boolean(), nullable=True),
        sa.Column('has_fatty_liver', sa.Boolean(), nullable=True),
        sa.Column('has_obesity', sa.Boolean(), nullable=True),
        sa.Column('has_cardiovascular_disease', sa.Boolean(), nullable=True),
        sa.Column('family_diabetes', sa.Boolean(), nullable=True),
        sa.Column('physical_activity_minutes_week', sa.Integer(), nullable=True),
        sa.Column('sitting_hours_day', sa.Float(), nullable=True),
        sa.Column('sleep_hours', sa.Float(), nullable=True),
        sa.Column('alcohol', sa.String(20), nullable=True),
        sa.Column('smoking', sa.String(20), nullable=True),
        sa.Column('sugary_drinks_per_week', sa.Integer(), nullable=True),
        sa.Column('ultraprocessed_per_week', sa.Integer(), nullable=True),
        sa.Column('fruit_veg_servings_day', sa.Integer(), nullable=True),
        sa.Column('musculoskeletal_limitations', sa.Text(), nullable=True),
        sa.Column('pain_level', sa.Integer(), nullable=True),
        sa.Column('goals', sa.Text(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(
        'ix_metabolic_profiles_patient_id', 'metabolic_profiles', ['patient_id'], unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_metabolic_profiles_patient_id', table_name='metabolic_profiles')
    op.drop_table('metabolic_profiles')
    op.drop_index('ix_metabolic_assessments_assessed_at', table_name='metabolic_assessments')
    op.drop_index('ix_metabolic_assessments_patient_id', table_name='metabolic_assessments')
    op.drop_table('metabolic_assessments')
    op.drop_index('ix_metabolic_engine_configs_version', table_name='metabolic_engine_configs')
    op.drop_table('metabolic_engine_configs')
    op.drop_column('vitals', 'hip_circumference')
