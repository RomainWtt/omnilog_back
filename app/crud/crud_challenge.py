from datetime import datetime, timezone
from typing import Optional, Tuple, List
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, or_

from app.api.endpoints.media import get_media_by_tmdb_id
from app.crud import crud_media
from app.crud.crud_media import create_media
from app.crud.crud_memberships import get_challenge_members, get_user_membership_by_challenge, create_membership_by_ids  # <-- Import direct, pas depuis endpoints
from app.db.models import Challenge, ChallengeStatus, Media, ChallengeMembership, User, MediaType
from app.schemas.challenge import ChallengeCreate, ChallengeRead
from app.schemas.media import MediaRead


def _members_stats(members: List[Tuple[User, ChallengeMembership]]) -> Tuple[int, float]:
    """Return (members_total, average_progress)."""
    if not members:
        return 0, 0.0
    progresses = [m.progress or 0 for _, m in members]
    total = sum(progresses)
    avg = total / len(progresses) if progresses else 0.0
    return len(progresses), avg


def to_challenge_read(
    challenge: Challenge,
    members: Optional[List[Tuple[User, ChallengeMembership]]] = None,
    personal_user_id: Optional[UUID] = None,
) -> ChallengeRead:
    """Convert a Challenge SQLModel instance + optional members into a ChallengeRead schema."""
    members_total, average_progress = _members_stats(members or [])
    personal_progress = None  # par défaut si non membre
    if personal_user_id and members:
        for u, m in members:
            if u.id == personal_user_id:
                personal_progress = m.progress or 0
                break

    return ChallengeRead(
        id=challenge.id,
        creator_id=challenge.creator_id,
        name=challenge.name,
        description=challenge.description,
        challenge_type=challenge.challenge_type,
        avatar_url=challenge.avatar_url,
        start_date=challenge.start_date,
        end_date=challenge.end_date,
        media_list=challenge.media_list,
        created_at=challenge.created_at,
        updated_at=challenge.updated_at,
        members_total=members_total,
        average_progress=average_progress,
        personal_progress=personal_progress,
    )


async def add_new_challenge(session: AsyncSession, data: ChallengeCreate, current_user: User) -> ChallengeRead:
    challenge = Challenge(**data.dict(exclude={"media_list"}), creator_id=current_user.id)
    challenge.media_list = challenge.media_list or []

    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)

    for media_item in data.media_list or []:
        media_obj = await get_media_by_tmdb_id(
            session=session,
            tmdb_id=media_item.tmdb_id,
            media_type=media_item.media_type,
            current_user=current_user
        )

        if not media_obj:
            media_obj = await create_media(
                session=session,
                tmdb_id=media_obj.tmdb_id,
                media_type=media_obj.media_type,
                title=media_obj.title or "Unknown Title",
                original_title=media_obj.original_title,
                overview=media_obj.overview,
                poster_path=media_obj.poster_path,
                backdrop_path=media_obj.backdrop_path,
                release_date=media_obj.release_date,
                current_user=current_user
            )

        if media_obj.tmdb_id not in challenge.media_list:
            # ⚡ Réassigner la liste pour forcer la détection du changement
            challenge.media_list = challenge.media_list + [media_obj.tmdb_id]

    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)

    membership = await create_membership_by_ids(
        session=session,
        user_id=current_user.id,
        challenge_id=challenge.id,
        is_admin=True
    )

    return to_challenge_read(challenge, [(current_user, membership)])


async def get_challenge_by_id(session: AsyncSession, challenge_id: UUID) -> Optional[Challenge]:
    result = await session.execute(select(Challenge).where(Challenge.id == challenge_id))
    return result.scalar_one_or_none()


