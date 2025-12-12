# app/services/notification_service.py

from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_notification, crud_friendship
from app.db.models import NotificationType, FriendshipStatus
from app.schemas.notification import NotificationRead, NotificationWebSocket
from app.websocket.manager import manager


class NotificationService:
    """Service centralisé pour gérer les notifications et leur envoi WebSocket"""

    @staticmethod
    async def _check_user_preferences(
            session: AsyncSession,
            user_id: UUID,
            notification_type: NotificationType
    ) -> bool:
        """
        Vérifie si l'utilisateur souhaite recevoir ce type de notification

        Args:
            session: Session DB
            user_id: ID de l'utilisateur
            notification_type: Type de notification à vérifier

        Returns:
            bool: True si l'utilisateur veut recevoir cette notification
        """
        from sqlalchemy import select
        from app.db.models import User

        try:
            # Récupérer les préférences de l'utilisateur
            stmt = select(User.notification_preferences).where(User.id == user_id)
            result = await session.execute(stmt)
            preferences = result.scalar_one_or_none()

            # Si pas de préférences définies, accepter par défaut
            if not preferences:
                return True

            # Mapper le type de notification à la clé de préférence
            preference_key = notification_type.value  # "friend_request", "friend_accepted", etc.

            # Vérifier la préférence (par défaut True si la clé n'existe pas)
            return preferences.get(preference_key, True)

        except Exception as e:
            print(f"⚠️ Erreur vérification préférences: {e}")
            # En cas d'erreur, on envoie la notification par sécurité
            return True


    @staticmethod
    async def send_notification(
            session: AsyncSession,
            user_id: UUID,
            notification_type: NotificationType,
            actor_id: Optional[UUID] = None,
            data: Optional[Dict[str, Any]] = None,
            send_websocket: bool = True
    ) -> Optional[NotificationRead]:
        """
        Crée une notification et l'envoie optionnellement via WebSocket

        Args:
            session: Session DB
            user_id: ID du destinataire
            notification_type: Type de notification
            actor_id: ID de l'acteur (optionnel)
            data: Données additionnelles (optionnel)
            send_websocket: Envoyer via WebSocket (défaut: True)

        Returns:
            NotificationRead: La notification créée, ou None si l'utilisateur ne veut pas recevoir ce type
        """
        try:
            # 🆕 Vérifier les préférences de l'utilisateur
            should_notify = await NotificationService._check_user_preferences(
                session, user_id, notification_type
            )

            if not should_notify:
                print(f"ℹ️ Notification {notification_type.value} ignorée pour {user_id} (préférences)")
                return None

            # 1. Créer la notification en DB
            notification = await crud_notification.create_notification(
                session=session,
                user_id=user_id,
                actor_id=actor_id,
                notification_type=notification_type,
                data=data or {}
            )

            print(f"✅ Notification créée: {notification.id} ({notification_type.value})")

            # 2. Envoyer via WebSocket si demandé
            if send_websocket:
                await NotificationService._send_websocket(user_id, notification)

            return NotificationRead.model_validate(notification)

        except Exception as e:
            print(f"❌ Erreur création notification: {e}")
            import traceback
            traceback.print_exc()
            raise

    @staticmethod
    async def notify_all_friends(
            session: AsyncSession,
            user_id: UUID,
            notification_type: NotificationType,
            data: Optional[Dict[str, Any]] = None,
            send_websocket: bool = True
    ) -> List[NotificationRead]:
        """
        🆕 Envoie une notification à tous les amis d'un utilisateur

        Args:
            session: Session DB
            user_id: ID de l'utilisateur dont on veut notifier les amis
            notification_type: Type de notification
            data: Données additionnelles (optionnel)
            send_websocket: Envoyer via WebSocket (défaut: True)

        Returns:
            List[NotificationRead]: Liste des notifications créées (exclut celles refusées par préférences)
        """
        try:
            # Récupérer tous les amis
            friendships = await crud_friendship.get_user_relationships(
                session,
                user_id,
                status=FriendshipStatus.ACCEPTED
            )

            notifications = []

            for friendship in friendships:
                # Déterminer l'ami (l'autre personne dans la relation)
                friend_id = (
                    friendship.user_two_id
                    if friendship.user_one_id == user_id
                    else friendship.user_one_id
                )

                # Créer la notification pour cet ami (peut retourner None si refusée)
                notification = await NotificationService.send_notification(
                    session=session,
                    user_id=friend_id,
                    actor_id=user_id,
                    notification_type=notification_type,
                    data=data,
                    send_websocket=send_websocket
                )

                # Ajouter uniquement si la notification a été créée
                if notification:
                    notifications.append(notification)

            print(f"✅ {len(notifications)} ami(s) notifié(s) ({notification_type.value})")
            return notifications

        except Exception as e:
            print(f"❌ Erreur notification amis: {e}")
            import traceback
            traceback.print_exc()
            raise

    @staticmethod
    async def _send_websocket(user_id: UUID, notification) -> None:
        """Envoie une notification via WebSocket"""
        try:
            notification_data = NotificationWebSocket(
                notification=NotificationRead.model_validate(notification)
            )

            # Convertir en dict JSON-safe
            import json
            data_dict = json.loads(notification_data.model_dump_json())

            await manager.send_personal_notification(user_id, data_dict)
            print(f"📤 Notification WebSocket envoyée à {user_id}")

        except Exception as e:
            print(f"⚠️ Erreur envoi WebSocket (non bloquant): {e}")
            import traceback
            traceback.print_exc()
            # On ne raise pas l'erreur pour ne pas bloquer le processus principal


# Instance singleton
notification_service = NotificationService()