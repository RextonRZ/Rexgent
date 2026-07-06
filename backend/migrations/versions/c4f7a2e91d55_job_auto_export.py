"""generation jobs: auto_export flag for full-auto runs

One premise in, one finished MP4 out: a full-auto job renders the final
episode the moment its last clip lands, with no click in between.

Revision ID: c4f7a2e91d55
Revises: b6e1d3a84c29
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op

revision = "c4f7a2e91d55"
down_revision = "b6e1d3a84c29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("auto_export", sa.Boolean(),
                                               nullable=True, server_default="false"))


def downgrade() -> None:
    op.drop_column("generation_jobs", "auto_export")
