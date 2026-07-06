"""cost events: record the model and the token split per LLM event

Feeds the token dashboard: spend per stage, per model tier, and the
"episode for X tokens" headline all come from these columns.

Revision ID: e7b2c5d94a11
Revises: d1a4b9c07e22
Create Date: 2026-07-06
"""
import sqlalchemy as sa
from alembic import op

revision = "e7b2c5d94a11"
down_revision = "d1a4b9c07e22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cost_events", sa.Column("model", sa.String(length=32), nullable=True))
    op.add_column("cost_events", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("cost_events", sa.Column("output_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("cost_events", "output_tokens")
    op.drop_column("cost_events", "input_tokens")
    op.drop_column("cost_events", "model")
