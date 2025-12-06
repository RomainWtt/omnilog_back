import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from uuid import UUID
from typing import Optional, Set

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_optional_current_user, get_current_user
from app.crud import crud_media, crud_genre
from app.db.models import MediaType, User, ListStatus, Media, UserMediaEntry
from app.db.session import get_session
from app.schemas.genre import GenreRead
from app.schemas.media import (
    MediaRead,
    MediaSearch
)
from app.schemas.tv import TVSeasonsSchema, SeasonSchema, EpisodeSchema
from app.services.redis_service import redis_service
from datetime import datetime
import asyncio
from app.services.tmdb_service import tmdb_service
from fastapi import BackgroundTasks
import asyncio
from asyncio import Semaphore

router = APIRouter()


async def _fetch_and_filter_results(
        query: Optional[str],
        media_type: Optional[MediaType],
        filters: dict,
        required_genre_ids: Set[int],
        min_year: Optional[int],
        max_year: Optional[int],
        min_rating: Optional[float],
        max_pages: int = 5
) -> list:
    """
    Helper pour fetch et filtrer les résultats (movies et/ou TV).
    Utilisé par search_media et discover_media pour éviter la duplication.
    """
    all_filtered_results = []

    search_movie = not media_type or media_type == MediaType.MOVIE
    search_tv = not media_type or media_type == MediaType.TV

    # Fetch movies
    if search_movie:
        for p in range(1, max_pages + 1):
            try:
                if query:
                    movie_results = await tmdb_service.search_movie(query, p)
                else:
                    movie_filters = filters.copy()
                    movie_results = await tmdb_service.discover_media("movie", p, **movie_filters)

                movies = movie_results.get("results", [])
                if not movies:
                    break

                # Filter each movie
                for movie in movies:
                    if _matches_filters(
                            movie, required_genre_ids, min_year, max_year, min_rating
                    ):
                        all_filtered_results.append(movie)

                # Stop if we have enough results
                if len(all_filtered_results) >= 20:
                    break

                # Stop if last page
                if len(movies) < 20:
                    break

            except HTTPException as e:
                if e.status_code == 429:  # Rate limit
                    await asyncio.sleep(1)
                    continue
                raise

    # Fetch TV shows
    if search_tv:
        for p in range(1, max_pages + 1):
            try:
                if query:
                    tv_results = await tmdb_service.search_tv(query, p)
                else:
                    tv_filters = filters.copy()
                    tv_results = await tmdb_service.discover_media("tv", p, **tv_filters)

                shows = tv_results.get("results", [])
                if not shows:
                    break

                # Filter each show
                for show in shows:
                    if _matches_filters(
                            show, required_genre_ids, min_year, max_year, min_rating
                    ):
                        all_filtered_results.append(show)

                # Stop if we have enough results
                if len(all_filtered_results) >= 20:
                    break

                # Stop if last page
                if len(shows) < 20:
                    break

            except HTTPException as e:
                if e.status_code == 429:  # Rate limit
                    await asyncio.sleep(1)
                    continue
                raise

    return all_filtered_results


