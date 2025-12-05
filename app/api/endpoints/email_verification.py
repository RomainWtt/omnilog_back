# app/api/v1/endpoints/email_verification.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas.email_verification import (
    EmailVerificationResponse,
    EmailVerificationConfirm,
    EmailVerificationSuccess,
    ResendVerificationRequest,
    ResendVerificationResponse
)
from app.crud import crud_user
from app.core.email import send_verification_email
import os

from app.services.email_verification import EmailVerificationService

router = APIRouter()

FRONTEND_URL = settings.FRONTEND_URL


@router.post("/send-verification", response_model=EmailVerificationResponse)
async def send_verification(
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
):
    if current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )

    # Vérifier le cooldown anti-spam
    if not EmailVerificationService.can_request_new_token(current_user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting a new verification email"
        )

    # Générer le token via le service
    token = EmailVerificationService.generate_token(current_user)
    session.add(current_user)
    await session.commit()

    # Envoyer l'email
    await send_verification_email(
        email=current_user.email,
        username=current_user.username,
        verification_token=token,
        frontend_url=FRONTEND_URL
    )

    return EmailVerificationResponse(
        message="Verification email sent successfully",
        email=current_user.email
    )


@router.post("/verify", response_model=EmailVerificationSuccess)
async def verify_email(
        data: EmailVerificationConfirm,
        session: AsyncSession = Depends(get_session)
):
    user = await crud_user.get_user_by_verification_token(session, data.token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )

    # Valider via le service
    if not EmailVerificationService.is_token_valid(user, data.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )

    # Marquer comme vérifié via le service
    EmailVerificationService.mark_as_verified(user)
    session.add(user)
    await session.commit()

    return EmailVerificationSuccess(
        message="Email verified successfully",
        email=user.email
    )

@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    summary="Renvoyer l'email de vérification",
    description="Renvoie un email de vérification (sans authentification requise)"
)
async def resend_verification(
        data: ResendVerificationRequest,
        session: AsyncSession = Depends(get_session)
):
    """Renvoie un email de vérification (sans authentification requise)"""
    user = await crud_user.get_user_by_email(session, data.email)

    if not user:
        # Ne pas révéler si l'email existe pour la sécurité
        return ResendVerificationResponse(
            message="If the email exists, a verification email has been sent"
        )

    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )

    # Générer un nouveau token
    verification_token = user.generate_verification_token()
    session.add(user)
    await session.commit()

    # Envoyer l'email
    await send_verification_email(
        email=user.email,
        username=user.username,
        verification_token=verification_token,
        frontend_url=FRONTEND_URL
    )

    return ResendVerificationResponse(
        message="If the email exists, a verification email has been sent"
    )