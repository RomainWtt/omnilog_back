"""Change media_list to JSON

Revision ID: 6a7d5e068404
Revises: 9e585fdefd6f
Create Date: 2025-12-11 17:42:32.933293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '6a7d5e068404'
down_revision: Union[str, None] = '9e585fdefd6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # vider la colonne pour éviter tout conflit
    op.alter_column(
        "challenges",
        "media_list",
        type_=sa.JSON(),
        postgresql_using="to_json(media_list)"
    )

def downgrade() -> None:
    op.execute("UPDATE challenges SET media_list = ARRAY[]::integer[]")
    op.alter_column(
        "challenges",
        "media_list",
        type_=sa.JSON(),
        postgresql_using="to_json(media_list)"
    )