from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models import User, ChallengeStatus
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


@router.get("/search", response_model=list[ChallengeRead])
async def search_challenges(
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    limit = 20
    offset = (page - 1) * limit

    clean_query = query.strip() if query else None
    if clean_query == "":
        clean_query = None

    parsed_status = None
    if status:
        try:
            parsed_status = ChallengeStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    return await search_challenges_details(
        session,
        query=clean_query,
        status=parsed_status,
        limit=limit,
        offset=offset,
    )



@router.get("/latest/last5", response_model=list[ChallengeRead])
async def get_newest_challenges(session: AsyncSession = Depends(get_session)):
    return await list_last_five_challenges(session)


@router.get("/{challenge_id}", response_model=ChallengeRead)
async def get_challenge( challenge_id: UUID, session: AsyncSession = Depends(get_session)):
    return await get_challenge_by_id(session, challenge_id)



