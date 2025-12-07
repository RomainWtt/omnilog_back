"""
CRUD operations for reviews/comments
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import func, or_, exists, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.crud.crud_review_utils import exclude_review_private, exclude_report_review
from app.db.models import Review, User, Media, ReviewReport, FriendshipStatus


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
        is_visible=True,
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
        .options(
            selectinload(Review.user),
            selectinload(Review.media),
            selectinload(Review.reports))
        .where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()
    return review


async def get_media_comments(
        session: AsyncSession,
        media_id: UUID,
        limit: int = 20,
        offset: int = 0,
        exclude_reported_by: Optional[UUID] = None,
        requesting_user_id: Optional[UUID] = None
) -> List[Review]:
    """
    Get all visible comments for a specific media with pagination

    Args:
        session: Database session
        media_id: Media ID
        limit: Maximum number of results
        offset: Number of results to skip
        exclude_reported_by: User ID to exclude their reported reviews
        requesting_user_id: ID of the requesting user (to filter private accounts)

    Returns:
        List of Review objects ordered by created_at desc
    """
    query = (
        select(Review)
        .options(
            selectinload(Review.user),
            selectinload(Review.media)
        )
        .where(Review.media_id == media_id)
        .where(Review.is_visible == True)
        .where(func.length(func.trim(Review.content)) > 0)
    )

    # Exclure les commentaires signalés par cet utilisateur
    query = await exclude_report_review(exclude_reported_by, query)

    # Exclure les commentaires qui ont été écrit par des utilisateur privé et donc les 2 utilisateur ne sont pas amis
    query = await exclude_review_private(query, requesting_user_id)

    query = query.order_by(Review.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_media_comments_count(
        session: AsyncSession,
        media_id: UUID,
        exclude_reported_by: Optional[UUID] = None,
        requesting_user_id: Optional[UUID] = None
) -> int:
    """
    Get count of visible comments for a specific media

    Args:
        session: Database session
        media_id: Media ID
        exclude_reported_by: User ID to exclude their reported reviews
        requesting_user_id: ID of the requesting user (to filter private accounts)

    Returns:
        Count of comments
    """
    query = (
        select(func.count(Review.id))
        .where(Review.media_id == media_id)
        .where(Review.is_visible == True)
        .where(func.length(func.trim(Review.content)) > 0)
    )

    query = await exclude_report_review(exclude_reported_by, query)

    query = await exclude_review_private(query, requesting_user_id)

    result = await session.execute(query)
    return result.scalar_one()


async def get_user_reviews(
        session: AsyncSession,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        rating_filter: Optional[int] = None,
        search_query: Optional[str] = None,
        sort_by: str = "recent"
) -> List[Review]:
    """
    Get all reviews created by a specific user with filtering and sorting.

    Args:
        session: Database session
        user_id: User ID
        limit: Maximum number of results
        offset: Number of results to skip
        rating_filter: Optional rating to filter by (1-5)
        search_query: Optional search text for content AND media title
        sort_by: Sort order ('recent', 'oldest', 'rating-high', 'rating-low')

    Returns:
        List of Review objects
    """
    stmt = (
        select(Review)
        .options(
            selectinload(Review.media),
            selectinload(Review.user),
            selectinload(Review.reports)
        )
        .where(Review.user_id == user_id, Review.is_visible == True)
    )

    # Filter by rating
    if rating_filter is not None:
        stmt = stmt.where(Review.rating == rating_filter)

    # Filter by search query (case-insensitive) - DANS LE CONTENU ET LE TITRE DU MÉDIA
    if search_query and search_query.strip():
        search_pattern = f"%{search_query.strip()}%"
        # Join avec Media pour rechercher dans le titre
        stmt = stmt.join(Media, Review.media_id == Media.id)
        stmt = stmt.where(
            or_(
                Review.content.ilike(search_pattern),
                Media.title.ilike(search_pattern),
                Media.original_title.ilike(search_pattern)
            )
        )

    # Apply sorting
    if sort_by == "recent":
        stmt = stmt.order_by(Review.created_at.desc())
    elif sort_by == "oldest":
        stmt = stmt.order_by(Review.created_at.asc())
    elif sort_by == "rating-high":
        stmt = stmt.order_by(Review.rating.desc(), Review.created_at.desc())
    elif sort_by == "rating-low":
        stmt = stmt.order_by(Review.rating.asc(), Review.created_at.desc())
    else:
        stmt = stmt.order_by(Review.created_at.desc())

    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
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


async def search_reviews_by_query(
        session: AsyncSession,
        query: str,
        limit: int = 20,
        offset: int = 0,
        is_reported: Optional[bool] = None
) -> list[Review]:
    stmt = (
        select(Review)
        .options(
            selectinload(Review.user),
            selectinload(Review.media),
            selectinload(Review.reports)
        )
        .outerjoin(User)
        .outerjoin(Media)
        .where(
            or_(
                Review.content.ilike(f"%{query}%"),
                User.username.ilike(f"%{query}%"),
                Media.title.ilike(f"%{query}%"),
                Media.original_title.ilike(f"%{query}%")
            )
        )
    )

    if is_reported is True:
        stmt = stmt.where(
            exists().where(ReviewReport.review_id == Review.id)
        )
    elif is_reported is False:
        stmt = stmt.where(
            ~exists().where(ReviewReport.review_id == Review.id)
        )

    stmt = stmt.order_by(Review.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


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
        .options(
            selectinload(Review.user),
            selectinload(Review.media)
        )
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
        .options(selectinload(Review.user), selectinload(Review.media))
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


async def get_media_average_rating_friend(
        session: AsyncSession,
        media_id: UUID,
        user_id: UUID
) -> Optional[float]:
    """
    Calculate the average rating for a media based on friends' reviews only.

    Args:
        session: Database session
        media_id: Media ID
        user_id: Current user ID to find their friends

    Returns:
        Average rating from friends as float or None if no ratings from friends
    """
    from app.db.models import Friendship

    friend_ids_subquery = (
        select(
            case(
                (Friendship.user_one_id == user_id, Friendship.user_two_id),
                (Friendship.user_two_id == user_id, Friendship.user_one_id),
            )
        )
        .where(
            Friendship.status == FriendshipStatus.ACCEPTED
        )
        .where(
            (Friendship.user_one_id == user_id) | (Friendship.user_two_id == user_id)
        )
        .distinct()
        .alias("friend_ids")
    )

    # Requête principale pour la moyenne des notes des amis
    result = await session.execute(
        select(func.avg(Review.rating))
        .where(Review.media_id == media_id)
        .where(Review.is_visible == True)
        .where(Review.rating.isnot(None))
        .where(Review.user_id.in_(select(friend_ids_subquery)))
    )
    avg = result.scalar_one()

    return float(avg) if avg is not None else None


async def toggle_is_report(
        session: AsyncSession,
        review_id: UUID
) -> bool:
    # Récupérer la review
    review = await session.get(Review, review_id)

    if not review:
        raise ValueError(f"Review {review_id} not found")

    # Toggle la valeur
    review.is_report = not review.is_report

    # Commit les changements
    await session.commit()
    await session.refresh(review)

    return review.is_report
