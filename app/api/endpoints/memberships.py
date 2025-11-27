from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_memberships import get_challenge_members, \
    get_all_challenge_member_counts
from app.db.models import ChallengeMembership
from app.db.session import get_session
from app.schemas.memberships import MembershipRead

router = APIRouter()



@router.get("/{challenge_id}/members", response_model=list[MembershipRead])
async def list_challenge_members(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    members = await get_challenge_members(session, challenge_id)
    return [
        MembershipRead(
            id=user.id,
            username=user.username,
            avatar_url=user.avatar_url,
            is_admin=cm.is_admin,
            progress=cm.progress,
            rank=cm.rank,
            joined_at=cm.joined_at
        )
        for user, cm in members
    ]


@router.get("/participants/counts")
async def get_count_memberships(
    session: AsyncSession = Depends(get_session)
):
    return await get_all_challenge_member_counts(session)