from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

class ActivityChallenge(BaseModel):
    id: UUID
    type: str

    username: str
    avatar_url: Optional[str] = None
    timestamp: datetime

    episode_number: Optional[int] = None
    total_episodes: Optional[int] = None

    media_title: Optional[str] = None

    class Config:
        from_attributes = True