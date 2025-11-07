from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional
from datetime import date, datetime
from app.db.models import MediaType, ListStatus


class MediaBase(BaseModel):
    tmdb_id: int
    media_type: MediaType
    title: str
    

class MediaCreate(MediaBase):
    original_title: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_date: Optional[date] = None
    runtime: Optional[int] = None
    number_of_seasons: Optional[int] = None
    number_of_episodes: Optional[int] = None
    episode_run_time: Optional[list[int]] = None
    genres: Optional[list[str]] = None
    production_companies: Optional[list[str]] = None
    original_language: Optional[str] = None
    popularity: Optional[float] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None


class MediaRead(MediaBase):
    id: UUID
    original_title: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_date: Optional[date] = None
    runtime: Optional[int] = None
    number_of_seasons: Optional[int] = None
    number_of_episodes: Optional[int] = None
    episode_run_time: Optional[list[int]] = None
    genres: Optional[list[str]] = None
    production_companies: Optional[list[str]] = None
    original_language: Optional[str] = None
    popularity: Optional[float] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MediaSearch(BaseModel):
    """Media search result"""
    results: list[MediaRead]
    total_results: int
    page: int
    total_pages: int


class UserMediaEntryBase(BaseModel):
    list_status: ListStatus = ListStatus.PLAN_TO_WATCH


class UserMediaEntryCreate(UserMediaEntryBase):
    media_id: UUID
    progress: int = 0
    current_season: Optional[int] = None
    current_episode: Optional[int] = None
    timecode: int = 0
    score: Optional[int] = Field(None, ge=0, le=10)
    is_favorite: bool = False


class UserMediaEntryUpdate(BaseModel):
    list_status: Optional[ListStatus] = None
    progress: Optional[int] = None
    current_season: Optional[int] = None
    current_episode: Optional[int] = None
    timecode: Optional[int] = None
    score: Optional[int] = Field(None, ge=0, le=10)
    is_favorite: Optional[bool] = None


class UserMediaEntryRead(UserMediaEntryBase):
    user_id: UUID
    media_id: UUID
    progress: int
    current_season: Optional[int]
    current_episode: Optional[int]
    timecode: int
    score: Optional[int]
    is_favorite: bool
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserMediaEntryWithMedia(UserMediaEntryRead):
    """User media entry with full media details"""
    media: MediaRead
    
    class Config:
        from_attributes = True


class ProgressUpdate(BaseModel):
    """Update progress for a media item"""
    progress: int = Field(..., ge=0)
    current_season: Optional[int] = Field(None, ge=1)
    current_episode: Optional[int] = Field(None, ge=1)
    timecode: int = Field(0, ge=0)  # in seconds


class MediaFilter(BaseModel):
    """Filters for media search"""
    media_type: Optional[MediaType] = None
    genre: Optional[str] = None
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_rating: Optional[float] = Field(None, ge=0, le=10)
    sort_by: Optional[str] = "popularity"  # popularity, rating, release_date, title
    sort_order: Optional[str] = "desc"  # asc, desc
