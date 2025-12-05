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

    @staticmethod
    def normalize_media_item(item: dict, media_type: str) -> dict:
        """
        Normalize TMDB movie/TV show data to a consistent format.
        This ensures both movies and TV shows have the same field names.
        """
        normalized = item.copy()

        # Normalize title field
        if media_type == "tv":
            normalized["title"] = item.get("name", "")
            normalized["original_title"] = item.get("original_name", "")
        else:
            normalized["title"] = item.get("title", "")
            normalized["original_title"] = item.get("original_title", "")

        # Normalize release date
        if media_type == "tv":
            normalized["release_date"] = item.get("first_air_date", "")
        else:
            normalized["release_date"] = item.get("release_date", "")

        # Add media_type if not present
        if "media_type" not in normalized:
            normalized["media_type"] = media_type

        return normalized

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
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "movie") for item in data["results"]]
            return data

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
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "tv") for item in data["results"]]
            return data

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
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "movie") for item in data["results"]]
            return data

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
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "tv") for item in data["results"]]
            return data

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
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "movie") for item in data["results"]]
            return data

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
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "tv") for item in data["results"]]
            return data

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
                return {"results": []}
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "movie") for item in data["results"]]
            return data

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
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "tv") for item in data["results"]]
            return data

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
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "movie") for item in data["results"]]
            return data

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
            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, "tv") for item in data["results"]]
            return data

    async def discover_media(
            self,
            media_type: str,
            page: int = 1,
            sort_by: str = "vote_average.desc",
            **filters
    ) -> dict[str, Any]:
        """
        Generic discover endpoint with flexible filtering

        Args:
            media_type: "movie" or "tv"
            page: Page number
            sort_by: Sort order (default: vote_average.desc)
            **filters: Additional TMDB discover filters:
                - with_genres: Comma-separated genre IDs
                - primary_release_date.gte/lte: Date range for movies (YYYY-MM-DD)
                - first_air_date.gte/lte: Date range for TV shows (YYYY-MM-DD)
                - vote_average.gte/lte: Rating range
                - with_runtime.gte/lte: Runtime range (movies only)
                - vote_count.gte: Minimum number of votes
        """
        async with httpx.AsyncClient() as client:
            # Build params
            params = {
                "sort_by": sort_by,
                "vote_count.gte": 100,  # Default minimum votes for quality
                "page": page,
                "language": "en-US",
            }

            # Add all provided filters
            params.update(filters)

            # Make request
            endpoint = f"{self.base_url}/discover/{media_type}"
            response = await client.get(
                endpoint,
                headers=self.headers,
                params=params
            )

            if response.status_code != 200:
                print(f"TMDB API error for discover {media_type}, page {page}: {response.status_code}")
                print(f"Params: {params}")
                print(f"Response: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )

            data = response.json()
            # Normalize results
            if "results" in data:
                data["results"] = [self.normalize_media_item(item, media_type) for item in data["results"]]
            return data

    async def get_movie_genres(self, language: str = "en-US") -> dict[str, Any]:
        """Get the list of official movie genres"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/genre/movie/list",
                headers=self.headers,
                params={"language": language}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()

    async def get_tv_genres(self, language: str = "en-US") -> dict[str, Any]:
        """Get the list of official TV genres"""

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/genre/tv/list",
                headers=self.headers,
                params={"language": language}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()

    async def get_tv_season(self, tmdb_id: int, season_number: int) -> dict[str, Any]:
        """Get detailed information about a specific TV season"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tv/{tmdb_id}/season/{season_number}",
                headers=self.headers,
                params={"language": "en-US"}
            )
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Season not found"
                )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="TMDB API is unavailable"
                )
            return response.json()

tmdb_service = TMDBService()