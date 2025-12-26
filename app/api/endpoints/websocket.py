# app/api/endpoints/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.websocket.manager import manager
from app.db.session import get_session
from app.crud import crud_user
from app.core.security import decode_token

router = APIRouter()


@router.websocket("/ws/notifications")
async def websocket_endpoint(
        websocket: WebSocket,
        session: AsyncSession = Depends(get_session)
):
    """
    Endpoint WebSocket pour les notifications en temps réel.

    Requiert une authentification JWT envoyée après connexion au format:
    {"type": "auth", "token": "votre_jwt_token"}

    Supporte les messages ping/pong pour maintenir la connexion active.
    """
    await websocket.accept()
    user_id = None

    try:
        # Attendre le token d'authentification
        auth_data = await websocket.receive_json()

        if auth_data.get("type") != "auth":
            await websocket.close(code=4001, reason="Authentication required")
            return

        token = auth_data.get("token")
        if not token:
            await websocket.close(code=4001, reason="Token missing")
            return

        # Décoder et valider le token
        try:
            payload = decode_token(token)
            user_id = UUID(payload.get("sub"))

            if not user_id:
                await websocket.close(code=4001, reason="Invalid token payload")
                return

        except Exception as e:
            print(f"Token validation error: {e}")
            await websocket.close(code=4001, reason="Invalid token")
            return

        # Vérifier que l'utilisateur existe et est actif
        user = await crud_user.get_user_by_id(session, user_id)
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="User not found or inactive")
            return

        # Connecter l'utilisateur au WebSocket
        await manager.connect(websocket, user_id)

        # Envoyer confirmation de connexion
        await websocket.send_json({
            "type": "connected",
            "message": "Successfully connected to notifications"
        })

        print(f"✅ User {user_id} connected to WebSocket")

        # Garder la connexion ouverte et écouter les messages
        while True:
            data = await websocket.receive_json()

            # Gérer les ping/pong pour keep-alive
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        if user_id:
            manager.disconnect(websocket, user_id)
            print(f"❌ User {user_id} disconnected from WebSocket")

    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()

        if user_id:
            manager.disconnect(websocket, user_id)
