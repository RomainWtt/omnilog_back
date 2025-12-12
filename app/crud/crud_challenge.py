from datetime import datetime, timezone
from typing import Optional, Tuple, List, cast
from uuid import UUID

from fastapi import HTTPException

from sqlalchemy import func, update, delete, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, or_

from app.api.endpoints.media import get_media_by_tmdb_id
from app.crud import crud_media, crud_memberships, crud_friendship, crud_activity
from app.crud.crud_media import create_media
from app.db.models import Challenge, ChallengeStatus, Media, ChallengeMembership, User, MediaType, ChallengeType, \
    Notification, NotificationType
from app.schemas.challenge import ChallengeCreate, ChallengeRead, ChallengeUpdate
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
    members_total, average_progress = _members_stats(members or [])
    personal_progress = None
    if personal_user_id and members:
        for u, m in members:
            if u.id == personal_user_id:
                personal_progress = m.progress or 0
                break

    # Transformation media_list
    media_list = []
    if challenge.media_list:
        for item in challenge.media_list:
            # Si item est un int, on peut construire un dict par défaut
            if isinstance(item, int):
                media_list.append({"tmdb_id": item, "media_type": "movie"})
            elif isinstance(item, dict):
                media_list.append(item)

    return ChallengeRead(
        id=challenge.id,
        creator_id=challenge.creator_id,
        name=challenge.name,
        description=challenge.description,
        challenge_type=challenge.challenge_type,
        avatar_url=challenge.avatar_url,
        start_date=challenge.start_date,
        end_date=challenge.end_date,
        media_list=media_list,
        created_at=challenge.created_at,
        updated_at=challenge.updated_at,
        members_total=members_total,
        average_progress=average_progress,
        personal_progress=personal_progress,
    )



async def add_new_challenge(
    session: AsyncSession,
    data: ChallengeCreate,
    current_user: User
) -> ChallengeRead:

    challenge = Challenge(**data.dict(exclude={"media_list"}), creator_id=current_user.id)
    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)

    media_list = []

    for media_item in data.media_list or []:
        tmdb_id = media_item["tmdb_id"]
        media_type = media_item["media_type"]
        if isinstance(media_type, str):
            media_type = MediaType(media_type)

        media_obj = await get_media_by_tmdb_id(
            session=session,
            tmdb_id=tmdb_id,
            media_type=media_type,
            current_user=current_user
        )

        if not media_obj:
            media_obj = await create_media(
                session=session,
                tmdb_id=tmdb_id,
                media_type=media_type,
                title=media_item.get("title") or "Unknown Title",
                original_title=media_item.get("original_title"),
                overview=media_item.get("overview"),
                poster_path=media_item.get("poster_path"),
                backdrop_path=media_item.get("backdrop_path"),
                release_date=media_item.get("release_date"),
                current_user=current_user
            )

        media_list.append({"tmdb_id": tmdb_id, "media_type": media_type.value})

    await session.execute(
        update(Challenge)
        .where(Challenge.id == challenge.id)
        .values(media_list=media_list)
    )

    await session.commit()
    await session.refresh(challenge)

    membership = await crud_memberships.create_membership_by_ids(
        session=session,
        user_id=current_user.id,
        challenge_id=challenge.id,
        is_admin=True
    )
    await crud_activity.add_join_challenge_activity(session, membership)
    return to_challenge_read(challenge, [(current_user, membership)])


async def get_challenge_by_id(session: AsyncSession, challenge_id: UUID) -> Optional[Challenge]:
    result = await session.execute(select(Challenge).where(Challenge.id == challenge_id))
    return result.scalar_one_or_none()


