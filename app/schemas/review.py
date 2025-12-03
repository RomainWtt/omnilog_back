"""
Pydantic schemas for reviews/comments
"""
from pydantic import BaseModel, Field
from app.schemas.media import MediaBasic
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from app.schemas.user import UserPublic
from pydantic import field_validator


class ReviewBase(BaseModel):
    """Base review schema"""
    content: Optional[str] = Field(None, max_length=5000)
    rating: int = Field(..., ge=1, le=5)
    is_visible: bool = True


class ReviewCreate(BaseModel):
    """Schema for creating a review"""
    media_id: UUID
    content: Optional[str] = Field(None, max_length=5000)
    rating: int = Field(..., ge=1, le=5)


class ReviewUpdate(BaseModel):
    """Schema for updating a review"""
    content: Optional[str] = Field(None, max_length=5000)
    rating: Optional[int] = Field(None, ge=1, le=5)


class ReviewRead(ReviewBase):
    """Schema for reading a review"""
    id: UUID
    user_id: UUID
    media_id: UUID
    created_at: datetime
    updated_at: datetime
    user: UserPublic
    is_friend: Optional[bool] = None
    is_reported: Optional[bool] = None
    media: Optional[MediaBasic]

    @field_validator("is_reported", mode="before")
    def compute_is_reported(cls, v, values):
        obj = values.get("__object__")
        if obj and hasattr(obj, "reports"):
            return len(obj.reports) > 0
        return False

    class Config:
        from_attributes = True


class ReviewsPaginated(BaseModel):
    """Paginated reviews response"""
    results: List[ReviewRead]
    page: int
    total: int
    pages: int
    source: str


class MediaAverageRating(BaseModel):
    """Average rating for a media"""
    media_id: UUID
    average_rating: Optional[float] = None
    average_rating_friend: Optional[float] = None
    total_ratings: int
