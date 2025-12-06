# app/crud/crud_helpers.py
from typing import List, Tuple
from app.db.models import Media, ChallengeMembership, User
from app.schemas.memberships import RankingMembership
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_total_episodes_for_challenge(session: AsyncSession, challenge) -> int:
    """
    Somme du nombre d'épisodes de tous les médias du challenge.
    """
    if not challenge.media_list:
        return 0

    result = await session.execute(
        select(Media.number_of_episodes).where(Media.tmdb_id.in_(challenge.media_list))
    )
    media_episodes = result.scalars().all()
    return sum(e or 0 for e in media_episodes)


def build_ranking(members: List[Tuple[User, ChallengeMembership]], total_episodes: int) -> List[RankingMembership]:
    total_episodes = max(total_episodes, 1)  # jamais zéro
    ranking = [
        RankingMembership(
            id=user.id,
            username=user.username,
            avatar_url=user.avatar_url,
            episode_number=cm.progress or 0,
            total_episodes=total_episodes,
            rank=None,  # on calcule après tri
        )
        for user, cm in members
    ]
    ranking.sort(key=lambda x: x.episode_number, reverse=True)
    for index, member in enumerate(ranking, start=1):
        member.rank = index
    return ranking