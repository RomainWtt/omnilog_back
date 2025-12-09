import time
from typing import Optional
from datetime import datetime, timedelta
from app.core.config import settings
from google.genai import Client
from google.genai.types import GenerateContentConfig

# Instruction système pour forcer le modèle à agir comme un modérateur strict avec contexte
SYSTEM_INSTRUCTION = (
    "Votre tâche est de déterminer si un commentaire est offensant, haineux, "
    "sexuellement explicite, illégal, ou harcelant. "
    "IMPORTANT : Vous recevrez le synopsis du média commenté pour comprendre le contexte. "
    "Un commentaire parlant du sujet du média (handicap, violence, etc.) de manière "
    "descriptive ou critique constructive N'EST PAS offensant. "
    "Répondez UNIQUEMENT par 'OUI' si le commentaire est inapproprié, sinon répondez 'NON'."
)


class GoogleIAService:
    MODEL = 'gemini-2.5-flash'

    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
        self.google = Client(api_key=self.api_key)

        # Rate limiting: mémoriser le dernier appel
        self.last_call_time: Optional[datetime] = None
        self.min_delay_seconds = 2  # Minimum 2 secondes entre chaque appel
        self.retry_after: Optional[float] = None

    def _wait_if_needed(self):
        """Attend si nécessaire pour respecter le rate limiting."""
        if self.retry_after:
            # Si on a un retry_after d'une précédente erreur 429
            wait_time = self.retry_after - time.time()
            if wait_time > 0:
                print(f"⏳ Attente de {wait_time:.1f}s avant de réessayer...")
                time.sleep(wait_time)
            self.retry_after = None

        if self.last_call_time:
            elapsed = (datetime.now() - self.last_call_time).total_seconds()
            if elapsed < self.min_delay_seconds:
                wait_time = self.min_delay_seconds - elapsed
                print(f"⏳ Rate limiting: attente de {wait_time:.1f}s...")
                time.sleep(wait_time)

    def check_comment(self, comments: str, synopsis: str) -> bool:
        """
        Demande à Gemini de vérifier le commentaire reçu en paramètre avec le contexte du synopsis.
        :param comments: le commentaire à checker
        :param synopsis: le synopsis du média pour donner du contexte
        :return: True si le commentaire est inadapté, sinon False
        """
        # Liste de mots-clés offensants pour une détection locale rapide (fallback)
        OFFENSIVE_KEYWORDS = [
            # Français
            'pute', 'connard', 'salope', 'enculé', 'merde', 'chier',
            'con', 'débile', 'idiot', 'crétin', 'abruti', 'batard',
            'fils de', 'ta mère', 'nique', 'ta race', 'fdp',
            # Anglais
            'fuck', 'shit', 'bitch', 'asshole', 'bastard', 'cunt',
            'dick', 'pussy', 'damn', 'hell', 'motherfucker'
        ]

        # 1. Détection locale AVANT d'appeler l'API (économise le quota)
        comments_lower = comments.lower()
        for keyword in OFFENSIVE_KEYWORDS:
            if keyword in comments_lower:
                print(f"🚨 Commentaire BLOQUÉ par détection locale (mot-clé: '{keyword}').")
                return True

        # 2. Si pas de détection locale, appeler l'API Gemini avec le contexte
        CLASSIFICATION_PROMPT = f"""SYNOPSIS DU MÉDIA : {synopsis}
        COMMENTAIRE À ANALYSER : {comments}
        Analysez si ce commentaire est inapproprié en tenant compte du contexte du média."""

        try:
            # Respecter le rate limiting
            self._wait_if_needed()

            response = self.google.models.generate_content(
                model=self.MODEL,
                contents=CLASSIFICATION_PROMPT,
                config=GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION
                )
            )

            # Mémoriser le temps du dernier appel réussi
            self.last_call_time = datetime.now()

            # Vérification sécurisée du prompt_feedback
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback is not None:
                block_reason = getattr(response.prompt_feedback, 'block_reason', None)
                if block_reason:
                    print(f"🚨 Commentaire BLOQUÉ par les filtres de sécurité (raison: {block_reason}).")
                    return True

            # Vérification de la présence du texte de réponse
            if not hasattr(response, 'text') or not response.text:
                print("⚠️ Aucune réponse textuelle du modèle. Blocage par prudence.")
                return True

            # Analyse de la réponse textuelle explicite du modèle
            classification = response.text.strip().upper()

            if "OUI" in classification:
                print(f"🚨 Commentaire BLOQUÉ par la classification du modèle (Réponse: {classification}).")
                return True

            print(f"✅ Commentaire JUGÉ SÛR (Réponse: {classification}).")
            return False

        except Exception as e:
            error_str = str(e)

            # Gestion spécifique de l'erreur 429 (quota dépassé)
            if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                print(f"⚠️ Quota API dépassé. Utilisation du filtre local uniquement.")

                # Extraire le retry_after si disponible
                if 'retry in' in error_str.lower():
                    try:
                        # Exemple: "Please retry in 37.344162651s"
                        import re
                        match = re.search(r'retry in (\d+\.?\d*)s', error_str)
                        if match:
                            retry_seconds = float(match.group(1))
                            self.retry_after = time.time() + retry_seconds
                            print(f"⏳ Réessai possible dans {retry_seconds:.1f}s")
                    except:
                        pass

                # En cas de quota dépassé, on se rabat sur la détection locale
                # qui a déjà été faite au début. Si rien n'a été détecté localement,
                # on laisse passer par sécurité (ou bloquer selon votre politique)
                print("ℹ️ Commentaire jugé SÛR par détection locale (API indisponible).")
                return False

            print(f"⚠️ Erreur critique lors de l'appel à l'API Gemini: {e}")
            # En cas d'erreur inconnue, bloquer par prudence
            return True


# Initialisation du service
google_service = GoogleIAService()
