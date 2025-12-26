from typing import Optional, List
import json
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import get_current_user, get_current_active_user, get_optional_current_user
from app.crud import crud_challenge_stats, crud_challenge, crud_activity, crud_notification
from app.crud.crud_challenge import (
    get_challenge_by_id,
    search_challenges_details,
    get_challenges_by_type,
    get_user_challenges,
    list_newest_challenges_with_details,
    get_challenge_with_medias,
)
from app.db.models import User, ChallengeStatus, ChallengeType, ChallengeMembership, NotificationType
from app.db.session import get_session
from app.schemas.activity import ActivityChallenge
from app.schemas.challenge import ChallengeCreate, ChallengeRead, ChallengeProgressUpdate, ChallengeUpdate
from app.schemas.memberships import RankingMembership

router = APIRouter()


@router.post(
    "/",
    response_model=ChallengeRead,
    summary="Créer un nouveau challenge"
)
async def create_challenge(
        data: ChallengeCreate,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user),
):
    """Crée un nouveau challenge avec les données fournies par l'utilisateur connecté."""
    return await crud_challenge.add_new_challenge(session, data, current_user)


@router.post(
    "/{challenge_id}",
    response_model=ChallengeRead,
    summary="Récupérer un challenge par ID"
)
async def get_challenge_by_id(
        challenge_id: UUID,
        session: AsyncSession = Depends(get_session)
):
    """Récupère les informations détaillées d'un challenge spécifique."""
    return await crud_challenge.get_challenge_by_id(session=session, challenge_id=challenge_id)


@router.patch(
    "/update/{challenge_id}",
    response_model=ChallengeRead,
    summary="Mettre à jour un challenge"
)
async def update_challenge(
        challenge_id: UUID,
        data: ChallengeUpdate,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user),
):
    """Met à jour les informations d'un challenge tant qu'il n'a pas commencé."""
    return await crud_challenge.update_challenge(challenge_id, data, session, current_user)


@router.get(
    "/type/{challenge_type}",
    response_model=List[ChallengeRead],
    summary="Récupérer les challenges par type"
)
async def get_challenges_by_type_route(
        challenge_type: ChallengeType,
        session: AsyncSession = Depends(get_session),
):
    """Récupère tous les challenges d'un type spécifique (public, privé, etc.)."""
    return await get_challenges_by_type(session, challenge_type)


@router.get(
    "/my-challenges",
    response_model=List[ChallengeRead],
    summary="Récupérer mes challenges"
)
async def get_challenges_personal(
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user),
):
    """Récupère tous les challenges auxquels l'utilisateur connecté participe."""
    return await get_user_challenges(session, current_user.id)


@router.get(
    "/search",
    response_model=List[ChallengeRead],
    summary="Rechercher des challenges"
)
async def search_challenges(
        query: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        session: AsyncSession = Depends(get_session),
):
    """Recherche des challenges par mots-clés, statut et pagination."""
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


@router.get(
    "/{challenge_id}/full",
    summary="Récupérer un challenge avec médias et progression"
)
async def get_challenge_with_medias_details(
        challenge_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Récupère les détails complets d'un challenge incluant les médias et la progression de l'utilisateur."""
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


@router.get(
    "/admin/latest/full",
    summary="Récupérer les derniers challenges créés"
)
async def get_newest_challenges(
        session: AsyncSession = Depends(get_session),
        limit: int = Query(5, ge=1, le=50),
):
    """Récupère les challenges les plus récents avec leurs détails complets (limité à 50)."""
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
@router.post(
    "/join/{challenge_id}",
    summary="Rejoindre un challenge"
)
async def join_challenge(
        challenge_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user),
):
    """Permet à l'utilisateur connecté de rejoindre un challenge et gère les notifications pour les challenges privés."""
    challenge = await get_challenge_by_id(challenge_id, session)

    membership = await crud_challenge.join_challenge_by_ids(session, current_user.id, challenge_id)

    if membership is None:
        raise HTTPException(status_code=404, detail="Challenge introuvable")

    if challenge.challenge_type == ChallengeType.PRIVATE:
        await crud_notification.update_type_notification(
            session=session,
            challenge_id=challenge_id,
            invitee_id=current_user.id,
            notification_type=NotificationType.CHALLENGE_ACCEPTED
        )
        await crud_notification.mark_notification_challenge_as_read(
            session=session,
            challenge_id=challenge_id,
            user_id=current_user.id
        )

    return {"success": True, "membership_id": getattr(membership, "user_id", None)}


@router.put(
    "/{challenge_id}/progress",
    summary="Mettre à jour la progression"
)
async def update_user_progress(
        challenge_id: UUID,
        data: ChallengeProgressUpdate,
        session: AsyncSession = Depends(get_session),
        current_user=Depends(get_current_active_user)
):
    """Met à jour la progression de l'utilisateur connecté sur un challenge spécifique."""
    await crud_challenge_stats.update_progress(session=session, data=data, challenge_id=challenge_id,
                                               current_user=current_user)


@router.get(
    "/{challenge_id}/ranking",
    response_model=list[RankingMembership],
    summary="Récupérer le classement du challenge"
)
async def calculate_ranking_challenge(
        challenge_id: UUID,
        session: AsyncSession = Depends(get_session)
):
    """Calcule et retourne le classement des participants d'un challenge."""
    return await crud_challenge_stats.calculate_ranking_challenge(session, challenge_id)


@router.get(
    "/{challenge_id}/activities",
    response_model=List[ActivityChallenge],
    summary="Récupérer les activités du challenge"
)
async def read_challenge_activities(
        challenge_id: UUID,
        session: AsyncSession = Depends(get_session)
):
    """Récupère toutes les activités liées à un challenge spécifique."""
    return await crud_activity.get_challenge_activities(session, challenge_id)
