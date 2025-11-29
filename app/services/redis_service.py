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
        """Cache top movies with media_type field (24 hour TTL by default)"""
        # Ensure each movie has media_type
        for movie in movies:
            if "media_type" not in movie:
                movie["media_type"] = "movie"
        return await self.set("top_movies", movies, ttl)
    
    async def clear_top_movies(self) -> bool:
        """Clear top movies cache"""
        return await self.delete("top_movies")
    
    async def get_top_tv(self) -> Optional[list[dict]]:
        """Get cached top TV shows"""
        return await self.get("top_tv")
    
    async def set_top_tv(self, shows: list[dict], ttl: int = 86400) -> bool:
        """Cache top TV shows with media_type field (24 hour TTL by default)"""
        # Ensure each show has media_type
        for show in shows:
            if "media_type" not in show:
                show["media_type"] = "tv"
        return await self.set("top_tv", shows, ttl)
    
    async def clear_top_tv(self) -> bool:
        """Clear top TV cache"""
        return await self.delete("top_tv")
    
    async def get_top_media(self) -> Optional[list[dict]]:
        """Get cached combined top media (movies + TV)"""
        return await self.get("top_media")
    
    async def set_top_media(self, media: list[dict], ttl: int = 86400) -> bool:
        """Cache combined top media (24 hour TTL by default)"""
        return await self.set("top_media", media, ttl)
    
    async def clear_top_media(self) -> bool:
        """Clear combined top media cache"""
        return await self.delete("top_media")


    async def get_genre_media(self, genre_id: int, media_type: str = "all") -> Optional[list[dict]]:
        """Get cached media for a specific genre"""
        key = f"genre_{genre_id}_{media_type}"
        return await self.get(key)


    async def set_genre_media(self, genre_id: int, media: list[dict], media_type: str = "all", ttl: int = 86400) -> bool:
        """Cache media for a specific genre (24 hour TTL by default)"""
        key = f"genre_{genre_id}_{media_type}"
        # Ensure each item has media_type
        for item in media:
            if "media_type" not in item:
                item["media_type"] = media_type if media_type in ["movie", "tv"] else "movie"
        return await self.set(key, media, ttl)


    async def clear_genre_cache(self, genre_id: int) -> bool:
        """Clear cache for a specific genre (all media types)"""
        if not self._client:
            await self.connect()

        # Delete all variations (all, movie, tv)
        keys = [
            f"genre_{genre_id}_all",
            f"genre_{genre_id}_movie",
            f"genre_{genre_id}_tv"
        ]
        deleted = 0
        for key in keys:
            deleted += await self._client.delete(key)
        return deleted > 0

redis_service = RedisService()