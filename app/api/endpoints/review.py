"""
API routes for reviews/comments
"""
from fastapi import APIRouter, Query, HTTPException, Depends, status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.review import (
    ReviewRead,
    ReviewCreate,
    ReviewUpdate,
    ReviewsPaginated,
    MediaAverageRating
)
from app.crud import crud_review
from app.db.session import get_session
from app.core.deps import get_current_user
from app.db.models import User

router = APIRouter()


# ============================================
# MEDIA-RELATED ROUTES (must come first to avoid conflicts)
# ============================================

@router.get("/media/{media_id}", response_model=ReviewsPaginated)
async def get_comments_for_media(
    media_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get paginated comments for a specific media with user information.

    Returns only visible comments ordered by most recent first.
    """
    offset = (page - 1) * 20

    comments = await crud_review.get_media_comments(
        session=session,
        media_id=media_id,
        limit=20,
        offset=offset,
    )

    total = await crud_review.get_media_comments_count(session, media_id)

    return {
        "results": [ReviewRead.model_validate(comment) for comment in comments],
        "page": page,
        "total": total,
        "pages": (total + 19) // 20,
        "source": "local"
    }


@router.get("/media/{media_id}/average", response_model=MediaAverageRating)
async def get_media_average_rating(
    media_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get the average rating for a specific media.

    Returns the average rating and total number of ratings.
    """
    average = await crud_review.get_media_average_rating(session, media_id)

    # Get count of ratings
    from sqlalchemy import func, select
    from app.db.models import Review

    result = await session.execute(
        select(func.count())
        .select_from(Review)
        .where(Review.media_id == media_id)
        .where(Review.is_visible == True)
        .where(Review.rating.isnot(None))
    )
    count = result.scalar_one()

    return {
        "media_id": media_id,
        "average_rating": average,
        "total_ratings": count
    }


@router.get("/media/{media_id}/user", response_model=ReviewRead)
async def get_current_user_review_for_media(
    media_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current user's review for a specific media.

    Returns 404 if the user hasn't reviewed this media yet.
    """
    review = await crud_review.get_user_review_for_media(
        session=session,
        user_id=current_user.id,
        media_id=media_id
    )

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You haven't reviewed this media yet"
        )

    return ReviewRead.model_validate(review)


# ============================================
# USER-RELATED ROUTES
# ============================================

@router.get("/user/{user_id}", response_model=ReviewsPaginated)
async def get_user_reviews(
    user_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get all reviews created by a specific user.

    Returns paginated results ordered by most recent first.
    """
    offset = (page - 1) * 20

    reviews = await crud_review.get_user_reviews(
        session=session,
        user_id=user_id,
        limit=20,
        offset=offset
    )

    # Count total reviews
    from sqlalchemy import func, select
    from app.db.models import Review

    result = await session.execute(
        select(func.count())
        .select_from(Review)
        .where(Review.user_id == user_id)
    )
    total = result.scalar_one()

    return {
        "results": [ReviewRead.model_validate(review) for review in reviews],
        "page": page,
        "total": total,
        "pages": (total + 19) // 20,
        "source": "local"
    }


# ============================================
# GENERAL ROUTES (static paths)
# ============================================

@router.get("/recent", response_model=list[ReviewRead])
async def get_recent_reviews(
    limit: int = Query(10, ge=1, le=50, description="Number of reviews to return"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get the most recent reviews across all media.

    Useful for displaying recent activity on the platform.
    """
    reviews = await crud_review.get_recent_reviews(
        session=session,
        limit=limit
    )

    return [ReviewRead.model_validate(review) for review in reviews]


# ============================================
# REVIEW CRUD ROUTES (generic {review_id} must come last)
# ============================================

@router.post("/", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def create_review(
    review_data: ReviewCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new review/comment for a media.

    - **rating**: Rating from 1-5 (required)
    - **content**: Review text (optional, max 5000 chars)
    - **media_id**: ID of the media being reviewed

    Users can only have one review per media.
    """
    # Check if user already reviewed this media
    existing_review = await crud_review.get_user_review_for_media(
        session=session,
        user_id=current_user.id,
        media_id=review_data.media_id
    )

    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this media. Use PUT to update your review."
        )

    review = await crud_review.create_review(
        session=session,
        user_id=current_user.id,
        media_id=review_data.media_id,
        rating=review_data.rating,
        content=review_data.content
    )

    return ReviewRead.model_validate(review)


@router.get("/{review_id}", response_model=ReviewRead)
async def get_review(
    review_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific review by ID.
    """
    review = await crud_review.get_review_by_id(session, review_id)

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    return ReviewRead.model_validate(review)


@router.put("/{review_id}", response_model=ReviewRead)
async def update_review(
    review_id: UUID,
    review_data: ReviewUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update your own review.

    You can update the content and/or rating.
    """
    review = await crud_review.get_review_by_id(session, review_id)

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    # Check if user owns this review
    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own reviews"
        )

    updated_review = await crud_review.update_review(
        session=session,
        review_id=review_id,
        content=review_data.content,
        rating=review_data.rating
    )

    return ReviewRead.model_validate(updated_review)


@router.delete("/{review_id}", response_model=ReviewRead)
async def delete_review(
    review_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Delete your own review (soft delete - sets is_visible to False).

    The review won't appear in public listings anymore but remains in database.
    Only the review owner can delete their review.
    """
    review = await crud_review.get_review_by_id(session, review_id)

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    # Check if user owns this review
    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own reviews"
        )

    deleted_review = await crud_review.delete_review(session, review_id)

    return ReviewRead.model_validate(deleted_review)


@router.patch("/{review_id}/hide", response_model=ReviewRead)
async def hide_review(
    review_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Hide a review (admin only or own review).

    Hidden reviews won't appear in public listings.
    """
    review = await crud_review.get_review_by_id(session, review_id)

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    # Only admins or review owner can hide
    if review.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only hide your own reviews"
        )

    hidden_review = await crud_review.hide_review(session, review_id)

    return ReviewRead.model_validate(hidden_review)


@router.patch("/{review_id}/unhide", response_model=ReviewRead)
async def unhide_review(
    review_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Unhide a review (admin only or own review).

    Makes a hidden review visible again.
    """
    review = await crud_review.get_review_by_id(session, review_id)

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    # Only admins or review owner can unhide
    if review.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only unhide your own reviews"
        )

    unhidden_review = await crud_review.unhide_review(session, review_id)

    return ReviewRead.model_validate(unhidden_review)