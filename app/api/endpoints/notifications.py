# app/api/v1/notifications.py

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_notification
from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.schemas.notification import NotificationRead
from app.schemas.user import UserRead

router = APIRouter()


@router.get(
    "/",
    response_model=List[NotificationRead],
    summary="Récupère les notifications de l'utilisateur"
)
async def get_notifications(
        limit: int = Query(20, ge=1, le=100, description="Nombre de notifications par page"),
        offset: int = Query(0, ge=0, description="Pagination offset"),
        unread_only: bool = Query(False, description="Afficher uniquement les non lues"),
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """Récupère les notifications de l'utilisateur authentifié avec pagination"""
    notifications = await crud_notification.get_user_notifications(
        session,
        current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only
    )
    return notifications


@router.get(
    "/unread-count",
    response_model=dict,
    summary="Compte les notifications non lues"
)
async def get_unread_count(
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """Retourne le nombre de notifications non lues"""
    count = await crud_notification.get_unread_count(session, current_user.id)
    return {"count": count}


@router.put(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Marque une notification comme lue"
)
async def mark_as_read(
        notification_id: UUID,
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """Marque une notification comme lue"""
    success = await crud_notification.mark_notification_as_read(
        session, notification_id, current_user.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    return


@router.put(
    "/mark-all-read",
    response_model=dict,
    summary="Marque toutes les notifications comme lues"
)
async def mark_all_read(
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """Marque toutes les notifications comme lues"""
    count = await crud_notification.mark_all_as_read(session, current_user.id)
    return {"marked_as_read": count}


# 🆕 Optionnel : endpoint pour nettoyer les anciennes notifications
@router.delete(
    "/cleanup",
    response_model=dict,
    summary="Supprime les notifications lues de plus de 30 jours"
)
async def cleanup_old_notifications(
        days: int = Query(30, ge=1, le=365),
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """Supprime les anciennes notifications lues"""
    count = await crud_notification.delete_old_notifications(
        session, current_user.id, days
    )
    return {"deleted": count}