@router.get("/search", response_model=MediaSearch)  # Changé de dict à MediaSearch
async def search_media(
        query: str = Query(..., min_length=1, description="Search query"),
        media_type: Optional[MediaType] = Query(None, description="Filter by media type (movie or tv)"),
        genre_ids: Optional[str] = Query(None, description="Comma-separated genre IDs (AND logic)"),
        min_year: Optional[int] = Query(None, description="Minimum release year"),
        max_year: Optional[int] = Query(None, description="Maximum release year"),
        min_rating: Optional[float] = Query(None, ge=0, le=10, description="Minimum vote average"),
        min_runtime: Optional[int] = Query(None, description="Minimum runtime in minutes (movies only)"),
        max_runtime: Optional[int] = Query(None, description="Maximum runtime in minutes (movies only)"),
        page: int = Query(1, ge=1, description="Page number"),
        session: AsyncSession = Depends(get_session),
        current_user: Optional[User] = Depends(get_optional_current_user)  # Ajouté
):
    """
    Search for movies and TV shows via TMDB with optional filters.
    Returns properly structured MediaRead objects with library status if user is authenticated
    """

    print("=" * 80)
    print("🔍 SEARCH ENDPOINT")
    print(f"query: {query}")
    print(f"genre_ids: {genre_ids}")
    print(f"filters: year={min_year}-{max_year}, rating={min_rating}, runtime={min_runtime}-{max_runtime}")
    print("=" * 80)

    # Check for runtime filters with keyword search
    if (min_runtime or max_runtime) and query:
        print("⚠️ Runtime filters with keyword search - returning empty results")
        return MediaSearch(
            results=[],
            page=1,
            total_pages=0,
            total_results=0
        )

    try:
        has_filters = bool(genre_ids or min_year or max_year or min_rating)

        if not has_filters:
            # Simple keyword search without filters
            if media_type == MediaType.MOVIE:
                movie_results = await tmdb_service.search_movie(query, page)
                all_results = movie_results.get("results", [])
                total_pages = movie_results.get("total_pages", 1)
            elif media_type == MediaType.TV:
                tv_results = await tmdb_service.search_tv(query, page)
                all_results = tv_results.get("results", [])
                total_pages = tv_results.get("total_pages", 1)
            else:
                # Both
                movie_results = await tmdb_service.search_movie(query, page)
                tv_results = await tmdb_service.search_tv(query, page)
                all_results = movie_results.get("results", []) + tv_results.get("results", [])
                all_results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
                total_pages = max(
                    movie_results.get("total_pages", 1),
                    tv_results.get("total_pages", 1)
                )

            # Convertir en MediaRead
            media_objects = [_tmdb_to_media_read(item) for item in all_results]

            # Enrichir avec statut library si user connecté
            if current_user:
                media_objects = await _enrich_with_library_status(
                    session=session,
                    user_id=current_user.id,
                    media_list=media_objects
                )

            return MediaSearch(
                results=media_objects,
                page=page,
                total_pages=total_pages,
                total_results=len(all_results)
            )

        # Search with filters: fetch multiple pages and filter
        required_genre_ids: Set[int] = set()
        if genre_ids:
            required_genre_ids = {int(gid) for gid in genre_ids.split(',')}

        all_filtered_results = await _fetch_and_filter_results(
            query=query,
            media_type=media_type,
            filters={},
            required_genre_ids=required_genre_ids,
            min_year=min_year,
            max_year=max_year,
            min_rating=min_rating,
            max_pages=5
        )

        # Sort by popularity
        all_filtered_results.sort(key=lambda x: x.get("popularity", 0), reverse=True)

        print(f"✅ Found {len(all_filtered_results)} results after filtering")

        # Convertir en MediaRead
        media_objects = [_tmdb_to_media_read(item) for item in all_filtered_results[:20]]

        # Enrichir avec statut library si user connecté
        if current_user:
            media_objects = await _enrich_with_library_status(
                session=session,
                user_id=current_user.id,
                media_list=media_objects
            )

        return MediaSearch(
            results=media_objects,
            page=1,
            total_pages=1,
            total_results=len(all_filtered_results)
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ Error in search_media:")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching media: {str(e)}"
        )


def _matches_filters(
        media: dict,
        required_genre_ids: Set[int],
        min_year: Optional[int],
        max_year: Optional[int],
        min_rating: Optional[float]
) -> bool:
    """
    Check if a media item matches all filters.

    Note: Runtime parameter removed because the TMDB search API
    does not return runtime information. Runtime filtering should only be
    used with the discover endpoint.
    """

    # Genre filter (AND logic - must have ALL required genres)
    if required_genre_ids:
        media_genres = set(media.get("genre_ids", []))
        if not required_genre_ids.issubset(media_genres):
            return False

    # Year filter
    if min_year or max_year:
        date_str = media.get("release_date") or media.get("first_air_date")
        if date_str:
            try:
                year = int(date_str[:4])
                if min_year and year < min_year:
                    return False
                if max_year and year > max_year:
                    return False
            except (ValueError, TypeError):
                pass

    # Rating filter
    if min_rating:
        vote_avg = media.get("vote_average", 0)
        if vote_avg < min_rating:
            return False

    return True


