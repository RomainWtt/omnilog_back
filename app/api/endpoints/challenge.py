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
from app.db.models import User, ChallengeStatus, ChallengeType, MediaType, ChallengeMembership, ActivityType
from app.db.session import get_session
from app.schemas.activity import ActivityChallenge
from app.schemas.challenge import ChallengeCreate, ChallengeRead, ChallengeProgressUpdate, ChallengeUpdate


from app.crud.crud_challenge import (
    get_challenge_by_id,
    search_challenges_details,
    get_challenges_by_type,
    get_user_challenges,
    list_newest_challenges_with_details,
    get_challenge_with_medias,
)
from app.schemas.memberships import RankingMembership

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
    return await crud_challenge.get_challenge_by_id(session = session, challenge_id=challenge_id)


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


@router.put("/{challenge_id}/progress")
async def update_user_progress(
        challenge_id: UUID,
        data: ChallengeProgressUpdate,
        session: AsyncSession = Depends(get_session),
        current_user = Depends(get_current_active_user)
):
    await crud_challenge_stats.update_progress(session = session, data = data, challenge_id= challenge_id, current_user=current_user )
    """
    
    # Vérifier challenge
    challenge = await crud_challenge.get_challenge_by_id(session=session, challenge_id=challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Vérifier membre
    result = await session.execute(
        select(ChallengeMembership).where(
            ChallengeMembership.user_id == current_user.id,
            ChallengeMembership.challenge_id == challenge_id
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this challenge")

    # Vérifier média
    media = await crud_media.get_media_by_id(session=session, media_id=data.media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    # Récupérer ou initialiser completed_media
    completed_media = membership.completed_media or {}
    if isinstance(completed_media, str):
        import json
        completed_media = json.loads(completed_media)

    media_id_str = str(media.id)

    # Mettre à jour progression média
    if media.media_type == MediaType.TV:
        completed_media[media_id_str] = {
            "media_type": "tv",
            "tmdb_id": media.tmdb_id,
            "status": data.status or "watching",
            "current_season": data.current_season,
            "current_episode": data.current_episode,
            "last_updated": datetime.utcnow().isoformat()
        }
    elif media.media_type == MediaType.MOVIE:
        completed_media[media_id_str] = {
            "media_type": "movie",
            "tmdb_id": media.tmdb_id,
            "status": data.status or "watching",
            "time_code": data.time_code,
            "last_updated": datetime.utcnow().isoformat()
        }

    membership.completed_media = completed_media
    flag_modified(membership, "completed_media")

    # Recalculer la progression individuelle
    total_medias = len(challenge.media_list) if challenge.media_list else 0
    completed_count = sum(
        1 for m in completed_media.values() if m.get("status") == "completed"
    )
    membership.progress = int((completed_count / total_medias) * 100) if total_medias > 0 else 0
    membership.updated_at = datetime.utcnow()
    session.add(membership)
    await session.commit()
    await session.refresh(membership)

    # 4. Milestones (25%, 50%, 75%, 100%)
    milestones = [25, 50, 75, 100]
    for milestone in milestones:
        if milestone <= membership.progress :
            await crud_activity.add_challenge_activity(
                session,
                user_id=current_user.id,
                challenge_id=challenge_id,
                activity_type=ActivityType.CHALLENGE_MILESTONE,
                timestamp=datetime.utcnow(),
                details={
                    "milestone": milestone,
                    "completed_count": completed_count,
                    "total_count": total_medias,
                }
            )

    # 5. Challenge terminé
    if membership.progress  == 100 :
        await crud_activity.add_challenge_activity(
            user_id=current_user.id,
            challenge_id=challenge_id,
            activity_type=ActivityType.CHALLENGE_FINISHED,
            timestamp=datetime.utcnow(),
            details={
                "total_medias": total_medias,
                "completion_date": datetime.utcnow().isoformat(),
            }
        )

    # Recalculer le classement
    from app.crud.crud_challenge_stats import calculate_ranking_challenge
    ranking = await calculate_ranking_challenge(session, challenge_id)

    return {
        "success": True,
        "user_progress": membership.progress,
        "completed_count": completed_count,
        "total_medias": total_medias,
        "media_progress": completed_media[media_id_str],
        "ranking": ranking  # liste de RankingMembership
    }
    """

@router.get("/{challenge_id}/ranking", response_model=list[RankingMembership])
async def calculate_ranking_challenge(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    return await crud_challenge_stats.calculate_ranking_challenge(session, challenge_id)


@router.get("/{challenge_id}/activities", response_model=List[ActivityChallenge])
async def read_challenge_activities(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    return await crud_activity.get_challenge_activities(session, challenge_id)
