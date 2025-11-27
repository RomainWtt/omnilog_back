from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.crud.ChallengeStatus import ChallengeStatus
from app.db.models import User
from app.db.session import get_session

from app.schemas.challenge import ChallengeCreate, ChallengeRead
from app.crud.crud_challenge import (
    get_challenge_by_id,
    list_last_five_challenges, add_new_challenge, search_challenges_details
)

router = APIRouter()

@router.post("/", response_model=ChallengeRead)
async def create_challenge(
    data: ChallengeCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await add_new_challenge(session, data, current_user.id)


@router.get("/{challenge_id}", response_model=ChallengeRead)
async def get_challenge( challenge_id: UUID, session: AsyncSession = Depends(get_session)):
    return await get_challenge_by_id(session, challenge_id)


@router.get("/latest/last5", response_model=list[ChallengeRead])
async def get_newest_challenges(session: AsyncSession = Depends(get_session)):
    return await list_last_five_challenges(session)


@router.get("/search", response_model=list[ChallengeRead])
async def search_challenges(
    query: Optional[str] = Query(None),
    status: Optional[ChallengeStatus] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    return await search_challenges_details(session, query=query, status=status)