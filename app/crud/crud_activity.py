from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Activity, ActivityType, Friendship, User, ChallengeMembership
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


async def delete_activity_by_id(session: AsyncSession, activity_id: UUID) -> bool:
    result = await session.execute(
        delete(Activity)
        .where(Activity.id == activity_id)
        .returning(Activity.id)
    )
    deleted = result.scalar_one_or_none()
    if deleted:
        await session.commit()
        return True
    return False


async def add_challenge_activity(
    session: AsyncSession,
    *,
    user_id: UUID,
    challenge_id: UUID,
    activity_type: ActivityType,
    timestamp: datetime | None = None,
    details: dict | None = None,
) -> Activity:
    activity = Activity(
        user_id=user_id,
        activity_type=activity_type,
        details={
            "challenge_id": str(challenge_id),
            "at": timestamp.isoformat() if timestamp else datetime.utcnow().isoformat(),
            **(details or {})
        },
    )
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return activity

# TODO je sais que join_challenge_activity doit etre rajouté qlq part ailleurs dans le code mais je ne sais plus où
async def join_challenge_activity(session: AsyncSession, user_id: UUID, challenge_id: UUID):
    """Créer une activité pour rejoindre le challenge."""
    await add_challenge_activity(
        session=session,
        user_id=user_id,
        challenge_id=challenge_id,
        activity_type=ActivityType.CHALLENGE_JOINED,
        timestamp=datetime.utcnow()
    )

async def leave_challenge_activity(session: AsyncSession, user_id: UUID, challenge_id: UUID):
    """Créer une activité pour quitter le challenge."""
    await add_challenge_activity(
        session=session,
        user_id=user_id,
        challenge_id=challenge_id,
        activity_type=ActivityType.CHALLENGE_LEFT,
        timestamp=datetime.utcnow()
    )

async def challenge_is_finished_activity(
    session: AsyncSession,
    user_id: UUID,
    challenge_id: UUID
):
    """Créer une activité indiquant que le challenge est terminé."""
    await add_challenge_activity(
        session=session,
        user_id=user_id,
        challenge_id=challenge_id,
        activity_type=ActivityType.CHALLENGE_FINISHED,
        timestamp=datetime.utcnow()
    )

async def update_challenge_progress_activity(
    session: AsyncSession,
    membership: ChallengeMembership
):
    """Met à jour ou crée une activité pour la progression complète du challenge."""
    completed_media = membership.completed_media or {}
    if isinstance(completed_media, str):
        import json
        completed_media = json.loads(completed_media)

    for media_id_str, media_data in completed_media.items():
        if media_data.get("status") == "completed":
            # Récupérer le média réel pour avoir le titre
            from app.crud import crud_media
            media = await crud_media.get_media_by_id(session=session, media_id=media_id_str)

            details = {
                "challenge_id": str(membership.challenge_id),
                "at": datetime.utcnow().isoformat(),
                "media_title": media.title if media else "Inconnu",
            }

            if media_data.get("media_type") == "tv":
                details["episode_number"] = media_data.get("current_episode")
                details["total_episodes"] = media_data.get("total_episodes")

            await add_challenge_activity(
                session=session,
                user_id=membership.user_id,
                challenge_id=membership.challenge_id,
                activity_type=ActivityType.CHALLENGE_COMPLETED_EPISODE,
                timestamp=datetime.utcnow(),
                details=details
            )

    if membership.progress == 100:
        await challenge_is_finished_activity(
            session=session,
            user_id=membership.user_id,
            challenge_id=membership.challenge_id
        )



async def get_challenge_activities(
        session: AsyncSession,
        challenge_id: UUID
) -> list[ActivityChallenge]:
    """Récupère toutes les activités liées à un challenge, avec infos utilisateur."""
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