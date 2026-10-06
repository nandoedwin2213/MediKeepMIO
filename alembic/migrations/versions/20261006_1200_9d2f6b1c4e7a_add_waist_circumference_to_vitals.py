"""add waist_circumference to vitals

Revision ID: 9d2f6b1c4e7a
Revises: 7c1e4a9b2d35
Create Date: 2026-10-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9d2f6b1c4e7a'
down_revision = '7c1e4a9b2d35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vitals', sa.Column('waist_circumference', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('vitals', 'waist_circumference')
