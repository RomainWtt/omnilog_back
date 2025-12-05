# app/schemas/notification_preferences.py

from typing import Optional
from pydantic import BaseModel, Field


class NotificationPreferences(BaseModel):
    """Préférences de notifications utilisateur"""
    friend_request: bool = Field(default=True, description="Recevoir les demandes d'ami")
    friend_accepted: bool = Field(default=True, description="Recevoir les notifications d'acceptation")
    friend_declined: bool = Field(default=True, description="Recevoir les notifications de refus")
    favorite_added: bool = Field(default=True, description="Recevoir les notifications de favoris d'amis")
    review_posted: bool = Field(default=True, description="Recevoir les notifications de reviews d'amis")
    challenge: bool = Field(default=True, description="Recevoir les notifications de challenges")


class NotificationPreferencesUpdate(BaseModel):
    """Mise à jour des préférences de notifications"""
    friend_request: Optional[bool] = None
    friend_accepted: Optional[bool] = None
    friend_declined: Optional[bool] = None
    favorite_added: Optional[bool] = None
    review_posted: Optional[bool] = None
    challenge: Optional[bool] = None


class NotificationPreferencesRead(BaseModel):
    """Lecture des préférences de notifications avec métadonnées"""
    preferences: NotificationPreferences

    class Config:
        from_attributes = True