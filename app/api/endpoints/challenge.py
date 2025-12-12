from datetime import datetime
from typing import Optional, List
from uuid import UUID
import json

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import get_current_user, get_current_active_user
from app.crud import crud_media, crud_challenge_stats, crud_challenge, crud_activity
from app.crud.crud_challenge_stats import compute_media_progress
from app.db.models import User, ChallengeStatus, ChallengeType, Media, MediaType, ChallengeMembership, Notification
from app.db.session import get_session
from app.schemas.activity import ActivityChallenge
from app.schemas.challenge import ChallengeCreate, ChallengeRead, ChallengeProgressUpdate, ChallengeUpdate

from app.api.endpoints.media import get_media_by_tmdb_id
from app.crud.crud_challenge import (
    get_challenge_by_id,
    add_new_challenge,
    search_challenges_details,
    get_challenges_by_type,
    get_user_challenges,
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
    return await crud_challenge.add_new_challenge(session, data, current_user)

@router.post("/{challenge_id}", response_model=ChallengeRead)
async def get_challenge_by_id(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    return await crud_challenge.get_challenge_by_id(session, challenge_id)


@router.patch("/update/{challenge_id}", response_model=ChallengeRead)
async def update_challenge(
    challenge_id: UUID,
    data: ChallengeUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Met à jour les informations d'un challenge tant qu'il n'a pas commencé.
    """
    return await crud_challenge.update_challenge(challenge_id, data, session, current_user)

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

    # progression utilisateur
    if current_user:
        result = await session.execute(
            select(ChallengeMembership).where(
                ChallengeMembership.user_id == current_user.id,
                ChallengeMembership.challenge_id == challenge_id
            )
        )
        membership = result.scalar_one_or_none()

        if membership and membership.completed_media:
            completed = membership.completed_media

            # JSON string -> dict
            if isinstance(completed, str):
                completed = json.loads(completed)

            if not isinstance(completed, dict):
                completed = {}

            user_progress = {}

            # (clé = UUID du média en string)
            for media in data.get("medias", []):
                media_id_str = str(media.id)

                if media_id_str in completed:
                    prog = completed[media_id_str]
                    user_progress[media_id_str] = {
                        "status": prog.get("status"),
                        "current_season": prog.get("current_season"),
                        "current_episode": prog.get("current_episode"),
                        "time_code": prog.get("time_code")
                    }

            data["user_progress"] = user_progress

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
    challenge = await get_challenge_by_id(challenge_id, session)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge introuvable")

    membership = await crud_challenge.join_challenge_by_ids(session, current_user.id, challenge_id)

    return {"success": True, "membership_id": getattr(membership, "user_id", None)}



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


@router.put("/{challenge_id}/progress")
async def update_user_progress(
        challenge_id: UUID,
        data: ChallengeProgressUpdate,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user),
):
    # Vérifier challenge
    challenge = await get_challenge_by_id(session=session, challenge_id=challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Vérifier membership
    result = await session.execute(
        select(ChallengeMembership).where(
            ChallengeMembership.user_id == current_user.id,
            ChallengeMembership.challenge_id == challenge_id
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this challenge")

    # Récupérer média
    media = await crud_media.get_media_by_id(session, data.media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    # Charger JSON
    completed_media = membership.completed_media or {}
    if isinstance(completed_media, str):
        completed_media = json.loads(completed_media)

    media_id_str = str(media.id)

    media_result = await compute_media_progress(media, data)
    progress_media = media_result["progress"]

    completed_media[media_id_str] = {
        "media_type": "tv" if media.media_type == MediaType.TV else "movie",
        "tmdb_id": media.tmdb_id,
        **media_result,
        "last_updated": datetime.utcnow().isoformat()
    }

    membership.completed_media = completed_media
    flag_modified(membership, "completed_media")

    total_medias = len(challenge.media_list) if challenge.media_list else 0

    if total_medias > 0:
        progress_sum = sum(
            m.get("progress", 0)
            for m in completed_media.values()
            if isinstance(m, dict)
        )
        global_progress = int(progress_sum / total_medias)
    else:
        global_progress = 0

    membership.progress = global_progress
    membership.updated_at = datetime.utcnow()

    session.add(membership)
    await session.commit()
    await session.refresh(membership)

    return {
        "success": True,
        "media_progress": progress_media,
        "global_progress": global_progress,
        "media_data": completed_media[media_id_str]
    }


@router.get("/{challenge_id}/activities", response_model=List[ActivityChallenge])
async def read_challenge_activities(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    return await crud_activity.get_challenge_activities(session, challenge_id)