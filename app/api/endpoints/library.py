from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import HTTPException, status, Query
from sqlalchemy import select, func, cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.deps import get_current_active_user, get_optional_current_user
from app.crud import crud_media
from app.db.models import Genre
from app.db.models import ListStatus, NotificationType
from app.db.models import User, UserMediaEntry, Media, MediaType
from app.db.session import get_session
from app.schemas.media import (
    UserMediaEntryCreate,
    UserMediaEntryUpdate,
    UserMediaEntryRead,
    UserMediaEntryWithMedia,
    ProgressUpdate,
    MediaRead
)
from app.schemas.streaming_availability import StreamingAvailabilityRead
from app.schemas.watch_list_stats import WatchlistStats
from app.services.notification_service import notification_service
from app.services.recommendation_service import recommendation_service
from app.services.streaming_service import streaming_service

router = APIRouter()


@router.get(
    "/recommendations",
    response_model=List[MediaRead],
    summary="Obtenir des recommandations personnalisées"
)
async def get_recommendations(
        limit: int = Query(30, ge=1, le=50),
        current_user: User = Depends(get_optional_current_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Get personalized recommendations based on user's profile.

    Algorithm:
    1. Build user profile from highly rated completed media (score >= 4.0)
    2. Fetch candidates from TMDB Discover API filtered by user preferences
    3. Score each candidate based on:
       - Genre match (40%)
       - Cast match (20%)
       - Director match (15%)
       - Rating proximity (15%)
       - Popularity boost (10%)
    4. Exclude media already in library
    5. Sort by match score (desc) then TMDB rating (desc)
    """

    if current_user is None:
        return []

    return await recommendation_service.get_recommendations(
        session=session,
        user_id=current_user.id,
        limit=limit
    )


def _map_tmdb_to_schema(item: dict, media_type: MediaType, genre_objects: List[Genre] = None) -> MediaRead:
    """Helper to map TMDB raw response to MediaRead schema"""

    # Handle dates safely
    date_str = item.get("release_date") or item.get("first_air_date")
    release_date = None
    if date_str:
        try:
            release_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass

    genres = genre_objects if genre_objects else []

    return MediaRead(
        id=None,  # Not in DB yet
        tmdb_id=item["id"],
        media_type=media_type,
        title=item.get("title") or item.get("name"),
        original_title=item.get("original_title") or item.get("original_name"),
        overview=item.get("overview", ""),
        poster_path=item.get("poster_path"),
        backdrop_path=item.get("backdrop_path"),
        vote_average=item.get("vote_average"),
        vote_count=item.get("vote_count"),
        popularity=item.get("popularity"),
        original_language=item.get("original_language"),
        genres=genres,
        release_date=release_date,
        # Default optional fields to None
        runtime=None,
        number_of_seasons=None,
        number_of_episodes=None,
        episode_run_time=None,
        production_companies=None,
        actors=None,
        directors=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@router.get(
    "/favorites/count",
    response_model=int,
    summary="Compter les favoris"
)
async def get_favorites_count(
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """Retourne le nombre total de médias marqués comme favoris par l'utilisateur connecté."""
    stmt = select(func.count(UserMediaEntry.media_id)).where(
        UserMediaEntry.user_id == current_user.id,
        UserMediaEntry.is_favorite == True
    )

    result = await session.execute(stmt)
    count = result.scalar() or 0

    return count


@router.get(
    "/stats",
    response_model=WatchlistStats,
    summary="Obtenir les statistiques de la watchlist"
)
async def get_watchlist_stats(
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Récupère les statistiques de la watchlist de l'utilisateur

    Retourne le nombre total de médias ainsi que le détail par type:
    - Films (movies)
    - Séries (series)
    - Animés (anime)
    """

    # Requête pour compter les films
    movies_stmt = (
        select(func.count(UserMediaEntry.media_id))
        .join(Media, UserMediaEntry.media_id == Media.id)
        .where(
            UserMediaEntry.user_id == current_user.id,
            UserMediaEntry.list_status == ListStatus.PLAN_TO_WATCH,
            Media.media_type == MediaType.MOVIE,
        )
    )
    movies_result = await session.execute(movies_stmt)
    movies_count = movies_result.scalar() or 0

    # Requête pour compter les séries (SANS les animés)
    series_stmt = (
        select(func.count(UserMediaEntry.media_id))
        .join(Media, UserMediaEntry.media_id == Media.id)
        .where(
            UserMediaEntry.user_id == current_user.id,
            Media.media_type == MediaType.TV,
            UserMediaEntry.list_status == ListStatus.PLAN_TO_WATCH,
            ~cast(Media.genre_ids, JSONB).contains([16])
        )
    )
    series_result = await session.execute(series_stmt)
    series_count = series_result.scalar() or 0

    # Requête pour compter les animés
    anime_stmt = (
        select(func.count(UserMediaEntry.media_id))
        .join(Media, UserMediaEntry.media_id == Media.id)
        .where(
            UserMediaEntry.user_id == current_user.id,
            UserMediaEntry.list_status == ListStatus.PLAN_TO_WATCH,
            Media.media_type != MediaType.MOVIE,
            cast(Media.genre_ids, JSONB).contains([16])
        )
    )

    anime_result = await session.execute(anime_stmt)
    anime_count = anime_result.scalar() or 0
    print(f"Nombre d'animé {anime_stmt}")

    # Total = Films (non animés) + Séries (non animées) + Animés
    total_count = movies_count + series_count + anime_count

    return WatchlistStats(
        total=total_count,
        movies=movies_count,
        series=series_count,
        anime=anime_count
    )


@router.get(
    "/completed/top-rated",
    response_model=list[UserMediaEntryWithMedia],
    summary="Obtenir les médias terminés les mieux notés"
)
async def get_top_rated_completed(
        min_score: float = Query(4.0, ge=0, le=5, description="Minimum score (default: 4.0)"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Get completed media with score >= min_score (default 4.0/5)

    Returns all completed entries from user's library with a score equal or above the specified minimum.
    """
    entries = await crud_media.get_top_rated_completed(
        session=session,
        user_id=current_user.id,
        min_score=min_score,
        limit=limit,
        offset=offset
    )

    result = []
    for entry in entries:
        media = await crud_media.get_media_by_id(session, entry.media_id)
        if media:
            entry_dict = UserMediaEntryRead.model_validate(entry).model_dump()
            entry_dict["media"] = media
            result.append(UserMediaEntryWithMedia(**entry_dict))

    return result


@router.post(
    "/",
    response_model=UserMediaEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un média à la bibliothèque"
)
async def add_to_library(
        entry_data: UserMediaEntryCreate,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Add media to user's library or update if already exists - REMOVED progress
    """
    # Check if media exists
    media = await crud_media.get_media_by_id(session, entry_data.media_id)
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )

    # Create or update entry
    entry = await crud_media.create_user_media_entry(
        session=session,
        user_id=current_user.id,
        media_id=entry_data.media_id,
        list_status=entry_data.list_status,
        current_season=entry_data.current_season,
        current_episode=entry_data.current_episode,
        timecode=entry_data.timecode,
        score=entry_data.score,
        is_favorite=entry_data.is_favorite
    )

    return entry


@router.get(
    "/availability/{tmdb_id}",
    response_model=StreamingAvailabilityRead,
    summary="Obtenir la disponibilité en streaming"
)
async def get_streaming_availability(
        tmdb_id: int,
        media_type: MediaType = Query("movie", description="Type de média: 'movie' ou 'tv'"),
        country_code: str = Query("FR", description="Code ISO 3166-1 alpha-2 du pays (ex: 'FR', 'CA', 'US')"),
        session: AsyncSession = Depends(get_session)
):
    """Récupère les plateformes de streaming où un média est disponible pour un pays spécifique."""
    # Valider l'existence du média dans votre DB (optionnel mais recommandé)
    media_entry = await crud_media.get_media_by_tmdb_id(session, tmdb_id, media_type.lower())
    if not media_entry:
        pass

    try:
        # Appel au service de streaming (qui appelle l'API externe)
        availability_data = await streaming_service.get_availability_by_tmdb_id(
            tmdb_id=tmdb_id,
            media_type=media_type.lower(),
            country=country_code.upper()
        )

        # Validation et retour du schéma Pydantic
        return StreamingAvailabilityRead(**availability_data)

    except Exception as e:
        # Gérer spécifiquement les erreurs de l'API externe
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erreur lors de la récupération des données de streaming: {str(e)}"
        )


@router.get(
    "/{media_id}",
    response_model=UserMediaEntryRead,
    summary="Récupérer une entrée de bibliothèque"
)
async def get_library_entry(
        media_id: UUID,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """Récupère l'entrée de bibliothèque de l'utilisateur pour un média spécifique."""
    entry = await crud_media.get_user_media_entry(
        session=session,
        user_id=current_user.id,
        media_id=media_id
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not in library"
        )

    return entry


@router.put(
    "/{media_id}",
    response_model=UserMediaEntryRead,
    summary="Mettre à jour une entrée de bibliothèque"
)
async def update_library_entry(
        media_id: UUID,
        entry_update: UserMediaEntryUpdate,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Update user's library entry for specific media - REMOVED progress
    
    Can update: list_status, season, episode, timecode, score, is_favorite
    """
    # Check if entry exists
    existing_entry = await crud_media.get_user_media_entry(
        session=session,
        user_id=current_user.id,
        media_id=media_id
    )

    if not existing_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not in library"
        )

    # Update entry
    update_data = entry_update.model_dump(exclude_unset=True)
    updated_entry = await crud_media.update_user_media_entry(
        session=session,
        user_id=current_user.id,
        media_id=media_id,
        **update_data
    )

    return updated_entry


@router.put(
    "/{media_id}/progress",
    response_model=UserMediaEntryRead | None,
    summary="Mettre à jour la progression de visionnage"
)
async def update_progress(
        media_id: UUID,
        progress: ProgressUpdate,
        is_finish: bool = False,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Update viewing progress for a media item - REMOVED progress field

    For movies: timecode (seconds)
    For TV shows: season, episode, timecode (seconds)
    """

    status_movie = ListStatus.COMPLETED if is_finish else ListStatus.WATCHING

    # Check if entry exists
    existing_entry = await crud_media.get_user_media_entry(
        session=session,
        user_id=current_user.id,
        media_id=media_id
    )

    if existing_entry and progress.timecode <= 0 and progress.current_episode <= 1 and progress.current_season <= 1:
        # Supprimer l'entrée directement
        deleted = await crud_media.delete_user_media_entry(
            session=session,
            user_id=current_user.id,
            media_id=media_id
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not in library"
            )
        return None

    if not existing_entry:
        # Create new entry if doesn't exist
        existing_entry = await crud_media.create_user_media_entry(
            session=session,
            user_id=current_user.id,
            media_id=media_id,
            list_status=status_movie,
            current_season=progress.current_season,
            current_episode=progress.current_episode,
            timecode=progress.timecode
        )
        return existing_entry

    # Update progress
    updated_entry = await crud_media.update_user_media_entry(
        session=session,
        user_id=current_user.id,
        media_id=media_id,
        current_season=progress.current_season,
        current_episode=progress.current_episode,
        timecode=progress.timecode,
        list_status=status_movie
    )

    return updated_entry


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un média de la bibliothèque"
)
async def remove_from_library(
        media_id: UUID,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """Supprime un média de la bibliothèque de l'utilisateur."""
    deleted = await crud_media.delete_user_media_entry(
        session=session,
        user_id=current_user.id,
        media_id=media_id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not in library"
        )

    return None


@router.post(
    "/{media_id}/favorite",
    response_model=UserMediaEntryRead,
    summary="Basculer le statut favori"
)
async def toggle_favorite(
        media_id: UUID,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """Bascule le statut favori d'un média et notifie les amis lors de l'ajout."""
    entry = await crud_media.get_user_media_entry(
        session=session,
        user_id=current_user.id,
        media_id=media_id
    )

    if not entry:
        # Create new entry as favorite
        entry = await crud_media.create_user_media_entry(
            session=session,
            user_id=current_user.id,
            media_id=media_id,
            list_status=ListStatus.FAVORITE,
            is_favorite=True
        )

        # Notifier les amis
        media = await crud_media.get_media_by_id(session, media_id)
        await notification_service.notify_all_friends(
            session=session,
            user_id=current_user.id,
            notification_type=NotificationType.FAVORITE_ADDED,
            data={
                "media_id": str(media_id),
                "media_title": media.title if media else "un média"
            }
        )

        return entry

    # Toggle favorite
    was_favorite = entry.is_favorite

    updated_entry = await crud_media.update_user_media_entry(
        session=session,
        user_id=current_user.id,
        media_id=media_id,
        is_favorite=not entry.is_favorite
    )

    if updated_entry.is_favorite and not was_favorite:
        media = await crud_media.get_media_by_id(session, media_id)
        await notification_service.notify_all_friends(
            session=session,
            user_id=current_user.id,
            notification_type=NotificationType.FAVORITE_ADDED,
            data={
                "media_id": str(media_id),
                "media_title": media.title if media else "un média"
            }
        )

    return updated_entry


@router.get(
    "/user/{user_id}/media/{media_id}",
    response_model=UserMediaEntryRead | None,
    summary="Récupérer l'entrée média d'un utilisateur"
)
async def get_user_media_entry(
        user_id: UUID,
        media_id: UUID,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """Récupère l'entrée de bibliothèque d'un utilisateur spécifique pour un média donné."""
    # Récupérer l'entrée pour l'utilisateur spécifié
    entry = await crud_media.get_user_media_entry(
        session=session,
        user_id=user_id,
        media_id=media_id
    )

    if not entry:
        return None

    return entry


@router.get(
    "/user/{user_id}",
    response_model=list[UserMediaEntryWithMedia],
    summary="Récupérer la bibliothèque d'un utilisateur"
)
async def get_user_library(
        user_id: UUID,
        status: Optional[ListStatus] = Query(None, description="Filter by list status"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Get a specific user's media library (for viewing other profiles)

    Can filter by status: watching, completed, plan_to_watch, dropped, on_hold, favorite
    """

    entries = await crud_media.get_user_library(
        session=session,
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset
    )

    result = []
    for entry in entries:
        media = await crud_media.get_media_by_id(session, entry.media_id)
        if media:
            entry_dict = UserMediaEntryRead.model_validate(entry).model_dump()
            entry_dict["media"] = media
            result.append(UserMediaEntryWithMedia(**entry_dict))

    return result


@router.get(
    "/user/{user_id}/favorites",
    response_model=list[UserMediaEntryWithMedia],
    summary="Récupérer les favoris d'un utilisateur"
)
async def get_user_favorites(
        user_id: UUID,
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0),
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """Récupère tous les médias marqués comme favoris par un utilisateur spécifique."""
    entries = await crud_media.get_user_favorites(
        session=session,
        user_id=user_id,
        limit=limit,
        offset=offset
    )

    result = []
    for entry in entries:
        media = await crud_media.get_media_by_id(session, entry.media_id)
        if media:
            entry_dict = UserMediaEntryRead.model_validate(entry).model_dump()
            entry_dict["media"] = media
            result.append(UserMediaEntryWithMedia(**entry_dict))

    return result
