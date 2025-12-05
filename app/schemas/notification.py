# app/schemas/notification.py

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from app.db.models import NotificationType
from app.schemas.user import UserRead


class NotificationBase(BaseModel):
    notification_type: NotificationType
    data: Optional[dict] = None


class NotificationCreate(NotificationBase):
    user_id: UUID
    actor_id: Optional[UUID] = None


class NotificationRead(NotificationBase):
    id: UUID
    user_id: UUID
    actor_id: Optional[UUID] = None
    read: bool  # 🆕
    created_at: datetime

    actor: Optional[UserRead] = None

    class Config:
        from_attributes = True


class NotificationWebSocket(BaseModel):
    """Message WebSocket pour les notifications"""
    type: str = "notification"
    notification: NotificationRead