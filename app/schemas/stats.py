"""
Schemas for user statistics
"""
from pydantic import BaseModel
from typing import List, Optional


class GenreStats(BaseModel):
    """Statistics for a single genre"""
    name: str
    count: int
    percentage: float


class MonthlyActivity(BaseModel):
    """Review activity for a single month"""
    month: str  # Format: "Jan", "Fév", etc.
    count: int


class RecentActivity(BaseModel):
    """Recent review activity"""
    this_week: int
    this_month: int
    this_year: int


class UserStatsRead(BaseModel):
    """Comprehensive user statistics"""
    # Reviews
    total_reviews: int
    average_rating: float

    # Watch time
    total_watch_time_hours: int

    # Genres
    favorite_genres: List[GenreStats]

    # Activity
    recent_activity: RecentActivity
    reviews_per_month: List[MonthlyActivity]

    # Library counts (from existing endpoint)
    watchlist_total: int
    watchlist_movies: int
    watchlist_series: int
    watchlist_anime: int


class UserStatsDetailed(UserStatsRead):
    """Extended statistics with additional data"""
    # Could add more detailed stats in the future
    completed_count: int
    watching_count: int
    plan_to_watch_count: int
    favorite_count: int