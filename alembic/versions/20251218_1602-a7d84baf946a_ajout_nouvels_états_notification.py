"""Ajout nouvels états notification

Revision ID: a7d84baf946a
Revises: ad3c19417dc7
Create Date: 2025-12-18 16:02:05.505029

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a7d84baf946a'
down_revision: Union[str, None] = 'ad3c19417dc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1️⃣ Créer le nouvel ENUM avec toutes les valeurs
    op.execute("""
        CREATE TYPE notificationtype_new AS ENUM (
            'FRIEND_REQUEST',
            'FRIEND_ACCEPTED',
            'FRIEND_DECLINED',
            'FAVORITE_ADDED',
            'REVIEW_POSTED',
            'CHALLENGE_INVITATION',
            'CHALLENGE_ACCEPTED',
            'CHALLENGE_DECLINED'
        )
    """)

    # 2️⃣ Convertir la colonne existante vers le nouvel ENUM
    #    Ici, on utilise text comme intermédiaire
    op.execute("""
        ALTER TABLE notifications
            ALTER COLUMN notification_type TYPE notificationtype_new
            USING notification_type::text::notificationtype_new
    """)

    # 4️⃣ Supprimer l’ancien type et renommer le nouveau
    op.execute("DROP TYPE notificationtype")
    op.execute("ALTER TYPE notificationtype_new RENAME TO notificationtype")


def downgrade() -> None:
    op.execute("""
        CREATE TYPE notificationtype_old AS ENUM (
            'FRIEND_REQUEST',
            'FRIEND_ACCEPTED',
            'FRIEND_DECLINED',
            'FAVORITE_ADDED',
            'REVIEW_POSTED',
            'CHALLENGE'
        )
    """)

    op.execute("""
        UPDATE notifications 
        SET notification_type = 'CHALLENGE'
        WHERE notification_type IN ('CHALLENGE_INVITATION', 'CHALLENGE_ACCEPTED', 'CHALLENGE_DECLINED')
    """)

    op.execute("""
        ALTER TABLE notifications 
            ALTER COLUMN notification_type TYPE notificationtype_old 
            USING notification_type::text::notificationtype_old
    """)

    op.execute("DROP TYPE notificationtype")
    op.execute("ALTER TYPE notificationtype_old RENAME TO notificationtype")
