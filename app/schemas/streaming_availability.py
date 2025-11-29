# app/schemas/streaming.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class StreamLink(BaseModel):
    """Représente un lien vers une plateforme de streaming."""
    service: str  # e.g., "Netflix", "Amazon Prime Video"
    type: str     # e.g., "subscription", "buy", "rent"
    link: str     # L'URL profonde
    price: Optional[float] = None # Prix pour l'achat/location

class StreamingAvailabilityRead(BaseModel):
    """Structure de la réponse pour la disponibilité en streaming."""
    tmdb_id: int
    country: str
    is_available: bool
    streaming_links: Dict[str, List[StreamLink]] # {'subscription': [...], 'buy': [...], ...}