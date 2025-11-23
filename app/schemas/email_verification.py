# app/schemas/email_verification.py
from pydantic import BaseModel

class EmailVerificationResponse(BaseModel):
    """Response après envoi d'email de vérification"""
    message: str
    email: str

class EmailVerificationConfirm(BaseModel):
    """Confirmer la vérification d'email avec token"""
    token: str

class EmailVerificationSuccess(BaseModel):
    """Response après vérification réussie"""
    message: str
    email: str

class ResendVerificationRequest(BaseModel):
    """Request pour renvoyer l'email de vérification"""
    email: str

class ResendVerificationResponse(BaseModel):
    """Response après demande de renvoi"""
    message: str