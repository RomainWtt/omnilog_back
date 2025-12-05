"""
CRUD operations for user statistics
"""
from datetime import datetime, timedelta
from typing import Dict, List
from uuid import UUID
from collections import defaultdict

from sqlalchemy import select, func, and_, case, cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserMediaEntry, Media, Review, ListStatus, MediaType


async def get_user_statistics(session: AsyncSession, user_id: UUID) -> Dict:
    """
    Get comprehensive user statistics

    Returns a dictionary with all user statistics:
    - Reviews (total, average rating, activity)
    - Watch time
    - Favorite genres
    - Library stats
    """

    # ============================================
    # 1. REVIEWS STATISTICS
    # ============================================

    # Count total reviews and calculate average rating
    review_stats_query = select(
        func.count(Review.id).label("total_reviews"),
        func.avg(Review.rating).label("average_rating")
    ).where(
        Review.user_id == user_id,
        Review.is_visible == True
    )

    review_stats_result = await session.execute(review_stats_query)
    review_stats = review_stats_result.first()

    total_reviews = review_stats.total_reviews or 0
    average_rating = float(review_stats.average_rating or 0)

    # ============================================
    # 2. RECENT ACTIVITY
    # ============================================

    now = datetime.utcnow()
    one_week_ago = now - timedelta(days=7)
    one_month_ago = now - timedelta(days=30)
    one_year_ago = now - timedelta(days=365)

    recent_activity_query = select(
        func.count(case((Review.created_at >= one_week_ago, 1))).label("this_week"),
        func.count(case((Review.created_at >= one_month_ago, 1))).label("this_month"),
        func.count(case((Review.created_at >= one_year_ago, 1))).label("this_year")
    ).where(
        Review.user_id == user_id,
        Review.is_visible == True
    )

    recent_activity_result = await session.execute(recent_activity_query)
    recent_activity = recent_activity_result.first()

    # ============================================
    # 3. MONTHLY ACTIVITY (Last 6 months)
    # ============================================

    # Get all reviews from the last 6 months
    six_months_ago = now - timedelta(days=180)

    monthly_reviews_query = select(Review).where(
        Review.user_id == user_id,
        Review.is_visible == True,
        Review.created_at >= six_months_ago
    )

    monthly_reviews_result = await session.execute(monthly_reviews_query)
    monthly_reviews = monthly_reviews_result.scalars().all()

    # Count reviews per month
    month_names = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
                   'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']

    reviews_per_month = []
    for i in range(5, -1, -1):  # Last 6 months
        target_date = datetime(now.year, now.month, 1) - timedelta(days=30 * i)
        month_name = month_names[target_date.month - 1]

        count = sum(1 for r in monthly_reviews
                    if r.created_at.month == target_date.month
                    and r.created_at.year == target_date.year)

        reviews_per_month.append({
            "month": month_name,
            "count": count
        })

    # ============================================
    # 4. LIBRARY STATISTICS
    # ============================================

    # Get all user's library entries with media info
    library_query = select(UserMediaEntry, Media).join(
        Media, UserMediaEntry.media_id == Media.id
    ).where(
        UserMediaEntry.user_id == user_id
    )

    library_result = await session.execute(library_query)
    library_entries = library_result.all()

    # ============================================
    # 5. WATCH TIME CALCULATION
    # ============================================

    total_minutes = 0
    genre_count: Dict[str, int] = defaultdict(int)

    # Watchlist counts
    watchlist_total = 0
    watchlist_movies = 0
    watchlist_series = 0
    watchlist_anime = 0

    # Status counts
    completed_count = 0
    watching_count = 0
    plan_to_watch_count = 0
    favorite_count = 0

    for entry, media in library_entries:
        # Status counts
        if entry.list_status == ListStatus.COMPLETED:
            completed_count += 1
        elif entry.list_status == ListStatus.WATCHING:
            watching_count += 1
        elif entry.list_status == ListStatus.PLAN_TO_WATCH:
            plan_to_watch_count += 1

        if entry.is_favorite:
            favorite_count += 1

        # Watchlist counts (plan_to_watch only)
        if entry.list_status == ListStatus.PLAN_TO_WATCH:
            watchlist_total += 1

            if media.media_type == MediaType.MOVIE:
                # Check if it's anime (genre 16)
                if media.genre_ids and 16 not in media.genre_ids:
                    watchlist_movies += 1
                else:
                    watchlist_anime += 1
            elif media.media_type == MediaType.TV:
                # Check if it's anime (genre 16)
                if media.genre_ids and 16 in media.genre_ids:
                    watchlist_anime += 1
                else:
                    watchlist_series += 1

        # Watch time calculation
        if media.runtime:
            total_minutes += media.runtime
        elif media.episode_run_time and media.number_of_episodes:
            # For series: average episode runtime × number of episodes
            avg_runtime = media.episode_run_time[0] if isinstance(media.episode_run_time,
                                                                  list) else media.episode_run_time
            total_minutes += avg_runtime * media.number_of_episodes

        # Genre counting
        if media.genre_ids:
            # Query actual genre names
            from app.db.models import Genre
            genre_query = select(Genre).where(
                Genre.id.in_(media.genre_ids),
                Genre.media_type == media.media_type
            )
            genre_result = await session.execute(genre_query)
            genres = genre_result.scalars().all()

            for genre in genres:
                genre_count[genre.name] += 1

    total_watch_time_hours = round(total_minutes / 60)

    # ============================================
    # 6. TOP GENRES (Top 5)
    # ============================================

    total_genre_count = sum(genre_count.values())
    favorite_genres = []

    if total_genre_count > 0:
        sorted_genres = sorted(genre_count.items(), key=lambda x: x[1], reverse=True)[:5]

        for genre_name, count in sorted_genres:
            percentage = round((count / total_genre_count) * 100, 1)
            favorite_genres.append({
                "name": genre_name,
                "count": count,
                "percentage": percentage
            })

    # ============================================
    # 7. BUILD RESPONSE
    # ============================================

    return {
        "total_reviews": total_reviews,
        "average_rating": round(average_rating, 1),
        "total_watch_time_hours": total_watch_time_hours,
        "favorite_genres": favorite_genres,
        "recent_activity": {
            "this_week": recent_activity.this_week or 0,
            "this_month": recent_activity.this_month or 0,
            "this_year": recent_activity.this_year or 0
        },
        "reviews_per_month": reviews_per_month,
        "watchlist_total": watchlist_total,
        "watchlist_movies": watchlist_movies,
        "watchlist_series": watchlist_series,
        "watchlist_anime": watchlist_anime,
        # Extended stats (optional)
        "completed_count": completed_count,
        "watching_count": watching_count,
        "plan_to_watch_count": plan_to_watch_count,
        "favorite_count": favorite_count
    }