# app/schemas/password_reset.py
from pydantic import BaseModel, EmailStr, Field


class PasswordResetRequest(BaseModel):
    """Demande de réinitialisation de mot de passe"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirmation de réinitialisation avec nouveau mot de passe"""
    token: str
    new_password: str = Field(
        ...,
        min_length=8,
        description="Nouveau mot de passe (minimum 8 caractères)"
    )


class PasswordResetResponse(BaseModel):
    """Réponse pour les opérations de réinitialisation"""
    message: str