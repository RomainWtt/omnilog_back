import httpx
from typing import Optional, Any
from app.core.config import settings
from fastapi import HTTPException, status


class TMDBService:
    """Service for interacting with TMDB API"""
    
    def __init__(self):
        self.api_key = settings.TMDB_API_KEY
        self.base_url = settings.TMDB_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def search_movie(self, query: str, page: int = 1) -> dict[str, Any]:
        """Search for movies by title"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/search/movie",
                headers=self.headers,
                params={"query": query, "page": page, "language": "en-US"}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()
    
    async def search_tv(self, query: str, page: int = 1) -> dict[str, Any]:
        """Search for TV shows by title"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/search/tv",
                headers=self.headers,
                params={"query": query, "page": page, "language": "en-US"}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()
    
    async def search_multi(self, query: str, page: int = 1) -> dict[str, Any]:
        """Search for movies and TV shows"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/search/multi",
                headers=self.headers,
                params={"query": query, "page": page, "language": "en-US"}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()
    
    async def get_movie_details(self, tmdb_id: int) -> dict[str, Any]:
        """Get detailed information about a movie"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/movie/{tmdb_id}",
                headers=self.headers,
                params={"language": "en-US", "append_to_response": "credits,videos"}
            )
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Movie not found"
                )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()
    
    async def get_tv_details(self, tmdb_id: int) -> dict[str, Any]:
        """Get detailed information about a TV show"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tv/{tmdb_id}",
                headers=self.headers,
                params={"language": "en-US", "append_to_response": "credits,videos"}
            )
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="TV show not found"
                )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()
    
    async def get_top_rated_movies(self, page: int = 1) -> dict[str, Any]:
        """Get top rated movies"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/movie/top_rated",
                headers=self.headers,
                params={"page": page, "language": "en-US"}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()
    
    async def get_top_rated_tv(self, page: int = 1) -> dict[str, Any]:
        """Get top rated TV shows"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tv/top_rated",
                headers=self.headers,
                params={"page": page, "language": "en-US"}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()
    
    async def get_popular_movies(self, page: int = 1) -> dict[str, Any]:
        """Get popular movies"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/movie/popular",
                headers=self.headers,
                params={"page": page, "language": "en-US"}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()
    
    async def get_popular_tv(self, page: int = 1) -> dict[str, Any]:
        """Get popular TV shows"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tv/popular",
                headers=self.headers,
                params={"page": page, "language": "en-US"}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()
    
    def get_image_url(self, path: str, size: str = "original") -> str:
        """Get full image URL from TMDB image path"""
        if not path:
            return ""
        return f"{settings.TMDB_IMAGE_BASE_URL}/{size}{path}"

    async def get_movie_similar(self, tmdb_id: int, page: int = 1) -> dict[str, Any]:
        """Get similar movies from TMDB"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/movie/{tmdb_id}/similar",
                headers=self.headers,
                params={"page": page, "language": "en-US"}
            )
            if response.status_code != 200:
                # On ne lève pas d'erreur ici pour ne pas bloquer tout l'algo si un film échoue
                return {"results": []}
            return response.json()

    async def get_tv_similar(self, tmdb_id: int, page: int = 1) -> dict[str, Any]:
        """Get similar TV shows from TMDB"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tv/{tmdb_id}/similar",
                headers=self.headers,
                params={"page": page, "language": "en-US"}
            )
            if response.status_code != 200:
                return {"results": []}
            return response.json()
    async def discover_movies_by_genre(
        self,
        genre_id: int,
        page: int = 1,
        sort_by: str = "vote_average.desc"
    ) -> dict[str, Any]:
        """Discover movies by genre, sorted by rating"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/discover/movie",
                headers=self.headers,
                params={
                    "with_genres": genre_id,
                    "sort_by": sort_by,
                    "vote_count.gte": 100,
                    "page": page,
                    "language": "en-US"
                }
            )
            if response.status_code != 200:
                print(f"TMDB API error for genre {genre_id}, page {page}: {response.status_code}")
                print(f"Response: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()

    async def discover_tv_by_genre(
        self,
        genre_id: int,
        page: int = 1,
        sort_by: str = "vote_average.desc"
    ) -> dict[str, Any]:
        """Discover TV shows by genre, sorted by rating"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/discover/tv",
                headers=self.headers,
                params={
                    "with_genres": genre_id,
                    "sort_by": sort_by,
                    "vote_count.gte": 100,
                    "page": page,
                    "language": "en-US"
                }
            )
            if response.status_code != 200:
                print(f"TMDB API error for TV genre {genre_id}, page {page}: {response.status_code}")
                print(f"Response: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()

tmdb_service = TMDBService()