"""project visual_style: the create-drama style picker's chosen look

Revision ID: a9c4e7d13f58
Revises: d4f8b2c6a915
Create Date: 2026-07-18
"""
import sqlalchemy as sa
from alembic import op

revision = "a9c4e7d13f58"
down_revision = "d4f8b2c6a915"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("visual_style", sa.String(length=40),
                                        nullable=True))


def downgrade():
    op.drop_column("projects", "visual_style")
