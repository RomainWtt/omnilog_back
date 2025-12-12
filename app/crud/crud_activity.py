from datetime import datetime
from uuid import UUID

from sqlalchemy import select, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Activity, ActivityType, Friendship, Challenge, ChallengeMembership, User
from app.schemas.activity import ActivityChallenge


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



async def add_join_challenge_activity(
    session: AsyncSession,
    membership: ChallengeMembership
) -> Activity:
    activity = Activity(
        user_id =membership.user_id,
        activity_type=ActivityType.CHALLENGE_JOINED,
        details={
            "challenge_id": str(membership.challenge_id),
            "joined_at": membership.joined_at.isoformat() if membership.joined_at else None
        }
    )
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return activity


async def get_challenge_activities(
        session: AsyncSession,
        challenge_id: UUID
) -> list[ActivityChallenge]:
    challenge_id_str = str(challenge_id)

    stmt = (
        select(Activity, User)
        .join(User, Activity.user_id == User.id)
        .where(Activity.details.isnot(None))
        .order_by(Activity.created_at.desc())
    )

    result = await session.execute(stmt)

    activities: list[ActivityChallenge] = []
    for activity, user in result:
        details = activity.details or {}

        if str(details.get("challenge_id")) == challenge_id_str:
            activities.append(ActivityChallenge(
                id=activity.id,
                type=activity.activity_type,
                username=user.username,
                avatar_url=user.avatar_url,
                timestamp=activity.created_at,
                episode_number=details.get("episode_number"),
                total_episodes=details.get("total_episodes"),
                media_title=details.get("media_title")
            ))

    return activities