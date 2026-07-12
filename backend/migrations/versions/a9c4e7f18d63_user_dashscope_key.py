"""bring-your-own-key: per-user encrypted DashScope key

Revision ID: a9c4e7f18d63
Revises: f3b7d9e14c52
Create Date: 2026-07-12
"""
import sqlalchemy as sa
from alembic import op

revision = "a9c4e7f18d63"
down_revision = "f3b7d9e14c52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fernet-encrypted with the server secret; a deployed instance with
    # REQUIRE_USER_API_KEY=true refuses paid work without it, so visitors
    # bill their own Qwen Cloud accounts instead of the operator's.
    op.add_column("users", sa.Column("dashscope_key_enc", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "dashscope_key_enc")
