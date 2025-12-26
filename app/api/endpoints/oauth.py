"""
OAuth Authentication Routes - Optimized for OpenAPI generation
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from fastapi.responses import RedirectResponse
from typing import Annotated, Optional

from app.db.session import get_session
from app.core.oauth import oauth
from app.services.redis_service import redis_service
from app.core.security import create_access_token, create_refresh_token
from app.schemas.token import Token
from app.crud import crud_user, crud_oauth
from app.core.config import settings
from app.services.email_verification import EmailVerificationService
import secrets
import httpx

router = APIRouter()


@router.get(
    "/google",
    summary="Initiate Google OAuth flow",
    description="Redirects user to Google authentication page",
    tags=["OAuth"],
    responses={
        302: {
            "description": "Redirect to Google OAuth page"
        }
    }
)
async def google_login(request: Request):
    """
    Initiate Google OAuth flow

    This endpoint redirects the user to Google's OAuth page for authentication.
    After authentication, Google will redirect back to the callback URL.
    """
    # Générer un state unique pour la sécurité CSRF
    state = secrets.token_urlsafe(32)

    # Stocker le state dans Redis avec TTL de 10 minutes
    state_data = {
        "created_at": str(datetime.utcnow()),
        "valid": True
    }
    await redis_service.set(f"oauth_state:{state}", state_data, ttl=600)

    # Utiliser la redirect_uri des settings (force HTTPS en prod)
    redirect_uri = settings.GOOGLE_REDIRECT_URI

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        state=state
    )


@router.get(
    "/google/callback",
    summary="Google OAuth callback",
    description="Handles Google OAuth callback and completes user authentication",
    tags=["OAuth"],
    responses={
        302: {
            "description": "Redirect to frontend with authentication tokens"
        }
    }
)
async def google_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    code: Annotated[str, Query(description="Authorization code from Google")],
    state: Annotated[Optional[str], Query(description="State parameter for CSRF protection")] = None,
    error: Annotated[Optional[str], Query(description="Error from Google")] = None
):
    """
    Handle Google OAuth callback

    This endpoint:
    1. Receives the authorization code from Google
    2. Validates the CSRF state token
    3. Exchanges the code for user information
    4. Creates or authenticates the user
    5. Generates JWT tokens
    6. Redirects to frontend with tokens
    """
    # Gérer les erreurs OAuth
    if error:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/connexion?error={error}"
        )

    if not code:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/connexion?error=no_code"
        )

    # Vérifier et valider le state CSRF
    if state:
        state_data = await redis_service.get(f"oauth_state:{state}")

        if not state_data or not isinstance(state_data, dict) or not state_data.get("valid"):
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/connexion?error=invalid_state"
            )

        # Supprimer le state après utilisation (usage unique)
        await redis_service.delete(f"oauth_state:{state}")

    try:
        # Échanger le code d'autorisation contre un token d'accès
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': code,
                    'client_id': settings.GOOGLE_CLIENT_ID,
                    'client_secret': settings.GOOGLE_CLIENT_SECRET,
                    'redirect_uri': settings.GOOGLE_REDIRECT_URI,
                    'grant_type': 'authorization_code',
                }
            )

            if token_response.status_code != 200:
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/connexion?error=token_exchange_failed"
                )

            token_data = token_response.json()
            access_token = token_data.get('access_token')

            # Récupérer les informations de l'utilisateur depuis Google
            user_response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'}
            )

            if user_response.status_code != 200:
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/connexion?error=user_info_failed"
                )

            user_info = user_response.json()

    except Exception:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/connexion?error=oauth_error"
        )

    # Extraire les informations utilisateur
    google_id = user_info.get('id')
    email = user_info.get('email')
    name = user_info.get('name', email.split('@')[0] if email else 'user')
    picture = user_info.get('picture')

    if not email or not google_id:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/connexion?error=missing_info"
        )

    # Vérifier si l'utilisateur existe déjà avec ce compte Google
    user = await crud_oauth.get_user_by_google_id(
        session=session,
        google_id=google_id
    )

    if not user:
        # Vérifier si un compte existe avec cet email
        existing_user = await crud_user.get_user_by_email(session, email)

        if existing_user:
            # Lier le compte Google au compte existant
            user = await crud_oauth.link_google_to_existing_user(
                session=session,
                user=existing_user,
                google_id=google_id
            )

            # Marquer l'email comme vérifié
            if not user.email_verified:
                EmailVerificationService.mark_as_verified_by_oauth(user, "google")
                session.add(user)
                await session.commit()
                await session.refresh(user)
        else:
            # Créer un nouveau compte utilisateur
            base_username = name.lower().replace(' ', '_').replace('-', '_')
            base_username = ''.join(c for c in base_username if c.isalnum() or c == '_')
            if not base_username:
                base_username = 'user'

            # Générer un username unique
            username = base_username
            counter = 1
            while await crud_user.get_user_by_username(session, username):
                username = f"{base_username}_{counter}"
                counter += 1

            user = await crud_oauth.create_google_user(
                session=session,
                email=email,
                username=username,
                google_id=google_id,
                avatar_url=picture
            )

            # Marquer l'email comme vérifié (vérifié par Google)
            EmailVerificationService.mark_as_verified_by_oauth(user, "google")
            session.add(user)
            await session.commit()
            await session.refresh(user)
    else:
        # Utilisateur existant - vérifier l'email si nécessaire
        if not user.email_verified:
            EmailVerificationService.mark_as_verified_by_oauth(user, "google")
            session.add(user)
            await session.commit()
            await session.refresh(user)

    # Générer les tokens JWT pour l'application
    jwt_access_token = create_access_token(data={"sub": str(user.id)})
    jwt_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Rediriger vers le frontend avec les tokens
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback/google?access_token={jwt_access_token}&refresh_token={jwt_refresh_token}"
    )