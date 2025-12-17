# app/services/password_reset.py
from datetime import datetime, timedelta
from typing import Optional
import secrets

from app.db.models import User


class PasswordResetService:
    """Service pour gérer la réinitialisation de mot de passe"""

    DEFAULT_EXPIRATION_HOURS = 1  # 1 heure pour plus de sécurité
    TOKEN_LENGTH = 32

    @staticmethod
    def generate_token(user: User, expiration_hours: int = DEFAULT_EXPIRATION_HOURS) -> str:
        """
        Génère un token de réinitialisation pour l'utilisateur

        Args:
            user: L'utilisateur pour qui générer le token
            expiration_hours: Durée de validité du token en heures

        Returns:
            Le token généré
        """
        user.password_reset_token = secrets.token_urlsafe(
            PasswordResetService.TOKEN_LENGTH
        )
        user.password_reset_token_expires = (
            datetime.utcnow() + timedelta(hours=expiration_hours)
        )
        return user.password_reset_token

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
        if not user.password_reset_token or not user.password_reset_token_expires:
            return False

        is_matching = user.password_reset_token == token
        is_not_expired = datetime.utcnow() < user.password_reset_token_expires

        return is_matching and is_not_expired

    @staticmethod
    def clear_token(user: User) -> None:
        """
        Nettoie le token après utilisation

        Args:
            user: L'utilisateur
        """
        user.password_reset_token = None
        user.password_reset_token_expires = None

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
        if not user.password_reset_token_expires:
            return True

        # Calculer le temps écoulé depuis la dernière génération
        time_since_last = datetime.utcnow() - (
            user.password_reset_token_expires - timedelta(hours=PasswordResetService.DEFAULT_EXPIRATION_HOURS)
        )

        return time_since_last.total_seconds() > (cooldown_minutes * 60)