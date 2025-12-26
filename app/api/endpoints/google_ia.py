from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.services.google_ia_service import google_service

router = APIRouter()


@router.get(
    "/",
    response_model=bool,
    summary="Vérifier la modération d'un commentaire"
)
async def check_message(
        comments: str = Query(..., min_length=1, description="Comments to check"),
        synopsis: str = Query(..., description="Synopsis to of media"),
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Vérifie si un commentaire est respectueux en utilisant Gemini AI avec le contexte du synopsis du média."""
    return google_service.check_comment(comments, synopsis)