async def get_challenges_by_type(
    session: AsyncSession,
    challenge_type: str,
    limit: int = 20,
) -> List[ChallengeRead]:
    stmt = select(Challenge).where(Challenge.challenge_type == challenge_type).order_by(Challenge.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    challenges = result.scalars().all()

    out: List[ChallengeRead] = []
    for challenge in challenges:
        members = await get_challenge_members(session, challenge.id)
        out.append(to_challenge_read(challenge, members))
    return out



async def get_challenge_with_medias(
    session: AsyncSession,
    challenge_id: UUID,
    personal_user_id: Optional[UUID] = None,
) -> Optional[dict]:

    challenge = await get_challenge_by_id(session, challenge_id)
    if not challenge:
        return None

    medias: List[MediaRead] = []

    if challenge.media_list:
        for tmdb_id in challenge.media_list:
            media_data: Optional[MediaRead] = None

            # Vérifie la DB pour MOVIE et TV
            for media_type in (MediaType.MOVIE, MediaType.TV):
                media_obj = await crud_media.get_media_by_tmdb_id(
                    session, tmdb_id, media_type
                )
                if media_obj:
                    media_data = MediaRead.model_validate(media_obj)
                    break

            # Si absent en DB, fetch via TMDB
            if not media_data:
                for media_type in (MediaType.MOVIE, MediaType.TV):
                    try:
                        media_data = await crud_media.get_media_by_tmdb_id(
                            tmdb_id, media_type, fetch_tmdb_if_missing=True
                        )
                        if media_data:
                            break
                    except Exception as e:
                        print(f"TMDB fetch failed for {tmdb_id} ({media_type}): {e}")

            if media_data:
                medias.append(media_data)
            else:
                print(f"Media {tmdb_id} not found in DB or TMDB")

    members = await get_challenge_members(session, challenge.id)

    return {
        "challenge": to_challenge_read(challenge, members, personal_user_id),
        "medias": medias
    }


async def get_user_challenges(session: AsyncSession, user_id: UUID) -> List[ChallengeRead]:
    """
        Return list of ChallengeRead for all challenges that the user has joined.
    """
    stmt = (
        select(Challenge)
        .join(ChallengeMembership, Challenge.id == ChallengeMembership.challenge_id)
        .where(ChallengeMembership.user_id == user_id)
        .order_by(Challenge.created_at.desc())
    )
    result = await session.execute(stmt)
    challenges = result.scalars().all()

    out: List[ChallengeRead] = []
    for challenge in challenges:
        members = await get_challenge_members(session, challenge.id)
        out.append(to_challenge_read(challenge, members, personal_user_id=user_id))
    return out


async def search_challenges_details(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    query: Optional[str] = None,
    status: Optional[ChallengeStatus] = None
) -> list[Challenge]:

    stmt = select(Challenge)
    conditions = []

    if query:
        pattern = f"%{query}%"
        conditions.append(
            or_(
                Challenge.name.ilike(pattern),
                Challenge.description.ilike(pattern)
            )
        )

    now = datetime.utcnow()
    if status and status != ChallengeStatus.TOUS:
        if status == ChallengeStatus.A_VENIR:
            conditions.append(Challenge.start_date > now)

        elif status == ChallengeStatus.EN_COURS:
            conditions.append(
                and_(
                    Challenge.start_date <= now,
                    Challenge.end_date >= now
                )
            )

        elif status == ChallengeStatus.TERMINE:
            conditions.append(Challenge.end_date < now)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(Challenge.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    return result.scalars().all()


async def update_challenge_avatar(
    session: AsyncSession,
    challenge_id: UUID,
    avatar_url: Optional[str],
) -> Optional[ChallengeRead]:
    """Update challenge avatar URL and return updated ChallengeRead or None if not found."""
    challenge = await get_challenge_by_id(session, challenge_id)
    if not challenge:
        return None

    challenge.avatar_url = avatar_url
    challenge.updated_at = func.now()

    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)

    members = await get_challenge_members(session, challenge.id)
    return to_challenge_read(challenge, members)


async def join_challenge_by_ids(session: AsyncSession, user_id: UUID, challenge_id: UUID) -> ChallengeMembership:
    existing = await get_user_membership_by_challenge(session, user_id, challenge_id)
    if existing:
        return existing

    membership = await create_membership_by_ids(session, user_id, challenge_id)
    return membership


async def list_newest_challenges_with_details(
    session: AsyncSession,
    limit: int = 5,
) -> List[ChallengeRead]:
    """
    Return newest challenges converted to ChallengeRead (with members stats).
    """
    result = await session.execute(select(Challenge).order_by(Challenge.created_at.desc()).limit(limit))
    challenges = result.scalars().all()

    full_challenges: List[ChallengeRead] = []
    for challenge in challenges:
        members = await get_challenge_members(session, challenge.id)
        full_challenges.append(to_challenge_read(challenge, members))
    return full_challenges

