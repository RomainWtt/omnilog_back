from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_active_user
from app.crud import crud_media, crud_challenge_stats
from app.crud.crud_challenge_stats import calculate_ranking_challenge
from app.db.models import User, ChallengeStatus, ChallengeType, Media, MediaType
from app.db.session import get_session
from app.schemas.challenge import ChallengeCreate, ChallengeRead

from app.crud.crud_challenge import (
    get_challenge_by_id,
    add_new_challenge,
    search_challenges_details,
    get_challenges_by_type,
    get_user_challenges,
    join_challenge_by_ids,
    list_newest_challenges_with_details,
    get_challenge_with_medias,
)
from app.schemas.memberships import RankingMembership
from app.schemas.tv import TVSeasonsSchema

router = APIRouter()


@router.post("/", response_model=ChallengeRead)
async def create_challenge(
    data: ChallengeCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await add_new_challenge(session, data, current_user)


@router.get("/type/{challenge_type}", response_model=List[ChallengeRead])
async def get_challenges_by_type_route(
    challenge_type: ChallengeType,
    session: AsyncSession = Depends(get_session),
):
    return await get_challenges_by_type(session, challenge_type)


@router.get("/my-challenges", response_model=List[ChallengeRead])
async def get_challenges_personal(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    return await get_user_challenges(session, current_user.id)


@router.get("/search", response_model=List[ChallengeRead])
async def search_challenges(
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    limit = 20
    offset = (page - 1) * limit

    clean_query = query.strip() if query else None
    if clean_query == "":
        clean_query = None

    parsed_status = None
    if status:
        try:
            parsed_status = ChallengeStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    return await search_challenges_details(
        session,
        query=clean_query,
        status=parsed_status,
        limit=limit,
        offset=offset,
    )


@router.get("/{challenge_id}/full")
async def get_challenge_with_medias_details(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_active_user)
):
    personal_user_id = current_user.id if current_user else None
    data = await get_challenge_with_medias(session, challenge_id, personal_user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return data



@router.get("/admin/latest/full")
async def get_newest_challenges(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(5, ge=1, le=50),
):
    challenges = await list_newest_challenges_with_details(session, limit)
    full_challenges = []

    for challenge in challenges:
        data = await get_challenge_with_medias(session, challenge.id)
        if data:
            # Remplace le challenge SQLModel par le Pydantic ChallengeRead déjà construit
            data["challenge"] = challenge
            full_challenges.append(data)

    return full_challenges


# ----------------------
# Participation & progression
# ----------------------
@router.post("/join/{challenge_id}")
async def join_challenge(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    challenge = await get_challenge_by_id(session, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    membership = await join_challenge_by_ids(session, current_user.id, challenge_id)
    return {"success": True, "membership_id": getattr(membership, "user_id", None)}



@router.get("/{challenge_id}/ranking", response_model=List[RankingMembership])
async def get_challenge_ranking(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await calculate_ranking_challenge(session, challenge_id)


@router.post("/media/film/{tmdb_id}/complete", response_model=list[dict])
async def update_progress_challenge_film(
    tmdb_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    media: Media = await crud_media.get_media_by_tmdb_id(session, tmdb_id, MediaType.MOVIE)
    if not media:
        return []

    return await crud_challenge_stats.calculate_progress_film(session, media, current_user)


@router.post("/media/serie/{tmdb_id}/complete", response_model=list[dict])
async def update_progress_challenge_serie(
    tmdb_id: int,
    serie_details: TVSeasonsSchema,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    media: Media = await crud_media.get_media_by_tmdb_id(session, tmdb_id, MediaType.TV)
    if not media:
        return []

    return await crud_challenge_stats.calculate_progress_serie(session, media, serie_details, current_user)
