from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlmodel import select

from app.db.models import MediaType, Media, ChallengeMembership
from app.schemas.challenge import ChallengeProgressUpdate
from app.schemas.memberships import RankingMembership



async def compute_media_progress(media: Media, data: ChallengeProgressUpdate) -> dict:
    if media.media_type == MediaType.MOVIE:
        runtime = media.runtime or 1
        viewed = data.time_code or 0

        progress = int(min(viewed / runtime, 1) * 100)
        status = "completed" if progress == 100 else "watching"

        return {
            "progress": progress,
            "status": status,
            "time_code": viewed
        }

    elif media.media_type == MediaType.TV:
        total_eps = media.number_of_episodes or 1
        current_episode = data.current_episode or 0

        progress = int(min(current_episode / total_eps, 1) * 100)
        status = "completed" if progress == 100 else "watching"

        return {
            "progress": progress,
            "status": status,
            "current_season": data.current_season,
            "current_episode": current_episode
        }

    return {"progress": 0, "status": "watching"}

async def calculate_ranking_challenge(session: AsyncSession, challenge_id: UUID) -> list[RankingMembership]:
    # Précharge user et challenge avec leurs media_list
    result = await session.execute(
        select(ChallengeMembership)
        .options(
            joinedload(ChallengeMembership.user),
            joinedload(ChallengeMembership.challenge)  # Assurez-vous que media_list est eager load
        )
        .where(ChallengeMembership.challenge_id == challenge_id)
    )
    memberships = result.scalars().all()

    ranking_list = []
    for m in memberships:
        total_count = len(m.challenge.media_list) if m.challenge and m.challenge.media_list else 0
        completed_media = m.completed_media or {}

        if completed_media and total_count > 0:
            progress = int(
                round(sum(media.get("progress", 0) for media in completed_media.values()) / total_count)
            )
        else:
            progress = 0

        completed_count = sum(1 for media in completed_media.values() if media.get("status") == "completed")

        ranking_list.append(RankingMembership(
            id=m.user_id,
            username=m.user.username if m.user else "Inconnu",
            avatar_url=m.user.avatar_url if m.user else None,
            completed_count=completed_count,
            total_media_count=total_count,
            progress=progress
        ))

    # Tri décroissant sur progress
    ranking_list.sort(key=lambda r: r.progress or 0, reverse=True)

    # Attribution des rangs
    for idx, r in enumerate(ranking_list, start=1):
        r.rank = idx

    return ranking_list