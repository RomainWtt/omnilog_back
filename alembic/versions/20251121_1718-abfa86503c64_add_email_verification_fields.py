"""add_email_verification_fields

Revision ID: abfa86503c64
Revises: dfc7c018f8f1
Create Date: 2025-11-21 17:18:56.329981

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'abfa86503c64'
down_revision: Union[str, None] = 'dfc7c018f8f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Ajouter la colonne email_verified avec une valeur par défaut temporaire
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))

    # Ajouter les colonnes optionnelles
    op.add_column('users', sa.Column('email_verification_token', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('email_verification_token_expires', sa.DateTime(), nullable=True))

    # Marquer les utilisateurs OAuth existants comme vérifiés
    op.execute("""
               UPDATE users
               SET email_verified = TRUE
               WHERE google_id IS NOT NULL
                  OR facebook_id IS NOT NULL
                  OR apple_id IS NOT NULL
               """)


def downgrade() -> None:
    op.drop_column('users', 'email_verification_token_expires')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'email_verified')
