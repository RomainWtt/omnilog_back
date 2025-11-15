"""merge heads

Revision ID: 49a31fea63f3
Revises: 6dfcdf5f8e14, 1b14ca656198
Create Date: 2025-11-15 14:55:27.657113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '49a31fea63f3'
down_revision: Union[str, None] = ('6dfcdf5f8e14', '1b14ca656198')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
