from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.db.models import ChallengeType, MediaType


class ChallengeToMedia(BaseModel):
    tmdb_id: Optional[int] = None
    media_type: MediaType = None


class ChallengeBase(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    challenge_type: Optional[ChallengeType] = None
    avatar_url: Optional[str] = None

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    media_list: Optional[list[ChallengeToMedia]] = None

class ChallengeCreate(ChallengeBase):
    name: str
    challenge_type: ChallengeType

class ChallengeUpdate(ChallengeBase):
    pass

class ChallengeRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    challenge_type: ChallengeType
    avatar_url: Optional[str]

    start_date: Optional[datetime]
    end_date: Optional[datetime]
    media_list: Optional[list[int]]

    creator_id: UUID
    created_at: datetime
    updated_at: datetime
    members_total: int = 0

    average_progress: Optional[float] = None
    personal_progress: Optional[float] = None # voir si on garde

    class Config:
        from_attributes = True