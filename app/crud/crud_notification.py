# app/crud/crud_notification.py

from typing import Sequence, Optional
from uuid import UUID
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.models import Notification, NotificationType


async def create_notification(
        session: AsyncSession,
        user_id: UUID,
        notification_type: NotificationType,
        actor_id: Optional[UUID] = None,
        data: Optional[dict] = None
) -> Notification:
    """Crée une nouvelle notification"""
    notification = Notification(
        user_id=user_id,
        actor_id=actor_id,
        notification_type=notification_type,
        data=data or {},
        read=False  # 🆕 Par défaut non lue
    )
    session.add(notification)
    await session.commit()

    await session.refresh(notification)
    result = await session.execute(
        select(Notification)
        .where(Notification.id == notification.id)
        .options(
            selectinload(Notification.actor),
            selectinload(Notification.user)
        )
    )
    return result.scalar_one()


async def get_user_notifications(
        session: AsyncSession,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False
) -> Sequence[Notification]:
    """Récupère les notifications d'un utilisateur"""
    query = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .options(selectinload(Notification.actor))
        .order_by(Notification.created_at.desc())
    )

    # 🆕 Filtre optionnel pour les non lues
    if unread_only:
        query = query.where(Notification.read == False)

    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    return result.scalars().all()


async def mark_notification_as_read(
        session: AsyncSession,
        notification_id: UUID,
        user_id: UUID
) -> bool:
    """Marque une notification comme lue"""
    result = await session.execute(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id
        )
    )
    notification = result.scalar_one_or_none()

    if notification:
        notification.read = True
        await session.commit()
        return True

    return False


async def mark_all_as_read(
        session: AsyncSession,
        user_id: UUID
) -> int:
    """Marque toutes les notifications comme lues"""
    result = await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read == False)
        .values(read=True)
    )
    await session.commit()
    return result.rowcount


async def get_unread_count(
        session: AsyncSession,
        user_id: UUID
) -> int:
    """Compte le nombre de notifications non lues"""
    result = await session.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id, Notification.read == False)
    )
    return result.scalar_one()


# 🆕 Optionnel : supprimer les anciennes notifications
async def delete_old_notifications(
        session: AsyncSession,
        user_id: UUID,
        days: int = 30
) -> int:
    """Supprime les notifications lues de plus de X jours"""
    from datetime import datetime, timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    result = await session.execute(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.read == True,
            Notification.created_at < cutoff_date
        )
    )
    notifications = result.scalars().all()

    count = len(notifications)
    for notif in notifications:
        await session.delete(notif)

    await session.commit()
    return count