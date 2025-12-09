from datetime import datetime
from typing import List, Tuple
from uuid import UUID

from app.crud import crud_challenge, crud_media
from app.db.models import Media, ChallengeMembership, User, Challenge, UserMediaEntry, MediaType
from app.schemas.memberships import RankingMembership
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.tv import TVSeasonsSchema, EpisodeSchema


async def calculate_progress_for_media_weighted(session: AsyncSession, media: Media, user: User):
    """
    Calcule le pourcentage de progression pour un média spécifique.
    """
    result = await session.execute(
        select(UserMediaEntry)
        .where(UserMediaEntry.user_id == user.id, UserMediaEntry.media_id == media.id)
    )
    entry: UserMediaEntry = result.scalar_one_or_none()
    if not entry:
        return 0

    if media.media_type == MediaType.MOVIE:
        total_duration = media.runtime or 1
        progress_percentage = min(int(entry.timecode / total_duration * 100), 100)
    else:  # TV
        total_episodes = media.number_of_episodes or 1
        episodes_watched = entry.episodes_watched or 0

        # Calculer le pourcentage basé sur les épisodes
        progress_percentage = min(int(episodes_watched / total_episodes * 100), 100)

    return progress_percentage


import json
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


async def calculate_ranking_challenge(session: AsyncSession, challenge_id: UUID) -> List[RankingMembership]:
    """
    Calculate and return a ranking for a challenge based on completed media count from JSON field.
    """
    challenge = await session.get(Challenge, challenge_id)
    if not challenge:
        return []

    result = await session.execute(
        select(User, ChallengeMembership)
        .join(ChallengeMembership, User.id == ChallengeMembership.user_id)
        .where(ChallengeMembership.challenge_id == challenge_id)
    )
    members = result.all()

    # Nombre total de médias dans le challenge
    total_media_count = len(challenge.media_list) if challenge.media_list else 0

    # Préparer les données pour le ranking
    ranking_data = []
    for user, membership in members:
        completed_media = membership.completed_media or {}

        # Si c'est une string, la parser
        if isinstance(completed_media, str):
            completed_media = json.loads(completed_media)

        # Compter les médias avec status "completed"
        completed_count = sum(
            1 for media_data in completed_media.values()
            if isinstance(media_data, dict) and media_data.get("status") == "completed"
        )

        # Calculer le nombre total d'épisodes à regarder dans le challenge
        total_episodes = 0
        watched_episodes = 0

        for media_id, media_progress in completed_media.items():
            if not isinstance(media_progress, dict):
                continue

            media_type = media_progress.get("media_type")

            # Pour les séries, compter les épisodes
            if media_type == "tv":
                # Récupérer les infos de la série depuis challenge.media_list
                # (tu devras adapter selon ta structure exacte)
                current_season = media_progress.get("current_season", 0)
                current_episode = media_progress.get("current_episode", 0)

                # Ici, tu peux calculer le nombre total d'épisodes de la série
                # Pour simplifier, on compte juste les épisodes regardés
                watched_episodes += current_episode if current_season else 0

        ranking_data.append({
            "user": user,
            "membership": membership,
            "completed_count": completed_count,
            "watched_episodes": watched_episodes
        })

    # Trier par nombre de médias complétés (décroissant), puis par épisodes regardés
    ranking_data.sort(
        key=lambda x: (x["completed_count"], x["watched_episodes"]),
        reverse=True
    )

    # Construire la liste de RankingMembership avec les rangs
    ranking_list = []
    for rank, data in enumerate(ranking_data, start=1):
        ranking_list.append(
            RankingMembership(
                id=data["user"].id,
                username=data["user"].username,
                avatar_url=data["user"].avatar_url,
                completed_count=data["completed_count"],
                total_media_count=total_media_count,
                progress=data["membership"].progress,
                rank=rank
            )
        )

    return ranking_list


