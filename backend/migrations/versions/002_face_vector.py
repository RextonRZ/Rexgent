"""add pgvector extension and Character.face_vector

Revision ID: 002
Revises: 001
Create Date: 2026-06-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("characters", sa.Column("face_vector", Vector(512), nullable=True))


def downgrade() -> None:
    op.drop_column("characters", "face_vector")
