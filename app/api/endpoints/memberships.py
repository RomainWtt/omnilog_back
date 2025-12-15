from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.crud import crud_memberships, crud_challenge, crud_activity
from app.crud.crud_memberships import get_challenge_members, get_user_membership_by_challenge, create_membership_by_ids
from app.db.models import ChallengeMembership, User, Challenge, Activity, ActivityType
from app.db.session import get_session
from app.schemas.memberships import MembershipRead, RankingMembership
from app.schemas.user import UserRead

router = APIRouter()


@router.get("/{challenge_id}/members", response_model=List[MembershipRead])
async def list_challenge_members(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    members = await get_challenge_members(session, challenge_id)

    challenge = await session.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    members_data = [
        {
            "id": user.id,
            "challenge_id": challenge_id,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "is_admin": membership.is_admin,
            "progress": membership.progress or 0,
            "joined_at": membership.joined_at
        }
        for user, membership in members
    ]

    members_data.sort(key=lambda x: x["progress"], reverse=True)
    for index, member in enumerate(members_data, start=1):
        member["rank"] = index

    return [
        MembershipRead(**m)
        for m in members_data
    ]


@router.get("/{challenge_id}/members/total")
async def get_challenge_members_count(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(func.count(ChallengeMembership.user_id))
        .where(ChallengeMembership.challenge_id == challenge_id)
    )
    count = result.scalar_one()
    return {"challenge_id": str(challenge_id), "members_count": count}


@router.get("/memberships/me/{challenge_id}", response_model=Optional[MembershipRead])
async def get_my_membership_for_challenge(
    challenge_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    membership = await get_user_membership_by_challenge(session, current_user.id, challenge_id)
    if not membership:
        return None

    user = await session.get(User, membership.user_id)

    return MembershipRead(
        id=user.id,
        challenge_id=challenge_id,
        username=user.username,
        avatar_url=user.avatar_url,
        is_admin=membership.is_admin,
        progress=membership.progress,
        rank=None,  # pas calculé ici
        joined_at=membership.joined_at
    )


@router.get("/{challenge_id}/is-member")
async def check_user_is_member(
    challenge_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    membership = await get_user_membership_by_challenge(session, current_user.id, challenge_id)
    return {"is_member": membership is not None}


@router.delete("/{challenge_id}/leave")
async def leave_challenge(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    deleted = await crud_memberships.delete_membership_by_ids(session, current_user.id, challenge_id)
    if not deleted:
        raise HTTPException(404, "Vous n'êtes pas membre de ce challenge")

    return {"detail": "Vous avez quitté le challenge"}


@router.post("/{challenge_id}/invite", response_model=None, status_code=status.HTTP_201_CREATED)
async def invite_friend_to_challenge(
    challenge_id: UUID,
    friend_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_active_user)
):
    await crud_challenge.invite_friend_to_challenge(
        session=session,
        challenge_id=challenge_id,
        inviter_id=current_user.id,
        friend_id=friend_id
    )
    return {"detail": "Invitation envoyée"}


@router.delete("/{challenge_id}/invite", status_code=status.HTTP_204_NO_CONTENT)
async def refuse_invitation(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_active_user)
):
    await crud_challenge.remove_invitation(
        session=session,
        challenge_id=challenge_id,
        invitee_id=current_user.id
    )
    return
