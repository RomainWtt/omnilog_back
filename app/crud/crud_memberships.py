from datetime import datetime
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.models import User, ChallengeMembership


async def get_challenge_members(
    session: AsyncSession,
    challenge_id: UUID
) -> List[Tuple[User, ChallengeMembership]]:
    """
    Retourne les couples (User, ChallengeMembership) triés par date d'entrée.
    """
    result = await session.execute(
        select(User, ChallengeMembership)
        .join(ChallengeMembership, User.id == ChallengeMembership.user_id)
        .where(ChallengeMembership.challenge_id == challenge_id)
        .order_by(ChallengeMembership.joined_at.asc())
    )
    return result.all()


async def get_user_membership_by_challenge(
    session: AsyncSession,
    user_id: UUID,
    challenge_id: UUID
) -> Optional[ChallengeMembership]:
    """
    Retourne le membership d'un utilisateur dans un challenge,
    ou None s'il n'est pas membre.
    """
    result = await session.execute(
        select(ChallengeMembership)
        .where(
            ChallengeMembership.user_id == user_id,
            ChallengeMembership.challenge_id == challenge_id
        )
    )
    return result.scalar_one_or_none()

async def create_membership_by_ids(
    session: AsyncSession,
    user_id: UUID,
    challenge_id: UUID,
    is_admin: bool = False,
    progress: int = 0
) -> ChallengeMembership:

    now = datetime.utcnow()
    membership = ChallengeMembership(
        user_id=user_id,
        challenge_id=challenge_id,
        is_admin=is_admin,
        progress=progress,
        joined_at=now,
        updated_at=now
    )
    session.add(membership)
    await session.commit()
    await session.refresh(membership)
    return membership