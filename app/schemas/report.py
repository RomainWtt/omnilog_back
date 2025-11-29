from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class ReportedReview(BaseModel):
    id: UUID
    content: Optional[str] = None
    rating: Optional[int] = None
    user_id: UUID

    class Config:
        from_attributes = True

class ReviewReportCreate(BaseModel):
    review_id: UUID
    reason: str = Field(..., min_length=10, max_length=1000)


class ReviewReportRead(BaseModel):
    id: UUID
    reporter_id: UUID
    reporter_username: Optional[str] = None
    reported_user_id: UUID
    reported_user_username: Optional[str] = None
    review_id: UUID
    reason: str
    created_at: datetime
    media : Optional[str] = None

    class Config:
        from_attributes = True

"""
class ReviewReportWithReview(ReviewReportRead):
    review: ReportedReview

    class Config:
        from_attributes = True
"""