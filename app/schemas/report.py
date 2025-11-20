from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class ReviewReportCreate(BaseModel):
    review_id: UUID
    reason: str = Field(..., min_length=10, max_length=1000)

class ReviewReportRead(BaseModel):
    id: UUID
    reporter_id: UUID
    reported_user_id: UUID
    review_id: UUID
    review_content: Optional[str]
    reason: str
    created_at: datetime

    class Config:
        orm_mode = True
