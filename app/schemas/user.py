from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str
    avatar_url: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    avatar_url: Optional[str] = None

class UserRead(UserBase):
    id: UUID
    avatar_url: Optional[str] = None
    
    class Config:
        from_attributes = True