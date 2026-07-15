"""widen shot description columns: lighting/colour_mood/emotional_beat -> Text

The Director/cinematic Stager writes full descriptive sentences into these
fields (e.g. "Natural daylight, slightly overcast to add unease"), which
overflowed VARCHAR(50)/VARCHAR(255) and threw StringDataRightTruncation on the
scene's batch insert — zero shots saved, the board crashed, the storyboard UI
hung. Widen them to unbounded Text, matching action/dialogue/notes.

Revision ID: c1e5b8a4f072
Revises: b7d2c1a9e084
Create Date: 2026-07-15
"""
import sqlalchemy as sa
from alembic import op

revision = "c1e5b8a4f072"
down_revision = "b7d2c1a9e084"
branch_labels = None
depends_on = None

_COLUMNS = ("lighting", "colour_mood", "emotional_beat")


def upgrade() -> None:
    for col in _COLUMNS:
        op.alter_column("shots", col, type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    # widths the pre-Director schema used; safe because Text values that fit
    # will round-trip, longer ones would truncate on downgrade (data loss is
    # acceptable on a revert of a widening).
    op.alter_column("shots", "lighting", type_=sa.String(length=50), existing_nullable=True)
    op.alter_column("shots", "colour_mood", type_=sa.String(length=50), existing_nullable=True)
    op.alter_column("shots", "emotional_beat", type_=sa.String(length=255), existing_nullable=True)
