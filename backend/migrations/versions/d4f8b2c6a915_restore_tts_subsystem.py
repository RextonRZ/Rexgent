"""restore the TTS subsystem: line_audio table + character voice columns

The TTS overlay returns behind the TTS_OVERLAY flag (muted-video voice
layer: designed voices, instruct acting, cloning, mouth pacing) — the
schema it needs comes back exactly as it was before b3f7a2c1d9e4 dropped it.

Revision ID: d4f8b2c6a915
Revises: c1e5b8a4f072
Create Date: 2026-07-17
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "d4f8b2c6a915"
down_revision = "c1e5b8a4f072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "line_audio",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_number", sa.Integer, nullable=False),
        sa.Column("line_index", sa.Integer, nullable=False),
        sa.Column("character_name", sa.String(255), nullable=True),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("voice_id", sa.String(255), nullable=True),
        sa.Column("audio_url", sa.String(500), nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
    )
    op.add_column("characters", sa.Column("voice_id", sa.String(255), nullable=True))
    op.add_column("characters", sa.Column("voice_model", sa.String(100), nullable=True))
    op.add_column("characters", sa.Column("voice_source", sa.String(50), nullable=True))
    op.add_column("characters", sa.Column("voice_sample_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_table("line_audio")
    for col in ("voice_id", "voice_model", "voice_source", "voice_sample_url"):
        op.drop_column("characters", col)
