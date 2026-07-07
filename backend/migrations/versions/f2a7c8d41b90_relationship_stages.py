"""character_relationships: store the relationship arc as ordered stages

The graph shows the current relationship state; stages record how the pair
got there (scene by scene) so the edge panel can draw the progression.

Revision ID: f2a7c8d41b90
Revises: e1c6b4d29f83
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f2a7c8d41b90"
down_revision = "e1c6b4d29f83"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("character_relationships", sa.Column("stages", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("character_relationships", "stages")
