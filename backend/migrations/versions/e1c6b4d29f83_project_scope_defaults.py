"""projects: persist the scope picked at creation (episodes + seconds/episode)

The create modal budgets against a scope; the Script page seeds Full Auto
from these columns so a later visit still matches what was budgeted.

Revision ID: e1c6b4d29f83
Revises: d5b9f1e3a76c
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op

revision = "e1c6b4d29f83"
down_revision = "d5b9f1e3a76c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("episode_count", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("target_length", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "target_length")
    op.drop_column("projects", "episode_count")
