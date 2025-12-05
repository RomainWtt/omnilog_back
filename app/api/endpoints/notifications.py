# app/api/v1/notifications.py

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_notification
from app.core.deps import get_current_active_user
from app.db.models import User
from app.db.session import get_session
from app.schemas.notification import NotificationRead
from app.schemas.notification_preferences import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
    NotificationPreferencesRead
)
from app.schemas.user import UserRead

router = APIRouter()


# ============================================
# NOTIFICATIONS - CRUD
# ============================================

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


# ============================================
# NOTIFICATION PREFERENCES
# ============================================

@router.get(
    "/preferences",
    response_model=NotificationPreferencesRead,
    summary="Récupère les préférences de notifications de l'utilisateur"
)
async def get_notification_preferences(
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """
    Récupère les préférences de notifications de l'utilisateur authentifié.

    Retourne les préférences pour chaque type de notification :
    - friend_request: Demandes d'ami
    - friend_accepted: Acceptations de demandes
    - friend_declined: Refus de demandes
    - favorite_added: Favoris ajoutés par des amis
    - review_posted: Reviews postées par des amis
    - challenge: Notifications de challenges
    """
    try:
        # Récupérer les préférences de l'utilisateur
        stmt = select(User.notification_preferences).where(User.id == current_user.id)
        result = await session.execute(stmt)
        preferences = result.scalar_one_or_none()

        # Si pas de préférences, utiliser les valeurs par défaut
        if not preferences:
            preferences = {
                "friend_request": True,
                "friend_accepted": True,
                "friend_declined": True,
                "favorite_added": True,
                "review_posted": True,
                "challenge": True
            }

        return NotificationPreferencesRead(
            preferences=NotificationPreferences(**preferences)
        )

    except Exception as e:
        print(f"❌ Erreur récupération préférences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des préférences"
        )


@router.put(
    "/preferences",
    response_model=NotificationPreferencesRead,
    summary="Met à jour les préférences de notifications"
)
async def update_notification_preferences(
        preferences_update: NotificationPreferencesUpdate,
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """
    Met à jour les préférences de notifications de l'utilisateur.

    Seuls les champs fournis seront mis à jour.
    Les autres préférences resteront inchangées.
    """
    try:
        # Récupérer les préférences actuelles
        stmt = select(User.notification_preferences).where(User.id == current_user.id)
        result = await session.execute(stmt)
        current_preferences = result.scalar_one_or_none()

        # Initialiser avec les valeurs par défaut si nécessaire
        if not current_preferences:
            current_preferences = {
                "friend_request": True,
                "friend_accepted": True,
                "friend_declined": True,
                "favorite_added": True,
                "review_posted": True,
                "challenge": True
            }

        # Mettre à jour avec les nouvelles valeurs
        update_data = preferences_update.model_dump(exclude_unset=True)
        updated_preferences = {**current_preferences, **update_data}

        # Sauvegarder en base de données
        stmt = (
            update(User)
            .where(User.id == current_user.id)
            .values(notification_preferences=updated_preferences)
        )
        await session.execute(stmt)
        await session.commit()

        print(f"✅ Préférences mises à jour pour {current_user.username}")

        return NotificationPreferencesRead(
            preferences=NotificationPreferences(**updated_preferences)
        )

    except Exception as e:
        print(f"❌ Erreur mise à jour préférences: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour des préférences"
        )


@router.patch(
    "/preferences/reset",
    response_model=NotificationPreferencesRead,
    summary="Réinitialise les préférences aux valeurs par défaut"
)
async def reset_notification_preferences(
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """
    Réinitialise toutes les préférences de notifications aux valeurs par défaut.

    Toutes les notifications seront activées.
    """
    try:
        # Valeurs par défaut
        default_preferences = {
            "friend_request": True,
            "friend_accepted": True,
            "friend_declined": True,
            "favorite_added": True,
            "review_posted": True,
            "challenge": True
        }

        # Sauvegarder en base de données
        stmt = (
            update(User)
            .where(User.id == current_user.id)
            .values(notification_preferences=default_preferences)
        )
        await session.execute(stmt)
        await session.commit()

        print(f"✅ Préférences réinitialisées pour {current_user.username}")

        return NotificationPreferencesRead(
            preferences=NotificationPreferences(**default_preferences)
        )

    except Exception as e:
        print(f"❌ Erreur réinitialisation préférences: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la réinitialisation des préférences"
        )