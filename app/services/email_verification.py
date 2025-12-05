# app/services/email_verification.py
from datetime import datetime, timedelta
from typing import Optional
import secrets

from app.db.models import User


class EmailVerificationService:
    """Service pour gérer la vérification d'email"""

    DEFAULT_EXPIRATION_HOURS = 24
    TOKEN_LENGTH = 32

    @staticmethod
    def generate_token(user: User, expiration_hours: int = DEFAULT_EXPIRATION_HOURS) -> str:
        """
        Génère un token de vérification pour l'utilisateur

        Args:
            user: L'utilisateur pour qui générer le token
            expiration_hours: Durée de validité du token en heures

        Returns:
            Le token généré
        """
        user.email_verification_token = secrets.token_urlsafe(
            EmailVerificationService.TOKEN_LENGTH
        )
        user.email_verification_token_expires = (
                datetime.utcnow() + timedelta(hours=expiration_hours)
        )
        return user.email_verification_token

    @staticmethod
    def is_token_valid(user: User, token: str) -> bool:
        """
        Vérifie si le token est valide et non expiré

        Args:
            user: L'utilisateur à vérifier
            token: Le token à valider

        Returns:
            True si le token est valide, False sinon
        """
        if not user.email_verification_token or not user.email_verification_token_expires:
            return False

        is_matching = user.email_verification_token == token
        is_not_expired = datetime.utcnow() < user.email_verification_token_expires

        return is_matching and is_not_expired

    @staticmethod
    def mark_as_verified(user: User) -> None:
        """
        Marque l'email comme vérifié et nettoie le token

        Args:
            user: L'utilisateur dont l'email est vérifié
        """
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_token_expires = None

    @staticmethod
    def mark_as_verified_by_oauth(user: User, provider: str = "oauth") -> None:
        """
        Marque l'email comme vérifié via OAuth (Google, Facebook, Apple, etc.)

        Args:
            user: L'utilisateur dont l'email est vérifié
            provider: Le fournisseur OAuth (pour les logs)
        """
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_token_expires = None
        print(f"✅ Email vérifié automatiquement via {provider} pour {user.email}")

    @staticmethod
    def can_request_new_token(user: User, cooldown_minutes: int = 5) -> bool:
        """
        Vérifie si l'utilisateur peut demander un nouveau token
        (anti-spam)

        Args:
            user: L'utilisateur
            cooldown_minutes: Temps d'attente entre deux demandes

        Returns:
            True si un nouveau token peut être généré
        """
        if not user.email_verification_token_expires:
            return True

        # Calculer le temps écoulé depuis la dernière génération
        time_since_last = datetime.utcnow() - (
                user.email_verification_token_expires - timedelta(hours=24)
        )

        return time_since_last.total_seconds() > (cooldown_minutes * 60)