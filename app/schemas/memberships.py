from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

class MembershipRead(BaseModel):
    id: UUID
    username: str
    avatar_url: Optional[str] = None
    is_admin: bool
    progress: int
    rank: Optional[int] = None
    # completed_media : Optional[int] = None
    joined_at: datetime

    class Config:
        from_attributes = True