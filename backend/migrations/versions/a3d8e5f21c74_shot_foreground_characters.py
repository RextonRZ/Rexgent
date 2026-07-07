"""shots: mark foreground-only characters (back/shoulder to camera)

A shot's subject gets a face lock; a character present only as a foreground
occlusion (over-the-shoulder) anchors outfit, not identity, so the model does
not render them front-and-centre in a shot that is about someone else.

Revision ID: a3d8e5f21c74
Revises: f2a7c8d41b90
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a3d8e5f21c74"
down_revision = "f2a7c8d41b90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shots", sa.Column("foreground_characters", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("shots", "foreground_characters")
