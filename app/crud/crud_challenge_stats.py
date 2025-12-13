from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlmodel import select

from app.db.models import MediaType, Media, ChallengeMembership
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