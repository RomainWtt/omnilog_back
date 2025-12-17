"""add password reset fields

Revision ID: e4106f05bd4f
Revises: 2a609a0a3339
Create Date: 2025-12-17 00:15:38.744078

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e4106f05bd4f'
down_revision: Union[str, None] = '2a609a0a3339'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
