"""shot prompt_json: the crafted prompt engineering, persisted per shot

Revision ID: e8a1c5d27b40
Revises: c4d9e2f71a05
Create Date: 2026-07-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "e8a1c5d27b40"
down_revision = "c4d9e2f71a05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # {"action", "prompt", "negative_prompt", "environment": {behavior,
    #   suppressed, source, priority, location, events}} — written at craft
    # time so the UI can show the beat -> prompt transformation and WHY the
    # environment behaves the way it does (world-graph override evidence)
    op.add_column("shots", sa.Column("prompt_json", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("shots", "prompt_json")
