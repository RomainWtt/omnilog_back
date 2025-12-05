"""
OAuth Pydantic Schemas
"""
from typing import Optional

from pydantic import BaseModel, EmailStr


class OAuthUserInfo(BaseModel):
    """Information utilisateur récupérée depuis Google"""
    email: EmailStr
    name: Optional[str]  = None
    picture: Optional[str] = None
    email_verified: bool = False


class OAuthCallbackRequest(BaseModel):
    """Request body pour le callback OAuth"""
    code: str
    state: Optional[str] = None