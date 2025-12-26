from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_session
from app.db.models import Genre
from app.schemas.genre import GenreRead
from typing import List

router = APIRouter()


@router.get(
    "/",
    response_model=List[GenreRead],
    summary="Récupérer tous les genres"
)
async def get_all_genres(
    session: AsyncSession = Depends(get_session),
):
    """Récupère tous les genres disponibles dans la base de données, triés par nom."""
    try:
        result = await session.execute(select(Genre).order_by(Genre.name))
        genres = result.scalars().all()
        return list(genres)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching genres: {str(e)}"
        )
