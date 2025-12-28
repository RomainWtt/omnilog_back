from pydantic import BaseModel, EmailStr, Field, field_validator, validator
from uuid import UUID
from typing import Optional
from datetime import date, datetime


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    birth_date: date  # OBLIGATOIRE maintenant
    is_public: bool = True  # Ajouter ce champ
    avatar_url: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, underscores and hyphens')
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    avatar_url: Optional[str] = None
    birth_date: Optional[date] = None
    social_links: Optional[dict] = None
    current_password: Optional[str] = None
    jellyfin_url: Optional[str] = None
    jellyfin_api_key: Optional[str] = None

class UserRead(UserBase):
    id: UUID
    avatar_url: Optional[str] = None
    birth_date: Optional[date] = None
    is_active: bool
    is_admin: bool
    email_verified: bool
    created_at: datetime
    social_links: Optional[dict] = None

    # NOUVEAUX CHAMPS OAUTH
    google_id: Optional[str] = None
    facebook_id: Optional[str] = None
    apple_id: Optional[str] = None

    class Config:
        from_attributes = True


class UserPublic(BaseModel):
    """Public user information visible to other users"""
    id: UUID
    username: str
    avatar_url: Optional[str] = None
    social_links: Optional[dict] = None
    is_public: bool
    email_verified: Optional[bool] = None

    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """User statistics"""
    total_media: int
    completed_media: int
    watching_media: int
    total_watch_time: int  # in minutes
    favorite_genres: list[str]

    class Config:
        from_attributes = True