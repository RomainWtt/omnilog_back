from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from app.db.models import FriendshipStatus  # Utiliser votre Enum
from app.schemas.user import UserRead  # Utilisé dans Friend

from typing import Optional, List


# --- Schémas Utilisateur pour les Relations ---

class FriendProfileRead(BaseModel):
    """
    Schéma de base contenant les infos essentielles d'un utilisateur
    dans le contexte d'une relation (pour Friendships et Amis).
    """
    id: UUID
    username: str
    profile_picture_url: Optional[str] = None

    class Config:
        from_attributes = True


# --- Modèles Friendship ---

class FriendshipCreate(BaseModel):
    user_two_id: UUID = Field(..., description="ID de l'utilisateur à qui envoyer la demande.")


class FriendshipUpdate(BaseModel):
    status: FriendshipStatus = Field(..., description="Nouveau statut de l'amitié (ACCEPTED, DECLINED, BLOCKED).")


class FriendshipRead(BaseModel):
    """
    Représente une relation complète (utilisée pour POST, PUT, ou GET avec filtre complet).
    Charge les données complètes des deux utilisateurs.
    """
    user_one: FriendProfileRead
    user_two: FriendProfileRead
    status: FriendshipStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Friend(BaseModel):
    """Représente l'autre utilisateur dans la relation d'amitié (Alternative à FriendshipRead)."""
    # Si UserRead est plus complet, utilisez-le, mais FriendProfileRead est suffisant
    user: FriendProfileRead
    status: FriendshipStatus

    class Config:
        from_attributes = True

class FriendshipReadSimple(BaseModel):
    user_one_id: UUID
    user_two_id: UUID
    status: FriendshipStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
