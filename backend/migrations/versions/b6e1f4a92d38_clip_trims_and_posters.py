"""generated clips: persisted trims + poster stills

Trim points set in the editor survive to ANY later export (the AI-default
path included), and every clip carries a small extracted poster JPG so
dashboards and analytics evidence outlive the clip URL's expiry.

Revision ID: b6e1f4a92d38
Revises: a3d8e5f21c74
Create Date: 2026-07-08
"""
import sqlalchemy as sa
from alembic import op

revision = "b6e1f4a92d38"
down_revision = "a3d8e5f21c74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("trim_start", sa.Float(), nullable=True))
    op.add_column("generated_clips", sa.Column("trim_end", sa.Float(), nullable=True))
    op.add_column("generated_clips", sa.Column("poster_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "poster_url")
    op.drop_column("generated_clips", "trim_end")
    op.drop_column("generated_clips", "trim_start")
