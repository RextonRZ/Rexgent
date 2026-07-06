"""scenes: persistent set dressing + prop state changes

Pins the background down per scene: which props must render identically
in every shot, and from which shot a prop's state changes (broken vase
stays broken).

Revision ID: a9c4e7f52d18
Revises: f3a8d6c21b47
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a9c4e7f52d18"
down_revision = "f3a8d6c21b47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scenes", sa.Column("set_json", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("scenes", "set_json")
