from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.models import User, ChallengeMembership


async def get_challenge_members(session: AsyncSession, challenge_id: UUID):
    result = await session.execute(
        select(User, ChallengeMembership)
        .join(ChallengeMembership, User.id == ChallengeMembership.user_id)
        .where(ChallengeMembership.challenge_id == challenge_id)
        .order_by(ChallengeMembership.joined_at.asc())
    )
    return result.all()




async def get_all_challenge_member_counts(session: AsyncSession) -> dict[str, int]:
    result = await session.execute(
        select(
            ChallengeMembership.challenge_id,
            func.count().label("count")
        )
        .group_by(ChallengeMembership.challenge_id)
    )
    return {str(challenge_id): count for challenge_id, count in result.all()}