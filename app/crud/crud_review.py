"""
CRUD operations for reviews/comments
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import func, delete
from uuid import UUID
from datetime import datetime

from app.db.models import Review, User
from sqlmodel import select


async def create_review(
        session: AsyncSession,
        user_id: UUID,
        media_id: UUID,
        rating: int,
        content: Optional[str] = None
) -> Review:
    """
    Create a new review/comment

    Args:
        session: Database session
        user_id: ID of the user creating the review
        media_id: ID of the media being reviewed
        rating: Rating from 1-5 (required)
        content: Review content (optional)

    Returns:
        The created Review object
    """
    review = Review(
        user_id=user_id,
        media_id=media_id,
        content=content,
        rating=rating,
        is_visible=True
    )

    session.add(review)
    await session.commit()
    await session.refresh(review)

    return review


async def get_review_by_id(
        session: AsyncSession,
        review_id: UUID
) -> Optional[Review]:
    """
    Get a review by its ID

    Args:
        session: Database session
        review_id: Review ID

    Returns:
        Review object or None if not found
    """
    result = await session.execute(
        select(Review)
        .options(selectinload(Review.user))
        .where(Review.id == review_id)
    )
    return result.scalar_one_or_none()


async def get_media_comments(
        session: AsyncSession,
        media_id: UUID,
        limit: int = 20,
        offset: int = 0
) -> List[Review]:
    """
    Get all visible comments for a specific media with pagination

    Args:
        session: Database session
        media_id: Media ID
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of Review objects ordered by created_at desc
    """
    result = await session.execute(
        select(Review)
        .options(selectinload(Review.user))
        .where(Review.media_id == media_id)
        .where(Review.is_visible == True)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_media_comments_count(
        session: AsyncSession,
        media_id: UUID
) -> int:
    """
    Get total count of visible comments for a media

    Args:
        session: Database session
        media_id: Media ID

    Returns:
        Total count of visible comments
    """
    result = await session.execute(
        select(func.count())
        .select_from(Review)
        .where(Review.media_id == media_id)
        .where(Review.is_visible == True)
    )
    return result.scalar_one()


async def get_user_reviews(
        session: AsyncSession,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0
) -> List[Review]:
    """
    Get all reviews created by a specific user

    Args:
        session: Database session
        user_id: User ID
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of Review objects
    """
    result = await session.execute(
        select(Review)
        .options(selectinload(Review.media))
        .where(Review.user_id == user_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_review(
        session: AsyncSession,
        review_id: UUID,
        content: Optional[str] = None,
        rating: Optional[int] = None
) -> Optional[Review]:
    """
    Update a review's content and/or rating

    Args:
        session: Database session
        review_id: Review ID
        content: New content (optional)
        rating: New rating (optional)

    Returns:
        Updated Review object or None if not found
    """
    review = await get_review_by_id(session, review_id)

    if not review:
        return None

    if content is not None:
        review.content = content

    if rating is not None:
        review.rating = rating

    review.updated_at = datetime.utcnow()

    session.add(review)
    await session.commit()
    await session.refresh(review)

    return review


async def delete_review(
        session: AsyncSession,
        review_id: UUID
) -> Optional[Review]:
    """
    Delete a review (soft delete by setting is_visible to False)
    User deletes their own review - it becomes hidden but stays in database

    Args:
        session: Database session
        review_id: Review ID

    Returns:
        Deleted Review object or None if not found
    """
    review = await get_review_by_id(session, review_id)

    if not review:
        return None

    review.is_visible = False
    review.updated_at = datetime.utcnow()

    session.add(review)
    await session.commit()
    await session.refresh(review)

    return review


async def hide_review(
        session: AsyncSession,
        review_id: UUID
) -> Optional[Review]:
    """
    Hide a review (soft delete by setting is_visible to False)

    Args:
        session: Database session
        review_id: Review ID

    Returns:
        Hidden Review object or None if not found
    """
    review = await get_review_by_id(session, review_id)

    if not review:
        return None

    review.is_visible = False
    review.updated_at = datetime.utcnow()

    session.add(review)
    await session.commit()
    await session.refresh(review)

    return review


async def unhide_review(
        session: AsyncSession,
        review_id: UUID
) -> Optional[Review]:
    """
    Unhide a review (set is_visible to True)

    Args:
        session: Database session
        review_id: Review ID

    Returns:
        Unhidden Review object or None if not found
    """
    review = await get_review_by_id(session, review_id)

    if not review:
        return None

    review.is_visible = True
    review.updated_at = datetime.utcnow()

    session.add(review)
    await session.commit()
    await session.refresh(review)

    return review


async def get_user_review_for_media(
        session: AsyncSession,
        user_id: UUID,
        media_id: UUID
) -> Optional[Review]:
    """
    Get a specific user's review for a specific media
    Useful to check if user already reviewed a media

    Args:
        session: Database session
        user_id: User ID
        media_id: Media ID

    Returns:
        Review object or None if not found
    """
    result = await session.execute(
        select(Review)
        .where(Review.user_id == user_id)
        .where(Review.media_id == media_id)
        .where(Review.is_visible == True)
    )
    return result.scalar_one_or_none()


async def get_user_visible_review_for_media(
        session: AsyncSession,
        user_id: UUID,
        media_id: UUID
) -> Optional[Review]:
    """
    Get a specific user's VISIBLE review for a specific media.
    Use this to check if user has an active review for this media.
    """
    result = await session.execute(
        select(Review)
        .options(selectinload(Review.user))
        .where(Review.user_id == user_id)
        .where(Review.media_id == media_id)
        .where(Review.is_visible == True)
    )
    return result.scalar_one_or_none()


async def get_media_average_rating(
        session: AsyncSession,
        media_id: UUID
) -> Optional[float]:
    """
    Calculate the average rating for a media

    Args:
        session: Database session
        media_id: Media ID

    Returns:
        Average rating as float or None if no ratings
    """
    result = await session.execute(
        select(func.avg(Review.rating))
        .where(Review.media_id == media_id)
        .where(Review.is_visible == True)
        .where(Review.rating.isnot(None))
    )
    avg = result.scalar_one()

    return float(avg) if avg is not None else None


async def get_recent_reviews(
        session: AsyncSession,
        limit: int = 10
) -> List[Review]:
    """
    Get the most recent reviews across all media

    Args:
        session: Database session
        limit: Maximum number of results

    Returns:
        List of recent Review objects
    """
    result = await session.execute(
        select(Review)
        .options(selectinload(Review.user), selectinload(Review.media))
        .where(Review.is_visible == True)
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
