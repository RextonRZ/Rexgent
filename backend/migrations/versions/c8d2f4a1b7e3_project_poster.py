"""project poster_url

Revision ID: c8d2f4a1b7e3
Revises: ef68aed99bb8
Create Date: 2026-07-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8d2f4a1b7e3'
down_revision: Union[str, Sequence[str], None] = 'ef68aed99bb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('poster_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'poster_url')
