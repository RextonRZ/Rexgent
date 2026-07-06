"""backfill: dramas created before the format picker are 16:9

The video_ratio column shipped with a 9:16 default, so every drama that
predates the picker was marked vertical — but their clips were generated
16:9 and show letterboxed. Every project that exists at this point predates
the picker (new dramas send an explicit choice afterwards), so flip them all
to landscape.

Revision ID: d5b9f1e3a76c
Revises: c4f7a2e91d55
Create Date: 2026-07-07
"""
from alembic import op

revision = "d5b9f1e3a76c"
down_revision = "c4f7a2e91d55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE projects SET video_ratio = '16:9' "
        "WHERE video_ratio IS NULL OR video_ratio = '9:16'"
    )


def downgrade() -> None:
    # one-way data backfill; nothing to reverse
    pass
