from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select

from app.crud import crud_challenge, crud_media, crud_activity
from app.db.models import MediaType, ChallengeMembership, User, ActivityType
from app.schemas.challenge import ChallengeProgressUpdate
from app.schemas.memberships import RankingMembership



async def calculate_ranking_challenge(session: AsyncSession, challenge_id: UUID) -> list[RankingMembership]:
 # Précharge user et challenge avec leurs media_list
 result = await session.execute(
     select(ChallengeMembership)
     .options(
         joinedload(ChallengeMembership.user),
         joinedload(ChallengeMembership.challenge)
     )
     .where(ChallengeMembership.challenge_id == challenge_id)
 )
 memberships = result.scalars().all()

 ranking_list = []
 for m in memberships:
     media_list = m.challenge.media_list or []
     total_count = len(media_list)
     completed_media = m.completed_media or {}

     # Si completed_media est un string JSON, le convertir
     if isinstance(completed_media, str):
         import json
         completed_media = json.loads(completed_media)

     # Utiliser directement la progression déjà calculée et stockée
     progress = m.progress or 0

     completed_count = sum(
         1 for media in completed_media.values() if (
             media.get("status") == "completed" if isinstance(media, dict) else False
         )
     )

     ranking_list.append(RankingMembership(
         id=m.user_id,
         username=m.user.username if m.user else "Inconnu",
         avatar_url=m.user.avatar_url if m.user else None,
         completed_count=completed_count,
         total_media_count=total_count,
         progress=progress  # Utilise la valeur déjà en base
     ))

 # Tri décroissant et attribution des rangs
 ranking_list.sort(key=lambda r: r.progress or 0, reverse=True)
 for idx, r in enumerate(ranking_list, start=1):
     r.rank = idx

 return ranking_list

"""
async def update_progress(
    challenge_id: UUID,
    data: ChallengeProgressUpdate,
    session: AsyncSession,
    current_user=User
):
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

    await crud_activity.update_challenge_activities(
        session=session,
        current_user=current_user,
        challenge_id=challenge_id,
        data=data,
        old_status=old_status,
        old_progress=old_progress,
        new_progress=membership.progress,
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
        "ranking": ranking
    }
"""

def build_completed_media_entry(media, data: ChallengeProgressUpdate) -> dict:
    """
    Retourne le dict à stocker dans `completed_media` pour un média donné.
    """
    base = {
        "media_type": "movie" if media.media_type == MediaType.MOVIE else "tv",
        "tmdb_id": media.tmdb_id,
        "status": data.status or "watching",
        "last_updated": datetime.utcnow().isoformat()
    }

    if media.media_type == MediaType.TV:
        base.update({
            "current_season": data.current_season,
            "current_episode": data.current_episode
        })
    else:  # Movie
        base.update({
            "time_code": data.time_code
        })

    return base

async def update_progress(
    challenge_id: UUID,
    data: ChallengeProgressUpdate,
    session: AsyncSession,
    current_user: User,
):
    # Vérifier challenge
    challenge = await crud_challenge.get_challenge_by_id(session=session, challenge_id=challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    #Vérifier membre
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
    old_status = completed_media.get(media_id_str, {}).get("status")
    old_progress = membership.progress or 0

    completed_media[media_id_str] = build_completed_media_entry(media, data)
    membership.completed_media = completed_media
    flag_modified(membership, "completed_media")

    total_medias = len(challenge.media_list) if challenge.media_list else 0
    completed_count = sum(
        1 for m in completed_media.values() if m.get("status") == "completed"
    )
    membership.progress = int((completed_count / total_medias) * 100) if total_medias > 0 else 0
    membership.updated_at = datetime.utcnow()
    session.add(membership)
    await session.commit()
    await session.refresh(membership)

    # Gérer les activités médias et challenge
    await crud_activity.update_challenge_progress_activity(
        session=session,
        membership=membership
    )

    # Recalculer le classement
    ranking = await calculate_ranking_challenge(session, challenge_id)

    # Retourner le résultat
    return {
        "success": True,
        "user_progress": membership.progress,
        "completed_count": completed_count,
        "total_medias": total_medias,
        "media_progress": completed_media[media_id_str],
        "ranking": ranking
    }