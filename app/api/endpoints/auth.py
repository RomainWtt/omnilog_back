import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_verification_email, send_password_reset_email
from app.db.session import get_session
from app.schemas.password_reset import PasswordResetResponse, PasswordResetRequest, PasswordResetConfirm
from app.schemas.user import UserCreate, UserRead
from app.schemas.token import Token, LoginRequest, RefreshTokenRequest
from app.crud import crud_user
from app.core.security import create_access_token, create_refresh_token, decode_token, get_password_hash
from datetime import datetime

from app.services.email_verification import EmailVerificationService
from app.services.password_reset import PasswordResetService
router = APIRouter()


# app/api/v1/endpoints/auth.py

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
        user_data: UserCreate,
        session: AsyncSession = Depends(get_session)
):
    """
    Register a new user account

    - **email**: Valid email address (must be unique)
    - **username**: Username (must be unique, 3-50 characters)
    - **password**: Password (minimum 8 characters, must contain uppercase and digit)
    - **birth_date**: REQUIRED birth date for age verification (must be 13+)
    - **is_public**: Optional, default to True
    """
    # Check if user already exists
    existing_user = await crud_user.get_user_by_email(session, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    existing_username = await crud_user.get_user_by_username(session, user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Check age requirement (13+) - OBLIGATOIRE
    if not user_data.birth_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Birth date is required. You must be at least 13 years old to register."
        )

    today = datetime.now().date()
    age = today.year - user_data.birth_date.year - (
            (today.month, today.day) < (user_data.birth_date.month, user_data.birth_date.day)
    )
    if age < 13:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must be at least 13 years old to register"
        )

    # Create user
    user = await crud_user.create_user(
        session=session,
        email=user_data.email,
        username=user_data.username,
        password=user_data.password,
        birth_date=user_data.birth_date,
        avatar_url=user_data.avatar_url,
        is_public=user_data.is_public if hasattr(user_data, 'is_public') else True
    )

    # Générer et envoyer l'email de vérification
    verification_token = EmailVerificationService.generate_token(user)
    await session.commit()
    await session.refresh(user)

    try:
        await send_verification_email(
            email=user.email,
            username=user.username,
            verification_token=verification_token,
            frontend_url=settings.FRONTEND_URL
        )
    except Exception as e:
        print(f"Failed to send verification email: {e}")

    return user


@router.post("/login", response_model=Token)
async def login(
    credentials: LoginRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Login with email/username and password
    
    Returns JWT access token and refresh token
    """
    user = await crud_user.authenticate_user(
        session=session,
        identifier=credentials.identifier,
        password=credentials.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Refresh access token using refresh token
    """
    try:
        payload = decode_token(token_data.refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        from uuid import UUID
        user = await crud_user.get_user_by_id(session, UUID(user_id))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new tokens
        access_token = create_access_token(data={"sub": user_id})
        new_refresh_token = create_refresh_token(data={"sub": user_id})
        
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        )
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


@router.post("/password-reset/request", response_model=PasswordResetResponse)
async def request_password_reset(
        request_data: PasswordResetRequest,
        session: AsyncSession = Depends(get_session)
):
    """
    Demande de réinitialisation de mot de passe

    - Vérifie que l'email existe et est vérifié
    - Génère un token de réinitialisation
    - Envoie un email avec le lien de réinitialisation
    """
    user = await crud_user.get_user_by_email(session, request_data.email)

    # ⚠️ Pour la sécurité, on ne révèle pas si l'email existe ou non
    if not user:
        return PasswordResetResponse(
            message="Si cet email existe et est vérifié, vous recevrez un lien de réinitialisation."
        )

    # Vérifier que l'email est vérifié
    if not user.email_verified:
        return PasswordResetResponse(
            message="Si cet email existe et est vérifié, vous recevrez un lien de réinitialisation."
        )

    # Vérifier le cooldown anti-spam
    if not PasswordResetService.can_request_new_token(user, cooldown_minutes=5):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Veuillez attendre 5 minutes avant de demander un nouveau lien."
        )

    # Générer le token
    reset_token = PasswordResetService.generate_token(user)
    await session.commit()

    # Envoyer l'email
    try:
        await send_password_reset_email(
            email=user.email,
            username=user.username,
            reset_token=reset_token,
            frontend_url=settings.FRONTEND_URL
        )
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")

    return PasswordResetResponse(
        message="Si cet email existe et est vérifié, vous recevrez un lien de réinitialisation."
    )


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
async def confirm_password_reset(
        confirm_data: PasswordResetConfirm,
        session: AsyncSession = Depends(get_session)
):
    """
    Confirme la réinitialisation et définit le nouveau mot de passe

    - Vérifie la validité du token
    - Met à jour le mot de passe
    - Invalide le token
    """
    user = await crud_user.get_user_by_password_reset_token(
        session,
        confirm_data.token
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token invalide ou expiré."
        )

    if not PasswordResetService.is_token_valid(user, confirm_data.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token invalide ou expiré."
        )

    # Mettre à jour le mot de passe
    user.hashed_password = get_password_hash(confirm_data.new_password)

    # Nettoyer le token
    PasswordResetService.clear_token(user)

    await session.commit()

    return PasswordResetResponse(
        message="Votre mot de passe a été réinitialisé avec succès."
    )


@router.get("/password-reset/verify/{token}", response_model=PasswordResetResponse)
async def verify_reset_token(
        token: str,
        session: AsyncSession = Depends(get_session)
):
    """
    Vérifie si un token de réinitialisation est valide
    (utilisé par le frontend avant d'afficher le formulaire)
    """
    user = await crud_user.get_user_by_password_reset_token(session, token)

    if not user or not PasswordResetService.is_token_valid(user, token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token invalide ou expiré."
        )

    return PasswordResetResponse(
        message="Token valide."
    )

@router.get("/debug/frontend-url")
async def debug_frontend_url():
    """Endpoint de debug pour vérifier FRONTEND_URL"""
    return {
        "frontend_url_from_settings": settings.FRONTEND_URL,
        "frontend_url_from_env": os.getenv("FRONTEND_URL", "NOT_SET"),
        "all_settings": {
            "FRONTEND_URL": settings.FRONTEND_URL,
        }
    }