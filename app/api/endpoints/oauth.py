"""
OAuth Authentication Routes - Optimized for OpenAPI generation
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from fastapi.responses import RedirectResponse
from typing import Annotated, Optional

from app.db.session import get_session
from app.core.oauth import oauth
from app.core.security import create_access_token, create_refresh_token
from app.schemas.token import Token
from app.schemas.oauth import OAuthCallbackRequest
from app.crud import crud_user, crud_oauth
from app.core.config import settings
from app.services.email_verification import EmailVerificationService  # ✅ AJOUTÉ
import secrets
import httpx

router = APIRouter()

# Store pour les states OAuth (en production, utiliser Redis)
oauth_states = {}


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
    oauth_states[state] = True

    # Construire l'URL de redirection
    redirect_uri = request.url_for('google_callback_get')

    return await oauth.google.authorize_redirect(
        request,
        str(redirect_uri),
        state=state
    )


@router.get(
    "/google/callback",
    summary="Google OAuth callback (browser redirect)",
    description="Handles browser redirect from Google and forwards to frontend",
    tags=["OAuth"],
    responses={
        302: {
            "description": "Redirect to frontend with authorization code"
        }
    }
)
async def google_callback_get(
    request: Request,
    code: Annotated[str, Query(description="Authorization code from Google")],
    state: Annotated[Optional[str], Query(description="State parameter for CSRF protection")] = None,
    error: Annotated[Optional[str], Query(description="Error from Google")] = None
):
    """
    GET endpoint for Google OAuth callback (for browser redirects)

    This endpoint receives the redirect from Google after user authentication
    and forwards the authorization code to the frontend callback page.

    - **code**: Authorization code that can be exchanged for tokens
    - **state**: CSRF protection token
    - **error**: Error message if authentication failed
    """
    if error:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/connexion?error={error}"
        )

    if not code:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/connexion?error=no_code"
        )

    # Rediriger vers le frontend avec le code
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback/google?code={code}&state={state or ''}"
    )


@router.post(
    "/google/callback",
    response_model=Token,
    summary="Exchange Google code for JWT tokens",
    description="Exchanges Google authorization code for application JWT tokens",
    tags=["OAuth"],
    responses={
        200: {
            "description": "Successfully authenticated",
            "model": Token
        },
        400: {
            "description": "Invalid code or state parameter"
        },
        500: {
            "description": "Internal server error"
        }
    }
)
async def google_callback_post(
    callback_data: OAuthCallbackRequest,
    session: Annotated[AsyncSession, Depends(get_session)]
):
    """
    Handle Google OAuth callback and create/authenticate user

    This endpoint:
    1. Validates the state parameter (CSRF protection)
    2. Exchanges the authorization code for a Google access token
    3. Retrieves user information from Google
    4. Creates a new user or links to existing account
    5. Returns JWT tokens for application authentication

    **Request Body:**
    - **code**: Authorization code from Google (required)
    - **state**: State parameter for CSRF validation (optional)

    **Returns:**
    - **access_token**: JWT access token for API authentication
    - **refresh_token**: JWT refresh token for renewing access
    - **token_type**: Always "bearer"
    """
    # Vérifier le state pour la sécurité CSRF
    if callback_data.state and callback_data.state not in oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )

    # Nettoyer le state
    if callback_data.state:
        oauth_states.pop(callback_data.state, None)

    try:
        # Échanger le code contre un token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': callback_data.code,
                    'client_id': settings.GOOGLE_CLIENT_ID,
                    'client_secret': settings.GOOGLE_CLIENT_SECRET,
                    'redirect_uri': settings.GOOGLE_REDIRECT_URI,
                    'grant_type': 'authorization_code',
                }
            )

            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange code for token"
                )

            token_data = token_response.json()
            access_token = token_data.get('access_token')

            # Récupérer les informations utilisateur
            user_response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'}
            )

            if user_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user info"
                )

            user_info = user_response.json()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth error: {str(e)}"
        )

    # Extraire les informations
    google_id = user_info.get('id')
    email = user_info.get('email')
    name = user_info.get('name', email.split('@')[0] if email else 'user')
    picture = user_info.get('picture')
    email_verified = user_info.get('verified_email', False)

    if not email or not google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or ID not provided by Google"
        )

    # Vérifier si l'utilisateur existe déjà avec cet OAuth ID
    user = await crud_oauth.get_user_by_google_id(
        session=session,
        google_id=google_id
    )

    if not user:
        # Vérifier si un utilisateur avec cet email existe déjà
        existing_user = await crud_user.get_user_by_email(session, email)

        if existing_user:
            # Lier le compte OAuth au compte existant
            user = await crud_oauth.link_google_to_existing_user(
                session=session,
                user=existing_user,
                google_id=google_id
            )

            # ✅ AJOUTÉ : Vérifier l'email automatiquement si pas déjà fait
            if not user.email_verified:
                EmailVerificationService.mark_as_verified_by_oauth(user, "google")
                session.add(user)
                await session.commit()
                await session.refresh(user)
        else:
            # Créer un nouveau compte
            # Générer un username unique
            base_username = name.lower().replace(' ', '_').replace('-', '_')
            # Nettoyer le username (garder seulement alphanumérique et underscore)
            base_username = ''.join(c for c in base_username if c.isalnum() or c == '_')
            if not base_username:
                base_username = 'user'

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

            # ✅ AJOUTÉ : Marquer l'email comme vérifié pour les nouveaux utilisateurs OAuth
            EmailVerificationService.mark_as_verified_by_oauth(user, "google")
            session.add(user)
            await session.commit()
            await session.refresh(user)
    else:
        # ✅ AJOUTÉ : Vérifier l'email même pour les utilisateurs existants OAuth
        if not user.email_verified:
            EmailVerificationService.mark_as_verified_by_oauth(user, "google")
            session.add(user)
            await session.commit()
            await session.refresh(user)

    # Créer les tokens JWT
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )