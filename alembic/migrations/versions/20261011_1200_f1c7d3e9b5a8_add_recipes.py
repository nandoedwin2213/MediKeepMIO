"""add recipe library

Revision ID: f1c7d3e9b5a8
Revises: e8b4c1d6a2f7
Create Date: 2026-10-11 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = 'f1c7d3e9b5a8'
down_revision = 'e8b4c1d6a2f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'recipes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(80), nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('servings', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('prep_minutes', sa.Integer(), nullable=True),
        sa.Column('kcal', sa.Float(), nullable=True),
        sa.Column('protein_g', sa.Float(), nullable=True),
        sa.Column('carbs_g', sa.Float(), nullable=True),
        sa.Column('fat_g', sa.Float(), nullable=True),
        sa.Column('fiber_g', sa.Float(), nullable=True),
        sa.Column('diets', sa.JSON(), nullable=False),
        sa.Column('allergens', sa.JSON(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('ingredients', sa.JSON(), nullable=False),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('image_credit', sa.String(300), nullable=True),
        sa.Column('image_source_url', sa.String(500), nullable=True),
        sa.Column('language', sa.String(10), nullable=False, server_default='es'),
        sa.Column('is_library', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            'created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_recipes_slug', 'recipes', ['slug'], unique=True)
    op.create_index('ix_recipes_category', 'recipes', ['category'])


def downgrade() -> None:
    op.drop_index('ix_recipes_category', table_name='recipes')
    op.drop_index('ix_recipes_slug', table_name='recipes')
    op.drop_table('recipes')
