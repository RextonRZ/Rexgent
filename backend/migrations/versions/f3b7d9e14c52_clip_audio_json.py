"""clip audio_json: the per-clip audio policy, computed once, read everywhere

Revision ID: f3b7d9e14c52
Revises: e8a1c5d27b40
Create Date: 2026-07-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f3b7d9e14c52"
down_revision = "e8a1c5d27b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # {"mute": bool, "volume": float|None} — bed_decision's verdict (VAD +
    # Qwen ASR), persisted so the editor preview and the export worker read
    # ONE stored decision instead of recomputing (or disagreeing)
    op.add_column("generated_clips", sa.Column("audio_json", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "audio_json")