async def load_challenge_context(session: AsyncSession, user: User, media: Media):
    user_challenges = await crud_challenge.get_user_challenges(session, user.id)
    if not user_challenges:
        return None

    challenges_with_media = await crud_media.filter_challenges_by_media(user_challenges, media)
    if not challenges_with_media:
        return None

    # memberships
    challenge_ids = [c.id for c in challenges_with_media]
    result = await session.execute(
        select(ChallengeMembership)
        .where(
            ChallengeMembership.user_id == user.id,
            ChallengeMembership.challenge_id.in_(challenge_ids)
        )
    )
    memberships = result.scalars().all()
    membership_map = {m.challenge_id: m for m in memberships}
    if not memberships:
        return None

    # tous les tmdb ids
    all_tmdb_ids = list({
        tmdb_id
        for c in challenges_with_media
        for tmdb_id in c.media_list
    })

    result = await session.execute(
        select(Media).where(Media.tmdb_id.in_(all_tmdb_ids))
    )
    medias = result.scalars().all()
    media_map = {m.tmdb_id: m for m in medias}

    media_ids = [m.id for m in medias]
    result = await session.execute(
        select(UserMediaEntry).where(
            UserMediaEntry.user_id == user.id,
            UserMediaEntry.media_id.in_(media_ids)
        )
    )
    entries = result.scalars().all()
    entry_map = {e.media_id: e for e in entries}

    return {
        "challenges": challenges_with_media,
        "memberships": memberships,
        "membership_map": membership_map,
        "media_map": media_map,
        "entry_map": entry_map,
    }


async def calculate_progress_film(session: AsyncSession, media: Media, user: User):
    ctx = await load_challenge_context(session, user, media)
    if ctx is None:
        return []

    progress_results = []

    for challenge in ctx["challenges"]:
        membership = ctx["membership_map"].get(challenge.id)
        if not membership or not challenge.media_list:
            continue

        total_duration = 0
        total_viewed = 0
        completed_media = []

        for tmdb_id in challenge.media_list:
            media_item = ctx["media_map"].get(tmdb_id)
            if not media_item or media_item.media_type != MediaType.MOVIE:
                continue

            entry = ctx["entry_map"].get(media_item.id)
            media_duration = media_item.runtime
            viewed = entry.timecode if entry else 0

            total_duration += media_duration
            total_viewed += min(viewed, media_duration)

            if viewed >= media_duration * 0.95:
                completed_media.append(tmdb_id)

        membership.progress = int(total_viewed / total_duration * 100) if total_duration else 0
        membership.completed_media = completed_media
        membership.updated_at = datetime.utcnow()
        session.add(membership)

        progress_results.append({
            "challenge_id": challenge.id,
            "progress": membership.progress,
            "completed_media": completed_media
        })

    await session.commit()
    for m in ctx["memberships"]:
        await session.refresh(m)

    return progress_results


async def calculate_progress_serie(
        session: AsyncSession,
        media: Media,
        serie_details: TVSeasonsSchema,
        user: User
):
    ctx = await load_challenge_context(session, user, media)
    if ctx is None:
        return []

    progress_results = []

    for challenge in ctx["challenges"]:
        membership = ctx["membership_map"].get(challenge.id)
        if not membership or not challenge.media_list:
            continue

        total_episodes = sum(
            len(season.episodes or [])
            for season in serie_details.seasons.values()
        )
        if total_episodes == 0:
            continue

        entry = ctx["entry_map"].get(media.id)

        if entry and entry.current_season and entry.current_episode:
            user_season = entry.current_season
            user_episode = entry.current_episode

            episodes_before = sum(
                len(serie_details.seasons[s].episodes or [])
                for s in sorted(serie_details.seasons.keys(), key=int)
                if int(s) < user_season
            )
            episodes_seen_total = episodes_before + user_episode
        else:
            episodes_seen_total = 0

        episodes_seen_total = min(episodes_seen_total, total_episodes)
        progress_percentage = int(episodes_seen_total / total_episodes * 100)

        completed_media = (
            [media.tmdb_id] if episodes_seen_total >= total_episodes else []
        )

        membership.progress = progress_percentage
        membership.completed_media = completed_media
        membership.updated_at = datetime.utcnow()
        session.add(membership)

        progress_results.append({
            "challenge_id": challenge.id,
            "progress": progress_percentage,
            "completed_media": completed_media
        })

    await session.commit()
    for m in ctx["memberships"]:
        await session.refresh(m)

    return progress_results


def build_ranking(members: List[Tuple[User, ChallengeMembership]], total_media_count: int) -> List[RankingMembership]:
    """
    Build ranking based on number of completed media.
    """
    ranking = [
        RankingMembership(
            id=user.id,
            username=user.username,
            avatar_url=user.avatar_url,
            episode_number=len(cm.completed_media) if cm.completed_media else 0,
            total_episodes=total_media_count,
            progress=cm.progress or 0,
            rank=None,
        )
        for user, cm in members
    ]
    # Tri par nombre de médias complétés
    ranking.sort(key=lambda x: x.episode_number, reverse=True)

    # Attribuer les rangs (gérer les ex-aequo)
    for index, member in enumerate(ranking, start=1):
        member.rank = index

    return ranking
