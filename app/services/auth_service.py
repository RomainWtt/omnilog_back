#TODO:Placeholder, il faut implementer OAuth correctement

#La marche a suivre:
#1. Exchange code for access token
#2. Get user info from Google API
#3. Create or update user in database
#4. Return user data

from typing import Optional
from app.core.config import settings


class OAuthService:
    """Service for handling OAuth authentication flows"""
    
    async def google_auth(self, code: str, redirect_uri: str) -> dict:
        """
        Exchange Google authorization code for user info
        """
        raise NotImplementedError("Google OAuth not yet implemented")
    
    async def facebook_auth(self, code: str, redirect_uri: str) -> dict:
        """Exchange Facebook authorization code for user info"""
        raise NotImplementedError("Facebook OAuth not yet implemented")
    
    async def apple_auth(self, code: str, redirect_uri: str) -> dict:
        """Exchange Apple authorization code for user info"""
        raise NotImplementedError("Apple OAuth not yet implemented")


oauth_service = OAuthService()