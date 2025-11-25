from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Activity, ActivityType, Friendship

from uuid import UUID, uuid4


async def add_accept_friend(
        session: AsyncSession,
        users: Friendship,
) -> bool:
    activity = Activity(
        user_id=users.user_two_id,
        activity_type = ActivityType.FRIEND_ADDED,
        details = {"user_send_request_id": str(users.user_one_id)}
    )
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return True