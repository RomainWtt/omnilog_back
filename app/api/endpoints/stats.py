"""
Add this to your existing library routes file (app/api/routes/library.py)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.crud.crud_user_stats import get_user_statistics
from app.db.models import User
from app.db.session import get_session
from app.schemas.stats import UserStatsRead

router = APIRouter()

@router.get("/my-stats", response_model=UserStatsRead)
async def get_my_statistics(
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Get comprehensive statistics for the current users

    Returns:
    - Total reviews and average rating
    - Watch time in hours
    - Top 5 favorite genres
    - Recent activity (this week, month, year)
    - Reviews per month (last 6 months)
    - Watchlist breakdown (total, movies, series, anime)
    """
    stats = await get_user_statistics(session, current_user.id)
    return UserStatsRead(**stats)