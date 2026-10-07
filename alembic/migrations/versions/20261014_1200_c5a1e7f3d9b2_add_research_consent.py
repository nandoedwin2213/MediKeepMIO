"""add research consent to metabolic profiles

Revision ID: c5a1e7f3d9b2
Revises: b4f2d8e6c9a3
Create Date: 2026-10-14 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = 'c5a1e7f3d9b2'
down_revision = 'b4f2d8e6c9a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'metabolic_profiles', sa.Column('research_consent', sa.Boolean(), nullable=True)
    )
    op.add_column(
        'metabolic_profiles',
        sa.Column('research_consent_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('metabolic_profiles', 'research_consent_at')
    op.drop_column('metabolic_profiles', 'research_consent')
