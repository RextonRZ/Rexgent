"""projects: per-drama delivery format (9:16 vertical or 16:9 landscape)

Chosen at creation; drives the generation ratio parameter, the export
canvas, and the player frame.

Revision ID: b6e1d3a84c29
Revises: a9c4e7f52d18
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op

revision = "b6e1d3a84c29"
down_revision = "a9c4e7f52d18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("video_ratio", sa.String(length=8),
                                        nullable=True, server_default="9:16"))


def downgrade() -> None:
    op.drop_column("projects", "video_ratio")