@router.get("/discover", response_model=MediaSearch)  # Changé de dict à MediaSearch
async def discover_media(
        media_type: Optional[MediaType] = Query(None, description="Filter by media type (movie or tv)"),
        genre_ids: Optional[str] = Query(None, description="Comma-separated genre IDs (AND logic)"),
        min_year: Optional[int] = Query(None, description="Minimum release year"),
        max_year: Optional[int] = Query(None, description="Maximum release year"),
        min_rating: Optional[float] = Query(None, ge=0, le=10, description="Minimum vote average"),
        min_runtime: Optional[int] = Query(None, description="Minimum runtime in minutes"),
        max_runtime: Optional[int] = Query(None, description="Maximum runtime in minutes"),
        page: int = Query(1, ge=1, description="Page number"),
        session: AsyncSession = Depends(get_session),
        current_user: Optional[User] = Depends(get_optional_current_user),  # Ajouté
):
    """
    Discover media with filters only (no keyword search).
    Returns properly structured MediaRead objects with library status if user is authenticated
    """
    print("=" * 80)
    print("🔍 DISCOVER ENDPOINT")
    print(f"media_type: {media_type}")
    print(f"genre_ids: {genre_ids}")
    print(f"filters: year={min_year}-{max_year}, rating={min_rating}, runtime={min_runtime}-{max_runtime}")
    print("=" * 80)

    try:
        all_media = []
        pages_to_fetch = 5

        # Build base filters
        base_filters = {}
        if genre_ids:
            base_filters["with_genres"] = genre_ids
        if min_rating:
            base_filters["vote_average.gte"] = min_rating

        # Prepare tasks for parallel fetching
        tasks = []

        # Fetch movies
        if not media_type or media_type == MediaType.MOVIE:
            movie_filters = base_filters.copy()

            if min_year:
                movie_filters["primary_release_date.gte"] = f"{min_year}-01-01"
            if max_year:
                movie_filters["primary_release_date.lte"] = f"{max_year}-12-31"

            if min_runtime:
                movie_filters["with_runtime.gte"] = min_runtime
            if max_runtime:
                movie_filters["with_runtime.lte"] = max_runtime

            print(f"🎬 Fetching movies with filters: {movie_filters}")

            for p in range(1, pages_to_fetch + 1):
                tasks.append(('movie', tmdb_service.discover_media(
                    media_type="movie",
                    page=p,
                    **movie_filters
                )))

        # Fetch TV shows
        if not media_type or media_type == MediaType.TV:
            tv_filters = base_filters.copy()

            if min_year:
                tv_filters["first_air_date.gte"] = f"{min_year}-01-01"
            if max_year:
                tv_filters["first_air_date.lte"] = f"{max_year}-12-31"

            if min_runtime:
                tv_filters["with_runtime.gte"] = min_runtime
            if max_runtime:
                tv_filters["with_runtime.lte"] = max_runtime

            print(f"📺 Fetching TV shows with filters: {tv_filters}")

            for p in range(1, pages_to_fetch + 1):
                tasks.append(('tv', tmdb_service.discover_media(
                    media_type="tv",
                    page=p,
                    **tv_filters
                )))

        # Execute all requests in parallel
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                print(f"⚠️ Error fetching page: {result}")
                continue

            page_results = result.get("results", [])
            all_media.extend(page_results)

        # Sort by vote_average
        all_media.sort(key=lambda x: x.get("vote_average", 0), reverse=True)

        print(f"✅ Found {len(all_media)} total results")

        # Return paginated
        start_idx = (page - 1) * 20
        end_idx = start_idx + 20

        # Convertir en MediaRead
        media_objects = [_tmdb_to_media_read(item) for item in all_media[start_idx:end_idx]]

        # Enrichir avec statut library si user connecté
        if current_user:
            media_objects = await _enrich_with_library_status(
                session=session,
                user_id=current_user.id,
                media_list=media_objects
            )

        return MediaSearch(
            results=media_objects,
            page=page,
            total_pages=(len(all_media) + 19) // 20,
            total_results=len(all_media)
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ Error in discover_media:")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error discovering media: {str(e)}"
        )


