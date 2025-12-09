from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

class MembershipCreate(BaseModel):
    username: str
    avatar_url: Optional[str] = None
    episode_number: int
    total_episodes: int

class MembershipRead(BaseModel):
    id: UUID
    challenge_id: UUID
    username: str
    avatar_url: str | None
    is_admin: bool
    #progress: int = 0
    #rank: int | None = None
    joined_at: datetime

    class Config:
        from_attributes = True

class RankingMembership(BaseModel):
    id: UUID
    username: str
    avatar_url: Optional[str] = None
    completed_count: int
    total_media_count: int
    progress: int = 0
    rank: Optional[int] = None

    class Config:
        from_attributes = True

