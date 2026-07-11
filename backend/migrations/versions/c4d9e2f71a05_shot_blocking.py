"""shot blocking: structured subjects + reverse-angle flag

Revision ID: c4d9e2f71a05
Revises: b6e1f4a92d38
Create Date: 2026-07-11
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c4d9e2f71a05"
down_revision = "b6e1f4a92d38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # {"subjects": [{character, frame_position, screen_side, facing, eyeline,
    #   action}], "reverse_angle": bool} — absolute per-shot geometry so
    # relational prose ("backs away from him") never reaches the video model
    op.add_column("shots", sa.Column("blocking_json", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("shots", "blocking_json")
