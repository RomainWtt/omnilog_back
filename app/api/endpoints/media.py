from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.schemas.genre import GenreRead
from app.schemas.media import (
    MediaRead,
    MediaCreate,
    UserMediaEntryCreate,
    UserMediaEntryUpdate,
    UserMediaEntryRead,
    UserMediaEntryWithMedia,
    ProgressUpdate
)
from app.db.models import MediaType, ListStatus, User, Media
from app.crud import crud_media, crud_genre
from app.core.deps import get_current_active_user, get_optional_current_user
from app.services.tmdb_service import tmdb_service
from app.services.redis_service import redis_service
from datetime import datetime

router = APIRouter()


@router.get("/search", response_model=dict)
async def search_media(
        query: str = Query(..., min_length=1, description="Search query"),
        media_type: Optional[MediaType] = Query(None, description="Filter by media type (movie or tv)"),
        page: int = Query(1, ge=1, description="Page number"),
        session: AsyncSession = Depends(get_session),
):
    """
    Search for media (movies and TV shows) by title
    
    First checks local database, then queries TMDB API and stores results
    """
    # Search local database first
    local_results = await crud_media.search_media_by_title(
        session=session,
        query=query,
        limit=20
    )

    # If we have local results, return them
    if local_results:
        return {
            "results": [MediaRead.model_validate(media) for media in local_results],
            "page": page,
            "source": "local"
        }

    # Otherwise, search TMDB
    try:
        if media_type == MediaType.MOVIE:
            tmdb_results = await tmdb_service.search_movie(query, page)
        elif media_type == MediaType.TV:
            tmdb_results = await tmdb_service.search_tv(query, page)
        else:
            tmdb_results = await tmdb_service.search_multi(query, page)

        # Store results in database
        stored_media = []
        for item in tmdb_results.get("results", []):
            media_type_value = item.get("media_type")
            if not media_type_value:
                # Determine from endpoint used
                if "title" in item:
                    media_type_value = "movie"
                elif "name" in item:
                    media_type_value = "tv"
                else:
                    continue

            # Check if media already exists
            existing_media = await crud_media.get_media_by_tmdb_id(
                session=session,
                tmdb_id=item["id"],
                media_type=MediaType(media_type_value)
            )

            if not existing_media:
                # Create media entry
                # Parse date string to date object
                release_date_str = item.get("release_date") or item.get("first_air_date")
                release_date = None
                if release_date_str:
                    try:
                        from datetime import datetime
                        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        release_date = None

                media_data = {
                    "tmdb_id": item["id"],
                    "media_type": MediaType(media_type_value),
                    "title": item.get("title") or item.get("name"),
                    "original_title": item.get("original_title") or item.get("original_name"),
                    "overview": item.get("overview"),
                    "poster_path": item.get("poster_path"),
                    "backdrop_path": item.get("backdrop_path"),
                    "release_date": release_date,
                    "popularity": item.get("popularity"),
                    "vote_average": item.get("vote_average"),
                    "vote_count": item.get("vote_count"),
                    "original_language": item.get("original_language")
                }

                media = await crud_media.create_media(session=session, **media_data)
                stored_media.append(media)
            else:
                stored_media.append(existing_media)

        return {
            "results": [MediaRead.model_validate(media) for media in stored_media],
            "page": tmdb_results.get("page", page),
            "total_pages": tmdb_results.get("total_pages", 1),
            "total_results": tmdb_results.get("total_results", len(stored_media)),
            "source": "tmdb"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching media: {str(e)}"
        )


@router.get("/{media_id}", response_model=MediaRead)
async def get_media_details(
        media_id: UUID,
        session: AsyncSession = Depends(get_session),
):
    """
    Get detailed information about a specific media item
    """
    media = await crud_media.get_media_by_id(session, media_id)

    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )

    genres = await crud_genre.get_genres_by_ids(
        session,
        media.genre_ids or [],
    )

    # Fetch full details from TMDB if we don't have them
    if not media.runtime and not media.number_of_seasons:
        try:
            if media.media_type == MediaType.MOVIE:
                tmdb_details = await tmdb_service.get_movie_details(media.tmdb_id)
            else:
                tmdb_details = await tmdb_service.get_tv_details(media.tmdb_id)

            # Extract actors (top 5 cast members)
            actors = []
            if "credits" in tmdb_details and "cast" in tmdb_details["credits"]:
                actors = [actor["name"] for actor in tmdb_details["credits"]["cast"][:5]]
            
            # Extract directors (for movies) or creators (for TV)
            directors = []
            if media.media_type == MediaType.MOVIE and "credits" in tmdb_details:
                if "crew" in tmdb_details["credits"]:
                    directors = [
                        crew["name"] for crew in tmdb_details["credits"]["crew"] 
                        if crew.get("job") == "Director"
                    ]
            elif media.media_type == MediaType.TV:
                if "created_by" in tmdb_details:
                    directors = [creator["name"] for creator in tmdb_details["created_by"]]

            # Update media with full details
            update_data = {
                "runtime": tmdb_details.get("runtime"),
                "number_of_seasons": tmdb_details.get("number_of_seasons"),
                "number_of_episodes": tmdb_details.get("number_of_episodes"),
                "episode_run_time": tmdb_details.get("episode_run_time"),
                "genres": [g["name"] for g in tmdb_details.get("genres", [])],
                "production_companies": [pc["name"] for pc in tmdb_details.get("production_companies", [])],
                "actors": actors,
                "directors": directors,
            }

            media = await crud_media.update_media(session, media_id, **update_data)

        except Exception as e:
            # Return what we have if TMDB fetch fails
            pass
    media_dict = media.model_dump()
    media_dict["genres"] = [GenreRead.model_validate(g) for g in genres]
    return media_dict


