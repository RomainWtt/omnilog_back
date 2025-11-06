import json
from typing import Optional, Any
import redis.asyncio as redis
from app.core.config import settings


class RedisService:
    """Service for Redis caching operations"""
    
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.default_ttl = settings.REDIS_CACHE_TTL
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Initialize Redis connection"""
        if not self._client:
            self._client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._client:
            await self.connect()
        
        value = await self._client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        if not self._client:
            await self.connect()
        
        if ttl is None:
            ttl = self.default_ttl
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        return await self._client.setex(key, ttl, value)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self._client:
            await self.connect()
        
        return await self._client.delete(key) > 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self._client:
            await self.connect()
        
        return await self._client.exists(key) > 0
    
    async def get_top_movies(self) -> Optional[list[dict]]:
        """Get cached top movies"""
        return await self.get("top_movies")
    
    async def set_top_movies(self, movies: list[dict], ttl: int = 86400) -> bool:
        """Cache top movies (24 hour TTL by default)"""
        return await self.set("top_movies", movies, ttl)
    
    async def clear_top_movies(self) -> bool:
        """Clear top movies cache"""
        return await self.delete("top_movies")


redis_service = RedisService()
