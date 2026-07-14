"""drop the TTS subsystem: line_audio table + character voice columns

Revision ID: b3f7a2c1d9e4
Revises: a9c4e7f18d63
Create Date: 2026-07-15
"""
import sqlalchemy as sa
from alembic import op

revision = "b3f7a2c1d9e4"
down_revision = "a9c4e7f18d63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("line_audio")
    for col in ("voice_id", "voice_model", "voice_source", "voice_sample_url"):
        op.drop_column("characters", col)


def downgrade() -> None:
    op.add_column("characters", sa.Column("voice_id", sa.String(255), nullable=True))
    op.add_column("characters", sa.Column("voice_model", sa.String(100), nullable=True))
    op.add_column("characters", sa.Column("voice_source", sa.String(50), nullable=True))
    op.add_column("characters", sa.Column("voice_sample_url", sa.String(500), nullable=True))
    # line_audio recreation intentionally omitted (disposable TTS data)