@router.get("/tmdb/{tmdb_id}", response_model=MediaRead)
async def get_media_by_tmdb_id(
        tmdb_id: int,
        media_type: MediaType = Query(..., description="Media type (movie or tv)"),
        session: AsyncSession = Depends(get_session),
        current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Get media by TMDB ID, fetch from TMDB if not in database
    """
    # Check if media exists in database
    media = await crud_media.get_media_by_tmdb_id(session, tmdb_id, media_type)

    if media:
        return media

    # Fetch from TMDB and store
    try:
        if media_type == MediaType.MOVIE:
            tmdb_data = await tmdb_service.get_movie_details(tmdb_id)
        else:
            tmdb_data = await tmdb_service.get_tv_details(tmdb_id)

        # Create media entry
        # Parse date string to date object
        release_date_str = tmdb_data.get("release_date") or tmdb_data.get("first_air_date")
        release_date = None
        if release_date_str:
            try:
                from datetime import datetime
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                release_date = None

        # Extract actors (top 5 cast members)
        actors = []
        if "credits" in tmdb_data and "cast" in tmdb_data["credits"]:
            actors = [actor["name"] for actor in tmdb_data["credits"]["cast"][:5]]
        
        # Extract directors (for movies) or creators (for TV)
        directors = []
        if media_type == MediaType.MOVIE and "credits" in tmdb_data:
            if "crew" in tmdb_data["credits"]:
                directors = [
                    crew["name"] for crew in tmdb_data["credits"]["crew"] 
                    if crew.get("job") == "Director"
                ]
        elif media_type == MediaType.TV:
            if "created_by" in tmdb_data:
                directors = [creator["name"] for creator in tmdb_data["created_by"]]

        media_data = {
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "title": tmdb_data.get("title") or tmdb_data.get("name"),
            "original_title": tmdb_data.get("original_title") or tmdb_data.get("original_name"),
            "overview": tmdb_data.get("overview"),
            "poster_path": tmdb_data.get("poster_path"),
            "backdrop_path": tmdb_data.get("backdrop_path"),
            "release_date": release_date,
            "runtime": tmdb_data.get("runtime"),
            "number_of_seasons": tmdb_data.get("number_of_seasons"),
            "number_of_episodes": tmdb_data.get("number_of_episodes"),
            "episode_run_time": tmdb_data.get("episode_run_time"),
            "genres": [g["name"] for g in tmdb_data.get("genres", [])],
            "production_companies": [pc["name"] for pc in tmdb_data.get("production_companies", [])],
            "actors": actors,
            "directors": directors,
            "popularity": tmdb_data.get("popularity"),
            "vote_average": tmdb_data.get("vote_average"),
            "vote_count": tmdb_data.get("vote_count"),
            "original_language": tmdb_data.get("original_language")
        }

        media = await crud_media.create_media(session=session, **media_data)
        return media

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching media: {str(e)}"
        )


@router.get("/top/movies", response_model=dict)
async def get_top_movies(
        page: int = Query(1, ge=1, le=10),
        session: AsyncSession = Depends(get_session)
):
    """
    Get top rated movies (cached for performance)
    """
    # Check Redis cache
    cached_movies = await redis_service.get_top_movies()

    if cached_movies:
        return {
            "results": cached_movies,
            "page": page,
            "source": "cache"
        }

    # Fetch from TMDB
    try:
        # Fetch multiple pages to get top 500
        all_movies = []
        for p in range(1, 26):  # 25 pages * 20 = 500 movies
            tmdb_results = await tmdb_service.get_top_rated_movies(p)
            all_movies.extend(tmdb_results.get("results", []))

        # Store in Redis
        await redis_service.set_top_movies(all_movies[:500])

        # Return requested page
        start_idx = (page - 1) * 20
        end_idx = start_idx + 20

        return {
            "results": all_movies[start_idx:end_idx],
            "page": page,
            "total_pages": 25,
            "source": "tmdb"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching top movies: {str(e)}"
        )