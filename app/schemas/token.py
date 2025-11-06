from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data encoded in JWT token"""
    sub: str  # User ID
    type: str  # "access" or "refresh"


class LoginRequest(BaseModel):
    """Login credentials"""
    identifier: str 
    password: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class OAuthLoginRequest(BaseModel):
    """OAuth login request"""
    provider: str  # google, facebook, apple
    code: str  # Authorization code
    redirect_uri: Optional[str] = None
