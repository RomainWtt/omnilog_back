"""
Tests for review CRUD operations
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_user, crud_media, crud_review
from app.db.models import MediaType
from uuid import uuid4


@pytest.mark.asyncio
async def test_create_review(session: AsyncSession):
    """Test creating a review/comment"""
    user = await crud_user.create_user(
        session=session,
        email="reviewer@example.com",
        username="reviewer",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=550,
        media_type=MediaType.MOVIE,
        title="Fight Club"
    )

    review = await crud_review.create_review(
        session=session,
        user_id=user.id,
        media_id=media.id,
        content="Amazing movie!",
        rating=5
    )

    assert review.content == "Amazing movie!"
    assert review.rating == 5
    assert review.user_id == user.id
    assert review.media_id == media.id
    assert review.is_visible is True
    assert review.id is not None


@pytest.mark.asyncio
async def test_create_review_without_rating(session: AsyncSession):
    """Test creating a review without rating (only comment)"""
    user = await crud_user.create_user(
        session=session,
        email="commenter@example.com",
        username="commenter",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=551,
        media_type=MediaType.MOVIE,
        title="Test Movie"
    )

    review = await crud_review.create_review(
        session=session,
        user_id=user.id,
        media_id=media.id,
        content="Great film but no rating yet",
        rating=None
    )

    assert review.content == "Great film but no rating yet"
    assert review.rating is None


@pytest.mark.asyncio
async def test_get_media_comments(session: AsyncSession):
    """Test getting all comments for a media with pagination"""
    user = await crud_user.create_user(
        session=session,
        email="user1@example.com",
        username="user1",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=600,
        media_type=MediaType.MOVIE,
        title="Popular Movie"
    )

    # Create multiple reviews
    for i in range(5):
        await crud_review.create_review(
            session=session,
            user_id=user.id,
            media_id=media.id,
            content=f"Comment {i}",
            rating=i + 1
        )

    # Get all comments
    comments = await crud_review.get_media_comments(
        session=session,
        media_id=media.id,
        limit=10,
        offset=0
    )

    assert len(comments) == 5
    # Should be ordered by created_at desc (most recent first)
    assert comments[0].content == "Comment 4"


@pytest.mark.asyncio
async def test_get_media_comments_pagination(session: AsyncSession):
    """Test pagination of comments"""
    user = await crud_user.create_user(
        session=session,
        email="paguser@example.com",
        username="paguser",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=601,
        media_type=MediaType.MOVIE,
        title="Movie with Many Comments"
    )

    # Create 25 reviews
    for i in range(25):
        await crud_review.create_review(
            session=session,
            user_id=user.id,
            media_id=media.id,
            content=f"Comment {i}"
        )

    # Get first page (20 items)
    page1 = await crud_review.get_media_comments(
        session=session,
        media_id=media.id,
        limit=20,
        offset=0
    )
    assert len(page1) == 20

    # Get second page (5 items)
    page2 = await crud_review.get_media_comments(
        session=session,
        media_id=media.id,
        limit=20,
        offset=20
    )
    assert len(page2) == 5


@pytest.mark.asyncio
async def test_get_media_comments_only_visible(session: AsyncSession):
    """Test that only visible comments are returned"""
    user = await crud_user.create_user(
        session=session,
        email="visuser@example.com",
        username="visuser",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=602,
        media_type=MediaType.MOVIE,
        title="Movie"
    )

    # Create visible review
    visible_review = await crud_review.create_review(
        session=session,
        user_id=user.id,
        media_id=media.id,
        content="Visible comment"
    )

    # Create hidden review
    hidden_review = await crud_review.create_review(
        session=session,
        user_id=user.id,
        media_id=media.id,
        content="Hidden comment"
    )
    # Hide it
    hidden_review.is_visible = False
    session.add(hidden_review)
    await session.commit()

    # Get comments
    comments = await crud_review.get_media_comments(
        session=session,
        media_id=media.id
    )

    assert len(comments) == 1
    assert comments[0].content == "Visible comment"


@pytest.mark.asyncio
async def test_get_media_comments_with_user_info(session: AsyncSession):
    """Test that user relationship is loaded correctly"""
    user = await crud_user.create_user(
        session=session,
        email="userinfo@example.com",
        username="userinfo",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=603,
        media_type=MediaType.MOVIE,
        title="Movie"
    )

    await crud_review.create_review(
        session=session,
        user_id=user.id,
        media_id=media.id,
        content="Comment with user"
    )

    comments = await crud_review.get_media_comments(
        session=session,
        media_id=media.id
    )

    assert len(comments) == 1
    assert comments[0].user is not None
    assert comments[0].user.username == "userinfo"
    assert comments[0].user.id == user.id


@pytest.mark.asyncio
async def test_get_media_comments_count(session: AsyncSession):
    """Test counting visible comments for a media"""
    user = await crud_user.create_user(
        session=session,
        email="countuser@example.com",
        username="countuser",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=604,
        media_type=MediaType.MOVIE,
        title="Movie"
    )

    # Create 10 visible reviews
    for i in range(10):
        await crud_review.create_review(
            session=session,
            user_id=user.id,
            media_id=media.id,
            content=f"Comment {i}"
        )

    # Create 2 hidden reviews
    for i in range(2):
        review = await crud_review.create_review(
            session=session,
            user_id=user.id,
            media_id=media.id,
            content=f"Hidden {i}"
        )
        review.is_visible = False
        session.add(review)
    await session.commit()

    count = await crud_review.get_media_comments_count(
        session=session,
        media_id=media.id
    )

    assert count == 10  # Only visible ones


@pytest.mark.asyncio
async def test_get_media_comments_empty(session: AsyncSession):
    """Test getting comments for media with no comments"""
    media = await crud_media.create_media(
        session=session,
        tmdb_id=605,
        media_type=MediaType.MOVIE,
        title="Movie Without Comments"
    )

    comments = await crud_review.get_media_comments(
        session=session,
        media_id=media.id
    )

    assert len(comments) == 0

    count = await crud_review.get_media_comments_count(
        session=session,
        media_id=media.id
    )

    assert count == 0


@pytest.mark.asyncio
async def test_get_media_comments_nonexistent_media(session: AsyncSession):
    """Test getting comments for non-existent media"""
    fake_media_id = uuid4()

    comments = await crud_review.get_media_comments(
        session=session,
        media_id=fake_media_id
    )

    assert len(comments) == 0


@pytest.mark.asyncio
async def test_update_review(session: AsyncSession):
    """Test updating a review"""
    user = await crud_user.create_user(
        session=session,
        email="updaterev@example.com",
        username="updaterev",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=606,
        media_type=MediaType.MOVIE,
        title="Movie"
    )

    review = await crud_review.create_review(
        session=session,
        user_id=user.id,
        media_id=media.id,
        content="Initial comment",
        rating=3
    )

    updated = await crud_review.update_review(
        session=session,
        review_id=review.id,
        content="Updated comment",
        rating=5
    )

    assert updated.content == "Updated comment"
    assert updated.rating == 5
    assert updated.updated_at > updated.created_at


@pytest.mark.asyncio
async def test_delete_review(session: AsyncSession):
    """Test deleting a review (soft delete - user thinks it's deleted)"""
    user = await crud_user.create_user(
        session=session,
        email="deleterev@example.com",
        username="deleterev",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=607,
        media_type=MediaType.MOVIE,
        title="Movie"
    )

    review = await crud_review.create_review(
        session=session,
        user_id=user.id,
        media_id=media.id,
        content="To be deleted"
    )

    deleted = await crud_review.delete_review(
        session=session,
        review_id=review.id
    )

    assert deleted is not None
    assert deleted.is_visible is False

    # Verify it still exists in DB
    review_check = await crud_review.get_review_by_id(
        session=session,
        review_id=review.id
    )
    assert review_check is not None
    assert review_check.is_visible is False

    # Verify it's not in public listings
    comments = await crud_review.get_media_comments(
        session=session,
        media_id=media.id
    )
    assert len(comments) == 0


@pytest.mark.asyncio
async def test_hide_review(session: AsyncSession):
    """Test hiding a review (soft delete)"""
    user = await crud_user.create_user(
        session=session,
        email="hiderev@example.com",
        username="hiderev",
        password="TestPass123"
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=608,
        media_type=MediaType.MOVIE,
        title="Movie"
    )

    review = await crud_review.create_review(
        session=session,
        user_id=user.id,
        media_id=media.id,
        content="To be hidden"
    )

    hidden = await crud_review.hide_review(
        session=session,
        review_id=review.id
    )

    assert hidden.is_visible is False

    # Should not appear in public listing
    comments = await crud_review.get_media_comments(
        session=session,
        media_id=media.id
    )
    assert len(comments) == 0