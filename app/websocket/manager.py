# app/websocket/manager.py

from typing import Dict, Set
from uuid import UUID
from fastapi import WebSocket


class ConnectionManager:
    """Gestionnaire de connexions WebSocket"""

    def __init__(self):
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: UUID):
        """Enregistre une connexion WebSocket pour un utilisateur"""
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)

        connection_count = len(self.active_connections[user_id])
        print(f"✅ User {user_id} connected ({connection_count} active connection(s))")

    def disconnect(self, websocket: WebSocket, user_id: UUID):
        """Déconnecte un utilisateur"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                print(f"🗑️ User {user_id} fully disconnected")
            else:
                remaining = len(self.active_connections[user_id])
                print(f"📉 User {user_id} connection closed ({remaining} remaining)")

    async def send_personal_notification(self, user_id: UUID, data: dict):
        """Envoie une notification à toutes les connexions d'un utilisateur"""
        if user_id not in self.active_connections:
            print(f"⚠️ User {user_id} not connected, notification not sent")
            return

        disconnected = set()

        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(data)
                print(f"📤 Notification sent to user {user_id}")
            except Exception as e:
                print(f"❌ Failed to send notification: {e}")
                disconnected.add(websocket)

        # Nettoyer les connexions mortes
        for ws in disconnected:
            self.disconnect(ws, user_id)

    def get_active_users_count(self) -> int:
        """Retourne le nombre d'utilisateurs connectés"""
        return len(self.active_connections)

    def get_user_connection_count(self, user_id: UUID) -> int:
        """Retourne le nombre de connexions pour un utilisateur"""
        return len(self.active_connections.get(user_id, set()))


# Instance globale
manager = ConnectionManager()