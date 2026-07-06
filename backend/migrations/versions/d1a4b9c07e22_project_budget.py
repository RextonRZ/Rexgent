"""project budget

Revision ID: d1a4b9c07e22
Revises: c8d2f4a1b7e3
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd1a4b9c07e22'
down_revision: Union[str, Sequence[str], None] = 'c8d2f4a1b7e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('credit_budget', sa.Float(), nullable=True,
                                         server_default='40.0'))
    op.add_column('projects', sa.Column('token_budget', sa.Integer(), nullable=True,
                                         server_default='2000000'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'token_budget')
    op.drop_column('projects', 'credit_budget')
