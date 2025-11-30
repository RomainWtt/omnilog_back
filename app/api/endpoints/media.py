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
    ProgressUpdate, MediaSearch
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

        print(f"Valeur des genre {tmdb_data.get('genres')}")
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
            "genre_ids": [g["id"] for g in tmdb_data.get("genres", [])],
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
        page: int = Query(1, ge=1, le=25),
        session: AsyncSession = Depends(get_session)
):
    """
    Get top rated movies (cached for performance)
    Each item includes media_type: "movie"
    """
    # Check Redis cache
    cached_movies = await redis_service.get_top_movies()

    if cached_movies:
        # Return requested page from cache
        start_idx = (page - 1) * 20
        end_idx = start_idx + 20
        return {
            "results": cached_movies[start_idx:end_idx],
            "page": page,
            "total_pages": 25,
            "source": "cache"
        }

    # Fetch from TMDB
    try:
        # Fetch multiple pages to get top 500
        all_movies = []
        for p in range(1, 26):  # 25 pages * 20 = 500 movies
            tmdb_results = await tmdb_service.get_top_rated_movies(p)
            for movie in tmdb_results.get("results", []):
                movie["media_type"] = "movie"
            all_movies.extend(tmdb_results.get("results", []))

        # Store in Redis (media_type is added by set_top_movies)
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


@router.get("/top/tv", response_model=dict)
async def get_top_tv(
        page: int = Query(1, ge=1, le=25),
        session: AsyncSession = Depends(get_session)
):
    """
    Get top rated TV shows (cached for performance)
    Each item includes media_type: "tv"
    """
    # Check Redis cache
    cached_tv = await redis_service.get_top_tv()

    if cached_tv:
        start_idx = (page - 1) * 20
        end_idx = start_idx + 20
        return {
            "results": cached_tv[start_idx:end_idx],
            "page": page,
            "total_pages": 25,
            "source": "cache"
        }

    # Fetch from TMDB
    try:
        all_tv = []
        for p in range(1, 26):
            tmdb_results = await tmdb_service.get_top_rated_tv(p)
            for show in tmdb_results.get("results", []):
                show["media_type"] = "tv"  # Add media_type
            all_tv.extend(tmdb_results.get("results", []))

        # Store in Redis
        await redis_service.set_top_tv(all_tv[:500])

        start_idx = (page - 1) * 20
        end_idx = start_idx + 20

        return {
            "results": all_tv[start_idx:end_idx],
            "page": page,
            "total_pages": 25,
            "source": "tmdb"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching top TV shows: {str(e)}"
        )


@router.get("/top/all", response_model=MediaSearch)
async def get_top_media(
        page: int = Query(1, ge=1, le=25),
        session: AsyncSession = Depends(get_session)
):
    """
    Get top rated media (movies + TV combined, sorted by vote_average)
    Returns properly structured MediaRead objects
    """
    # Check Redis cache
    cached_media = await redis_service.get_top_media()

    if cached_media:
        start_idx = (page - 1) * 20
        end_idx = start_idx + 20

        # Convert cached dict to MediaRead objects
        media_objects = [_tmdb_to_media_read(item) for item in cached_media[start_idx:end_idx]]

        return MediaSearch(
            results=media_objects,
            page=page,
            total_pages=25,
            total_results=len(cached_media)
        )

    # Fetch both movies and TV from cache or TMDB
    try:
        # Get movies
        cached_movies = await redis_service.get_top_movies()
        if not cached_movies:
            all_movies = []
            for p in range(1, 26):
                tmdb_results = await tmdb_service.get_top_rated_movies(p)
                for movie in tmdb_results.get("results", []):
                    movie["media_type"] = "movie"
                all_movies.extend(tmdb_results.get("results", []))
            cached_movies = all_movies[:500]
            await redis_service.set_top_movies(cached_movies)

        # Get TV
        cached_tv = await redis_service.get_top_tv()
        if not cached_tv:
            all_tv = []
            for p in range(1, 26):
                tmdb_results = await tmdb_service.get_top_rated_tv(p)
                for show in tmdb_results.get("results", []):
                    show["media_type"] = "tv"
                all_tv.extend(tmdb_results.get("results", []))
            cached_tv = all_tv[:500]
            await redis_service.set_top_tv(cached_tv)

        # Combine and sort by vote_average
        all_media = cached_movies + cached_tv
        all_media.sort(key=lambda x: x.get("vote_average", 0), reverse=True)
        all_media = all_media[:500]

        # Cache combined result
        await redis_service.set_top_media(all_media)

        start_idx = (page - 1) * 20
        end_idx = start_idx + 20

        # Convert to MediaRead objects
        media_objects = [_tmdb_to_media_read(item) for item in all_media[start_idx:end_idx]]

        return MediaSearch(
            results=media_objects,
            page=page,
            total_pages=25,
            total_results=len(all_media)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching top media: {str(e)}"
        )


