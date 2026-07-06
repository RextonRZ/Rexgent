"""generated clips: reference provenance + deterministic seed

Each clip records exactly which bible references (identity, costume,
prev frame, location, style) conditioned it and the seed it rendered
with — so cross-shot consistency is provable on screen.

Revision ID: f3a8d6c21b47
Revises: e7b2c5d94a11
Create Date: 2026-07-06
"""
import sqlalchemy as sa
from alembic import op

revision = "f3a8d6c21b47"
down_revision = "e7b2c5d94a11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("references_json", sa.JSON(), nullable=True))
    op.add_column("generated_clips", sa.Column("seed", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "seed")
    op.drop_column("generated_clips", "references_json")
