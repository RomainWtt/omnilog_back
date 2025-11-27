from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.db.models import ChallengeType


class ChallengeBase(BaseModel):
    name:Optional[str] = None
    description: Optional[str] = None
    challenge_type: ChallengeType
    avatar_url: Optional[str] = None

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    media_list: Optional[list[int]] = None


class ChallengeCreate(ChallengeBase):
    pass
    #creator_id: UUID


class ChallengeRead(ChallengeBase):
    id: UUID
    creator_id: UUID
    created_at: datetime
    updated_at: datetime
    #participants_count: Optional[int] = 0

    class Config:
        from_attributes = True


#class MembersChallenge(ChallengeRead) :
#    participants_count: Optional[int] = 0
#    memberships: list[UserPublic] = []