def _tmdb_to_media_read(tmdb_data: dict) -> MediaRead:
    """Convert TMDB API response to MediaRead object"""
    media_type = tmdb_data.get("media_type", "movie")

    # Handle different title fields for movies vs TV
    title = tmdb_data.get("title") if media_type == "movie" else tmdb_data.get("name")
    original_title = tmdb_data.get("original_title") if media_type == "movie" else tmdb_data.get("original_name")

    # Handle different date fields
    release_date = tmdb_data.get("release_date") if media_type == "movie" else tmdb_data.get("first_air_date")

    return MediaRead(
        id=None,  # Not in DB yet
        tmdb_id=tmdb_data.get("id"),
        media_type=MediaType.MOVIE if media_type == "movie" else MediaType.TV,
        title=title,
        original_title=original_title,
        overview=tmdb_data.get("overview"),
        poster_path=tmdb_data.get("poster_path"),
        backdrop_path=tmdb_data.get("backdrop_path"),
        release_date=release_date,
        runtime=None,  # Not available in list endpoints
        number_of_seasons=None,
        number_of_episodes=None,
        episode_run_time=None,
        genre_ids=tmdb_data.get("genre_ids", []),
        genres=None,
        production_companies=None,
        actors=None,
        directors=None,
        original_language=tmdb_data.get("original_language"),
        popularity=tmdb_data.get("popularity"),
        vote_average=tmdb_data.get("vote_average"),
        vote_count=tmdb_data.get("vote_count"),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@router.get("/top/genre/{genre_id}", response_model=dict)
async def get_top_media_by_genre(
        genre_id: int,
        media_type: Optional[MediaType] = Query(None, description="Filter by media type (movie or tv)"),
        page: int = Query(1, ge=1, le=25),
        session: AsyncSession = Depends(get_session)
):
    """
    Get top rated media filtered by genre (cached for performance)
    Fetches from TMDB's discover endpoint and caches results
    """
    # Determine cache key based on media_type
    cache_type = "all" if not media_type else media_type.value

    # Check Redis cache
    try:
        cached_media = await redis_service.get_genre_media(genre_id, cache_type)

        if cached_media:
            start_idx = (page - 1) * 20
            end_idx = start_idx + 20
            return {
                "results": cached_media[start_idx:end_idx],
                "page": page,
                "total_pages": min(25, len(cached_media) // 20 + 1),
                "source": "cache"
            }
    except Exception as e:
        # Log cache error but continue to fetch from TMDB
        print(f"Cache error for genre {genre_id}: {str(e)}")

    # Fetch from TMDB
    try:
        all_media = []

        # Fetch multiple pages to get enough content (10 pages = 200 items)
        pages_to_fetch = 10

        if not media_type or media_type == MediaType.MOVIE:
            try:
                for p in range(1, pages_to_fetch + 1):
                    movie_results = await tmdb_service.discover_movies_by_genre(
                        genre_id=genre_id,
                        page=p
                    )

                    if not movie_results or "results" not in movie_results:
                        break

                    for movie in movie_results.get("results", []):
                        movie["media_type"] = "movie"
                        all_media.append(movie)

                    # Stop if we got less than 20 results (last page)
                    if len(movie_results.get("results", [])) < 20:
                        break
            except Exception as e:
                print(f"Error fetching movies for genre {genre_id}: {str(e)}")

        if not media_type or media_type == MediaType.TV:
            try:
                for p in range(1, pages_to_fetch + 1):
                    tv_results = await tmdb_service.discover_tv_by_genre(
                        genre_id=genre_id,
                        page=p
                    )

                    if not tv_results or "results" not in tv_results:
                        break

                    for show in tv_results.get("results", []):
                        show["media_type"] = "tv"
                        all_media.append(show)

                    # Stop if we got less than 20 results (last page)
                    if len(tv_results.get("results", [])) < 20:
                        break
            except Exception as e:
                print(f"Error fetching TV shows for genre {genre_id}: {str(e)}")

        # If no results found, return empty
        if not all_media:
            return {
                "results": [],
                "page": page,
                "total_pages": 0,
                "source": "tmdb"
            }

        # Sort by vote_average if combining both types
        if not media_type:
            all_media.sort(key=lambda x: x.get("vote_average", 0), reverse=True)

        # Limit to 200 items
        all_media = all_media[:200]

        # Cache results
        try:
            await redis_service.set_genre_media(genre_id, all_media, cache_type)
        except Exception as e:
            print(f"Error caching genre {genre_id}: {str(e)}")

        # Return requested page
        start_idx = (page - 1) * 20
        end_idx = start_idx + 20

        return {
            "results": all_media[start_idx:end_idx],
            "page": page,
            "total_pages": min(25, len(all_media) // 20 + 1),
            "source": "tmdb"
        }

    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        import traceback
        print(f"Error in get_top_media_by_genre for genre {genre_id}:")
        print(traceback.format_exc())

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching media by genre {genre_id}: {str(e)}"
        )


@router.delete("/cache/genre/{genre_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_genre_cache(genre_id: int):
    """Clear cache for a specific genre"""
    await redis_service.clear_genre_cache(genre_id)
    return None


@router.delete("/cache/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_media_cache():
    """Clear all media caches (admin utility)"""
    await redis_service.clear_top_movies()
    await redis_service.clear_top_tv()
    await redis_service.clear_top_media()
    return None
