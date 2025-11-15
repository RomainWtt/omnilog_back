from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from app.db.models import Genre, MediaType


async def get_genres_by_ids(
        session: AsyncSession,
        genre_ids: List[int],
) -> List[Genre]:
    """
    Get multiple genres by their TMDB IDs in a single query

    Args:
        session: Database session
        genre_ids: List of TMDB genre IDs

    Returns:
        List of Genre objects
    """
    if not genre_ids:
        return []

    result = await session.execute(
        select(Genre).where(
            Genre.id.in_(genre_ids)  # type: ignore
        )
    )
    return list(result.scalars().all())
