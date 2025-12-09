from app.services.google_ia_service import google_service
import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.crud import crud_media, crud_genre
from app.db.models import MediaType, User
from app.db.session import get_session
from app.schemas.genre import GenreRead
from app.schemas.media import (
    MediaRead,
    MediaSearch
)
from app.schemas.tv import TVSeasonsSchema, SeasonSchema, EpisodeSchema
from app.services.redis_service import redis_service
from app.services.google_ia_service import google_service

router = APIRouter()


@router.get("/", response_model=bool)
async def check_message(
        comments: str = Query(..., min_length=1, description="Comments to check"),
        synopsis:str = Query(..., description="Synopsis to of media"),
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """
    Ask to gemini if the commentaire is respectfully or not
    """
    return google_service.check_comment(comments, synopsis)
