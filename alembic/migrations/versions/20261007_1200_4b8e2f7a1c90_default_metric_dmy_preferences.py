"""default user preferences to metric units and dmy dates

Revision ID: 4b8e2f7a1c90
Revises: 9d2f6b1c4e7a
Create Date: 2026-10-07 12:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '4b8e2f7a1c90'
down_revision = '9d2f6b1c4e7a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SILHO (Ecuador) uses kg/cm and day-month-year dates for every user.
    op.execute(
        "UPDATE user_preferences SET unit_system = 'metric', date_format = 'dmy'"
    )


def downgrade() -> None:
    pass