@router.get("/{media_id}", response_model=MediaRead)
async def get_media_details(
        media_id: UUID,
        language: str = Query("fr", description="Language code (fr, en, de, nl)"),  # ✨ NOUVEAU
        session: AsyncSession = Depends(get_session),
        current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Get detailed information about a specific media item in the requested language
    """
    media = await crud_media.get_media_by_id(session, media_id)

    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )

    # Vérifier si les traductions existent, sinon les récupérer
    if not media.translations or not media.translations.get("title"):
        media = await crud_media.update_media_translations(session, media_id)

    genres = await crud_genre.get_genres_by_ids(
        session,
        media.genre_ids or [],
    )

    # Fetch full details from TMDB if we don't have them
    needs_update = False
    if media.media_type == MediaType.MOVIE and not media.runtime:
        needs_update = True
    elif media.media_type == MediaType.TV and not media.number_of_seasons:
        needs_update = True

    if needs_update:
        try:
            if media.media_type == MediaType.MOVIE:
                tmdb_details = await tmdb_service.get_movie_details(media.tmdb_id)
            else:
                tmdb_details = await tmdb_service.get_tv_details(media.tmdb_id)

            actors = []
            if "credits" in tmdb_details and "cast" in tmdb_details["credits"]:
                actors = [actor["name"] for actor in tmdb_details["credits"]["cast"][:5]]

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
            print(f"Error fetching TMDB details for {media_id}: {str(e)}")
            pass

    # APPLIQUER LA TRADUCTION
    translated_title = crud_media.get_translated_field(media, "title", language)
    translated_overview = crud_media.get_translated_field(media, "overview", language)

    media_dict = media.model_dump()
    media_dict["title"] = translated_title
    media_dict["overview"] = translated_overview
    media_dict["genres"] = [GenreRead.model_validate(g) for g in genres]

    media_read = MediaRead.model_validate(media_dict)

    # Enrichir avec statut library si user connecté
    if current_user:
        stmt = select(UserMediaEntry.list_status).where(
            UserMediaEntry.user_id == current_user.id,
            UserMediaEntry.media_id == media_id
        )
        result = await session.execute(stmt)
        list_status = result.scalar_one_or_none()

        media_read.in_library = list_status is not None
        media_read.library_status = list_status

    return media_read


@router.get("/tmdb/{tmdb_id}", response_model=MediaRead)
async def get_media_by_tmdb_id(
        tmdb_id: int,
        media_type: MediaType = Query(..., description="Media type (movie or tv)"),
        language: str = Query("fr", description="Language code (fr, en, de, nl)"),  # ✨ NOUVEAU
        session: AsyncSession = Depends(get_session),
        current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Get media by TMDB ID, fetch from TMDB if not in database.
    Returns data in the requested language.
    """
    media = await crud_media.get_media_by_tmdb_id(session, tmdb_id, media_type)

    if not media:
        # Fetch from TMDB and store WITH translations
        try:
            if media_type == MediaType.MOVIE:
                tmdb_data = await tmdb_service.get_movie_details(tmdb_id)
            else:
                tmdb_data = await tmdb_service.get_tv_details(tmdb_id)

            release_date_str = tmdb_data.get("release_date") or tmdb_data.get("first_air_date")
            release_date = None
            if release_date_str:
                try:
                    release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    release_date = None

            actors = []
            if "credits" in tmdb_data and "cast" in tmdb_data["credits"]:
                actors = [actor["name"] for actor in tmdb_data["credits"]["cast"][:5]]

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

            media = await crud_media.create_media_with_translations(
                session=session,
                tmdb_id=tmdb_id,
                media_type=media_type,
                **media_data
            )

        except HTTPException:
            raise
        except Exception as e:
            import traceback
            print(f"Error fetching media {tmdb_id}:")
            print(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching media: {str(e)}"
            )

    translated_title = crud_media.get_translated_field(media, "title", language)
    translated_overview = crud_media.get_translated_field(media, "overview", language)

    # Créer le MediaRead avec les traductions
    media_dict = media.model_dump()
    media_dict["title"] = translated_title
    media_dict["overview"] = translated_overview

    media_read = MediaRead.model_validate(media_dict, from_attributes=True)

    # Enrichir avec statut library si user connecté
    if current_user and media.id:
        stmt = select(UserMediaEntry.list_status).where(
            UserMediaEntry.user_id == current_user.id,
            UserMediaEntry.media_id == media.id
        )
        result = await session.execute(stmt)
        list_status = result.scalar_one_or_none()

        media_read.in_library = list_status is not None
        media_read.library_status = list_status

    return media_read


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


from fastapi import BackgroundTasks


@router.get("/top/all", response_model=MediaSearch)
async def get_top_media(
        background_tasks: BackgroundTasks,
        page: int = Query(1, ge=1, le=25),
        current_user: Optional[User] = Depends(get_optional_current_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Get top rated media (movies + TV combined, sorted by vote_average)
    Returns properly structured MediaRead objects with library status if user is authenticated
    """
    # Check Redis cache
    cached_media = await redis_service.get_top_media()

    if cached_media:
        start_idx = (page - 1) * 20
        end_idx = start_idx + 20

        current_page_items = cached_media[start_idx:end_idx]

        # Convert cached dict to MediaRead objects
        media_objects = [_tmdb_to_media_read(item) for item in current_page_items]

        # Enrich with library status if user is authenticated
        if current_user:
            media_objects = await _enrich_with_library_status(
                session=session,
                user_id=current_user.id,
                media_list=media_objects
            )


        background_tasks.add_task(
            prefetch_translations_for_items,
            current_page_items
        )

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
                all_movies.extend(tmdb_results.get("results", []))
            cached_movies = all_movies[:500]
            await redis_service.set_top_movies(cached_movies)

        # Get TV
        cached_tv = await redis_service.get_top_tv()
        if not cached_tv:
            all_tv = []
            for p in range(1, 26):
                tmdb_results = await tmdb_service.get_top_rated_tv(p)
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

        current_page_items = all_media[start_idx:end_idx]

        # Convert to MediaRead objects
        media_objects = [_tmdb_to_media_read(item) for item in current_page_items]

        # Enrich with library status if user is authenticated
        if current_user:
            media_objects = await _enrich_with_library_status(
                session=session,
                user_id=current_user.id,
                media_list=media_objects
            )

        background_tasks.add_task(
            prefetch_translations_for_items,
            current_page_items
        )

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


async def prefetch_translations_for_items(media_items: list[dict]):
    """
    Précharge les traductions pour une liste de médias en arrière-plan.
    Respecte la limite de 40 req/sec de TMDB.
    """
    semaphore = Semaphore(10)  # Max 10 requêtes simultanées

    async def fetch_and_cache(item: dict):
        async with semaphore:
            tmdb_id = item.get("id")
            media_type = item.get("media_type")

            if not tmdb_id or not media_type:
                return

            # Vérifier si déjà en cache
            cached = await redis_service.get_media_translations(tmdb_id, media_type)
            if cached:
                print(f"Est dans le cache {item.get('title')}")
                return

            try:
                # Récupérer les traductions
                translations = await tmdb_service.get_complete_translations(tmdb_id, media_type)

                # Mettre en cache
                await redis_service.set_media_translations(
                    tmdb_id,
                    media_type,
                    translations,
                    ttl=86400  # 24 heures
                )

                # Pause pour respecter le rate limit (40 req/sec = 25ms entre requêtes)
                await asyncio.sleep(0.025)

            except Exception as e:
                print(f"⚠️ Failed to prefetch translations for {media_type} {tmdb_id}: {e}")

    # Lancer toutes les tâches en parallèle avec gestion d'erreur
    await asyncio.gather(
        *[fetch_and_cache(item) for item in media_items],
        return_exceptions=True
    )


async def _enrich_with_library_status(
        session: AsyncSession,
        user_id: UUID,
        media_list: List[MediaRead]
) -> List[MediaRead]:
    """
    Enrich a list of MediaRead objects with library status information.

    Args:
        session: Database session
        user_id: Current user ID
        media_list: List of MediaRead objects to enrich

    Returns:
        Same list with in_library and library_status fields populated
    """
    # Extract all TMDB IDs from the media list
    tmdb_ids = [media.tmdb_id for media in media_list]

    # Query user's library for these TMDB IDs
    # Note: You'll need to join Media and UserMediaEntry tables

    stmt = select(Media.tmdb_id, UserMediaEntry.list_status).join(
        UserMediaEntry, Media.id == UserMediaEntry.media_id
    ).where(
        UserMediaEntry.user_id == user_id,
        Media.tmdb_id.in_(tmdb_ids)
    )

    result = await session.execute(stmt)
    library_map: Dict[int, ListStatus] = {row[0]: row[1] for row in result.all()}

    # Enrich each media object
    for media in media_list:
        if media.tmdb_id in library_map:
            media.in_library = True
            media.library_status = library_map[media.tmdb_id]
        else:
            media.in_library = False
            media.library_status = None

    return media_list


def _tmdb_to_media_read(tmdb_data: dict) -> MediaRead:
    """Convert TMDB API response to MediaRead object"""
    media_type = tmdb_data.get("media_type", "movie")

    # Handle different title fields for movies vs TV
    title = tmdb_data.get("title") if media_type == "movie" else tmdb_data.get("name")
    original_title = tmdb_data.get("original_title") if media_type == "movie" else tmdb_data.get("original_name")

    # Handle different date fields
    release_date_raw = tmdb_data.get("release_date") if media_type == "movie" else tmdb_data.get("first_air_date")

    release_date = release_date_raw if release_date_raw and release_date_raw.strip() else None

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


@router.get("/media/{tmdb_id}/translations")
async def get_media_translations(
        tmdb_id: int,
        media_type: str = Query(..., regex="^(movie|tv)$")
):
    """
    Get translations for a specific media item.
    Returns cached translations if available, otherwise fetches from TMDB.

    Response format:
    {
        "title": {"fr": "Very Bad Trip", "en": "The Hangover", "de": "...", "nl": "..."},
        "overview": {"fr": "...", "en": "...", "de": "...", "nl": "..."}
    }
    """
    # Vérifier le cache d'abord
    cached = await redis_service.get_media_translations(tmdb_id, media_type)
    if cached:
        return cached

    # Sinon, récupérer depuis TMDB
    try:
        translations = await tmdb_service.get_complete_translations(tmdb_id, media_type)

        # Mettre en cache
        await redis_service.set_media_translations(tmdb_id, media_type, translations)

        return translations
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching translations: {str(e)}"
        )


@router.get("/top/genre/{genre_id}", response_model=MediaSearch)
async def get_top_media_by_genre(
        genre_id: int,
        media_type: Optional[MediaType] = Query(None, description="Filter by media type (movie or tv)"),
        page: int = Query(1, ge=1, le=25),
        current_user: Optional[User] = Depends(get_optional_current_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Get top rated media filtered by genre (cached for performance)
    Fetches from TMDB's discover endpoint and caches results
    Returns properly structured MediaRead objects with library status if user is authenticated
    """
    # Determine cache key based on media_type
    cache_type = "all" if not media_type else media_type.value

    # Check Redis cache
    try:
        cached_media = await redis_service.get_genre_media(genre_id, cache_type)

        if cached_media:
            start_idx = (page - 1) * 20
            end_idx = start_idx + 20

            # Convert cached dict to MediaRead objects
            media_objects = [_tmdb_to_media_read(item) for item in cached_media[start_idx:end_idx]]

            # Enrich with library status if user is authenticated
            if current_user:
                media_objects = await _enrich_with_library_status(
                    session=session,
                    user_id=current_user.id,
                    media_list=media_objects
                )

            return MediaSearch(
                results=media_objects,
                page=page,
                total_pages=min(25, len(cached_media) // 20 + 1),
                total_results=len(cached_media)
            )
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

                    all_media.extend(movie_results.get("results", []))

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

                    all_media.extend(tv_results.get("results", []))

                    # Stop if we got less than 20 results (last page)
                    if len(tv_results.get("results", [])) < 20:
                        break
            except Exception as e:
                print(f"Error fetching TV shows for genre {genre_id}: {str(e)}")

        # If no results found, return empty
        if not all_media:
            return MediaSearch(
                results=[],
                page=page,
                total_pages=0,
                total_results=0
            )

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

        # Convert to MediaRead objects
        media_objects = [_tmdb_to_media_read(item) for item in all_media[start_idx:end_idx]]

        # Enrich with library status if user is authenticated
        if current_user:
            media_objects = await _enrich_with_library_status(
                session=session,
                user_id=current_user.id,
                media_list=media_objects
            )

        return MediaSearch(
            results=media_objects,
            page=page,
            total_pages=min(25, len(all_media) // 20 + 1),
            total_results=len(all_media)
        )

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


@router.get("/tv/{tmdb_id}/seasons", response_model=TVSeasonsSchema)
async def get_tv_seasons_episodes(
        tmdb_id: int,
        session: AsyncSession = Depends(get_session)
):
    """
    Get all seasons and episodes for a TV show
    """
    try:
        # Get TV show details to know how many seasons exist
        tv_details = await tmdb_service.get_tv_details(tmdb_id)

        seasons = tv_details.get("seasons", [])

        if not seasons:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No seasons found for this TV show"
            )

        # Create tasks to fetch all seasons in parallel
        tasks = []
        season_numbers = []

        for season in seasons:
            season_number = season.get("season_number")
            # Include all seasons (even Season 0 for specials)
            season_numbers.append(season_number)
            tasks.append(tmdb_service.get_tv_season(tmdb_id, season_number))

        # Execute all requests in parallel
        season_responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dictionary
        result = {"seasons": {}}

        for season_number, response in zip(season_numbers, season_responses):
            if isinstance(response, Exception):
                continue

            episodes = response.get("episodes", [])

            formatted_episodes = [
                EpisodeSchema(
                    episode_number=e.get("episode_number"),
                    name=e.get("name"),
                    air_date=e.get("air_date"),
                    runtime=e.get("runtime"),
                    overview=e.get("overview"),
                    still_path=e.get("still_path"),
                    vote_average=e.get("vote_average"),
                    vote_count=e.get("vote_count"),
                    season_number=season_number
                )
                for e in episodes
            ]

            result["seasons"][season_number] = SeasonSchema(
                season_number=season_number,
                episodes=formatted_episodes
            )

        return TVSeasonsSchema(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching TV seasons: {str(e)}"
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


# app/routes/media.py

@router.post("/{media_id}/translations/refresh")
async def refresh_media_translations(
        media_id: UUID,
        session: AsyncSession = Depends(get_session),
):
    """
    Refresh translations for a specific media from TMDB.
    Useful if translations were updated or incomplete.
    """
    media = await crud_media.update_media_translations(session, media_id)

    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )

    return {
        "success": True,
        "message": f"Translations refreshed for {media.title}",
        "available_languages": list(media.translations.get("title", {}).keys())
    }
