from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_

from app.crud.ChallengeStatus import ChallengeStatus
from app.db.models import Challenge, User, ChallengeMembership
from app.schemas.challenge import ChallengeCreate


async def add_new_challenge(session: AsyncSession, data: ChallengeCreate, creator_id: UUID) -> Challenge:
    challenge_dict = data.dict()
    challenge_dict['creator_id'] = creator_id
    challenge = Challenge(**challenge_dict)
    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)
    return challenge


async def get_challenge_by_id(session: AsyncSession, challenge_id: UUID) -> Challenge | None:
    result = await session.execute(
        select(Challenge).where(Challenge.id == challenge_id)
    )
    return result.scalar_one_or_none()


async def list_last_five_challenges(session: AsyncSession) -> list[Challenge]:
    result = await session.execute(
        select(Challenge)
        .order_by(Challenge.created_at.desc())
        .limit(5)
    )
    return result.scalars().all()


async def search_challenges_details(
        session: AsyncSession,
        query: Optional[str] = None,
        status: Optional[ChallengeStatus] = None
) -> list[Challenge]:
    stmt = select(Challenge)

    if query:
        like_pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Challenge.name.ilike(like_pattern),
                Challenge.description.ilike(like_pattern)
            )
        )

    now = datetime.now(timezone.utc)
    if status and status != ChallengeStatus.TOUS:
        if status == ChallengeStatus.A_VENIR:
            stmt = stmt.where(Challenge.start_date > now)
        elif status == ChallengeStatus.EN_COURS:
            stmt = stmt.where(
                Challenge.start_date <= now,
                Challenge.end_date >= now
            )
        elif status == ChallengeStatus.TERMINE:
            stmt = stmt.where(Challenge.end_date < now)

    stmt = stmt.order_by(Challenge.created_at.desc())

    result = await session.execute(stmt)
    return  result.scalars().all()