async def get_challenges_by_type(
    session: AsyncSession,
    challenge_type: str,
    limit: int = 20,
) -> List[ChallengeRead]:
    from app.crud import crud_memberships
    stmt = select(Challenge).where(Challenge.challenge_type == challenge_type).order_by(Challenge.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    challenges = result.scalars().all()

    out: List[ChallengeRead] = []
    for challenge in challenges:
        members = await crud_memberships.get_challenge_members(session, challenge.id)
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
        for item in challenge.media_list:
            tmdb_id = item.get("tmdb_id")
            media_type = item.get("media_type")

            if tmdb_id is None:
                continue

            # conversion string -> enum
            try:
                media_type_enum = MediaType(media_type)
            except Exception:
                media_type_enum = MediaType.MOVIE

            # lookup DB
            media_obj = await crud_media.get_media_by_tmdb_id(
                session=session,
                tmdb_id=tmdb_id,
                media_type=media_type_enum
            )

            if media_obj:
                medias.append(MediaRead.model_validate(media_obj))
            else:
                print(f"[WARN] Media not found for tmdb_id={tmdb_id}, type={media_type}")

    members = await crud_memberships.get_challenge_members(session, challenge.id)

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
        members = await crud_memberships.get_challenge_members(session, challenge.id)
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

    members = await crud_memberships.get_challenge_members(session, challenge.id)
    return to_challenge_read(challenge, members)


async def update_challenge(
    challenge_id: UUID,
    data: ChallengeUpdate,
    session: AsyncSession,
    current_user: User
) -> ChallengeRead:
    challenge = await get_challenge_by_id(session, challenge_id)

    if challenge.creator_id != current_user.id:
        raise HTTPException(403, "Seul le créateur peut modifier ce challenge")

    if challenge.start_date and challenge.start_date <= datetime.utcnow():
        raise HTTPException(400, "Impossible de modifier un challenge déjà commencé")


    for field, value in data.dict(exclude_unset=True).items():
        setattr(challenge, field, value)

    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)

    members = await crud_memberships.get_challenge_members(session, challenge.id)
    return to_challenge_read(challenge, members)


async def join_challenge_by_ids(session: AsyncSession, user_id: UUID, challenge_id: UUID) -> ChallengeMembership:
    existing = await crud_memberships.get_user_membership_by_challenge(session, user_id, challenge_id)
    if existing:
        return existing

    membership = await crud_memberships.create_membership_by_ids(session, user_id, challenge_id)
    await crud_activity.add_join_challenge_activity(session, membership)
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
        members = await crud_memberships.get_challenge_members(session, challenge.id)
        full_challenges.append(to_challenge_read(challenge, members))
    return full_challenges


async def invite_friend_to_challenge(session: AsyncSession, challenge_id: UUID, inviter_id: UUID, friend_id: UUID):
    challenge = await get_challenge_by_id(session, challenge_id)
    if not challenge:
        raise HTTPException(404, "Challenge introuvable")

    inviter_membership = await crud_memberships.get_user_membership_by_challenge(session, inviter_id, challenge_id)
    if not inviter_membership or not inviter_membership.is_admin:
        raise HTTPException(403, "Seul un administrateur peut inviter un ami")

    friendship_map = await crud_friendship.check_friendship_status(session, inviter_id, [friend_id])
    if not friendship_map.get(friend_id):
        raise HTTPException(400, "Vous n’êtes pas ami avec cet utilisateur")

    # Créer notification seulement
    notification = Notification(
        user_id=friend_id,
        actor_id=inviter_id,
        notification_type=NotificationType.CHALLENGE,
        data={
            "challenge_id": str(challenge.id),
            "challenge_name": challenge.name,
            "message": f"{inviter_membership.user.username} vous a invité au challenge '{challenge.name}'"
        },
        read=False,
        created_at=datetime.utcnow()
    )
    session.add(notification)
    await (session.commit())

async def remove_invitation(
    session: AsyncSession,
    challenge_id: UUID,
    invitee_id: UUID
) -> None:
    """
    Supprime une invitation à un challenge.
    """
    stmt = (
        delete(Notification)
        .where(
            and_(
                Notification.user_id == invitee_id,
                Notification.notification_type == NotificationType.CHALLENGE,
                cast(Notification.data["challenge_id"], String) == str(challenge_id)
            )
        )
    )
    await session.execute(stmt)
    await session.commit()