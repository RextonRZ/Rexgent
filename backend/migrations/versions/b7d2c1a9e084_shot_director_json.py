"""shot director_json: the Director Engine's per-shot cinematic plan

Revision ID: b7d2c1a9e084
Revises: b3f7a2c1d9e4
Create Date: 2026-07-15
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b7d2c1a9e084"
down_revision = "b3f7a2c1d9e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shots", sa.Column("director_json", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("shots", "director_json")
