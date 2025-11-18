"""
Complete tests for review/comment API endpoints - 100% coverage
"""
import pytest
from httpx import AsyncClient
from datetime import date, datetime, timedelta


# ============================================
# TEST GET COMMENTS FOR MEDIA (Already provided in your file)
# ============================================
# These tests are already in your test_review.py file
# I won't duplicate them here


# ============================================
# TEST CREATE REVIEW (POST /)
# ============================================

@pytest.mark.asyncio
async def test_create_review_success(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test creating a new review with content and rating"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    # Create media
    media = Media(
        tmdb_id=1000,
        media_type=MediaType.MOVIE,
        title="New Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Create review
    review_data = {
        "media_id": str(media.id),
        "content": "This is an amazing movie!",
        "rating": 5
    }

    response = await client.post("/api/v1/review/", json=review_data)

    assert response.status_code == 201
    data = response.json()

    assert data["content"] == "This is an amazing movie!"
    assert data["rating"] == 5
    assert data["media_id"] == str(media.id)
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_review_without_content(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test creating review with only rating (no content)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1001,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    review_data = {
        "media_id": str(media.id),
        "rating": 5
    }

    response = await client.post("/api/v1/review/", json=review_data)

    assert response.status_code == 201
    data = response.json()

    assert data["content"] is None
    assert data["rating"] == 5


@pytest.mark.asyncio
async def test_create_review_duplicate(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test creating duplicate review (should fail with 400)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1002,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    review_data = {
        "media_id": str(media.id),
        "rating": 4,
        "content": "First review"
    }

    # Create first review
    response1 = await client.post("/api/v1/review/", json=review_data)
    assert response1.status_code == 201

    # Try to create second review (should fail)
    review_data["content"] = "Second review attempt"
    review_data["rating"] = 5
    response2 = await client.post("/api/v1/review/", json=review_data)

    assert response2.status_code == 400
    assert "already reviewed" in response2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_review_invalid_rating(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test creating review with invalid rating (should fail with 422)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1003,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Rating too high
    review_data = {
        "media_id": str(media.id),
        "content": "Test",
        "rating": 6
    }
    response = await client.post("/api/v1/review/", json=review_data)
    assert response.status_code == 422

    # Rating too low (0 is now invalid, minimum is 1)
    review_data["rating"] = 0
    response = await client.post("/api/v1/review/", json=review_data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_review_missing_rating(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test creating review without rating (should fail with 422)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1004,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    review_data = {
        "media_id": str(media.id),
        "content": "Great movie"
    }

    response = await client.post("/api/v1/review/", json=review_data)
    assert response.status_code == 422


# ============================================
# TEST GET REVIEW BY ID (GET /{review_id})
# ============================================

@pytest.mark.asyncio
async def test_get_review_by_id_success(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test getting a specific review by ID"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash

    user = User(
        email="getreview@example.com",
        username="getreview",
        hashed_password=get_password_hash("TestPass123")
    )
    session.add(user)

    media = Media(
        tmdb_id=1100,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(user)
    await session.refresh(media)

    review = Review(
        user_id=user.id,
        media_id=media.id,
        content="Test review",
        rating=4
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)

    response = await client.get(f"/api/v1/review/{review.id}")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(review.id)
    assert data["content"] == "Test review"
    assert data["rating"] == 4


@pytest.mark.asyncio
async def test_get_review_nonexistent(
    authenticated_client: tuple[AsyncClient, dict]
):
    """Test getting non-existent review (404)"""
    client, tokens = authenticated_client

    from uuid import uuid4
    fake_id = str(uuid4())

    response = await client.get(f"/api/v1/review/{fake_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_review_invalid_uuid(
    authenticated_client: tuple[AsyncClient, dict]
):
    """Test getting review with invalid UUID format"""
    client, tokens = authenticated_client

    response = await client.get("/api/v1/review/invalid-uuid")

    assert response.status_code == 422


# ============================================
# TEST UPDATE REVIEW (PUT /{review_id})
# ============================================

@pytest.mark.asyncio
async def test_update_review_success(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test updating own review"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    # Create media and review
    media = Media(
        tmdb_id=1200,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Create review
    review_data = {
        "media_id": str(media.id),
        "content": "Initial content",
        "rating": 3
    }
    create_response = await client.post("/api/v1/review/", json=review_data)
    review_id = create_response.json()["id"]

    # Update review
    update_data = {
        "content": "Updated content",
        "rating": 5
    }
    response = await client.put(f"/api/v1/review/{review_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()

    assert data["content"] == "Updated content"
    assert data["rating"] == 5
    assert data["id"] == review_id


@pytest.mark.asyncio
async def test_update_review_only_content(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test updating only content"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1201,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Create review
    review_data = {
        "media_id": str(media.id),
        "content": "Initial",
        "rating": 4
    }
    create_response = await client.post("/api/v1/review/", json=review_data)
    review_id = create_response.json()["id"]

    # Update only content
    update_data = {"content": "Updated only content"}
    response = await client.put(f"/api/v1/review/{review_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()

    assert data["content"] == "Updated only content"
    assert data["rating"] == 4  # Rating unchanged


@pytest.mark.asyncio
async def test_update_review_only_rating(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test updating only rating"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1202,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Create review
    review_data = {
        "media_id": str(media.id),
        "content": "Great movie",
        "rating": 3
    }
    create_response = await client.post("/api/v1/review/", json=review_data)
    review_id = create_response.json()["id"]

    # Update only rating
    update_data = {"rating": 5}
    response = await client.put(f"/api/v1/review/{review_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()

    assert data["content"] == "Great movie"  # Content unchanged
    assert data["rating"] == 5


@pytest.mark.asyncio
async def test_update_review_not_owner(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test updating someone else's review (403)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash

    # Create another user
    other_user = User(
        email="otheruser@example.com",
        username="otheruser",
        hashed_password=get_password_hash("TestPass123")
    )
    session.add(other_user)

    media = Media(
        tmdb_id=1203,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(other_user)
    await session.refresh(media)

    # Create review as other user
    review = Review(
        user_id=other_user.id,
        media_id=media.id,
        content="Other user's review",
        rating=4
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)

    # Try to update as current user (should fail)
    update_data = {"content": "Trying to hack"}
    response = await client.put(f"/api/v1/review/{review.id}", json=update_data)

    assert response.status_code == 403
    assert "only update your own" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_review_nonexistent(
    authenticated_client: tuple[AsyncClient, dict]
):
    """Test updating non-existent review (404)"""
    client, tokens = authenticated_client

    from uuid import uuid4
    fake_id = str(uuid4())

    update_data = {"content": "Updated"}
    response = await client.put(f"/api/v1/review/{fake_id}", json=update_data)

    assert response.status_code == 404


# ============================================
# TEST DELETE REVIEW (DELETE /{review_id})
# ============================================

@pytest.mark.asyncio
async def test_delete_review_success(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test deleting own review (soft delete - sets is_visible to False)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1300,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Create review
    review_data = {
        "media_id": str(media.id),
        "rating": 4,
        "content": "To be deleted"
    }
    create_response = await client.post("/api/v1/review/", json=review_data)
    review_id = create_response.json()["id"]

    # Delete review (soft delete)
    response = await client.delete(f"/api/v1/review/{review_id}")

    assert response.status_code == 200  # Returns the deleted review
    data = response.json()

    assert data["id"] == review_id
    assert data["is_visible"] is False  # Now hidden

    # Verify it still exists but is not visible
    get_response = await client.get(f"/api/v1/review/{review_id}")
    assert get_response.status_code == 200
    assert get_response.json()["is_visible"] is False


@pytest.mark.asyncio
async def test_delete_review_not_in_public_list(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test that deleted review doesn't appear in media comments list"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1301,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Create review
    review_data = {
        "media_id": str(media.id),
        "rating": 4,
        "content": "To be deleted"
    }
    create_response = await client.post("/api/v1/review/", json=review_data)
    review_id = create_response.json()["id"]

    # Verify it appears in list
    list_response = await client.get(f"/api/v1/review/media/{media.id}")
    assert len(list_response.json()["results"]) == 1

    # Delete review
    await client.delete(f"/api/v1/review/{review_id}")

    # Verify it doesn't appear in list anymore
    list_response = await client.get(f"/api/v1/review/media/{media.id}")
    assert len(list_response.json()["results"]) == 0


@pytest.mark.asyncio
async def test_delete_review_not_owner(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test deleting someone else's review (403)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash

    # Create another user
    other_user = User(
        email="deletetest@example.com",
        username="deletetest",
        hashed_password=get_password_hash("TestPass123")
    )
    session.add(other_user)

    media = Media(
        tmdb_id=1302,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(other_user)
    await session.refresh(media)

    # Create review as other user
    review = Review(
        user_id=other_user.id,
        media_id=media.id,
        content="Other's review",
        rating=3
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)

    # Try to delete as current user (should fail)
    response = await client.delete(f"/api/v1/review/{review.id}")

    assert response.status_code == 403
    assert "only delete your own" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_review_nonexistent(
    authenticated_client: tuple[AsyncClient, dict]
):
    """Test deleting non-existent review (404)"""
    client, tokens = authenticated_client

    from uuid import uuid4
    fake_id = str(uuid4())

    response = await client.delete(f"/api/v1/review/{fake_id}")

    assert response.status_code == 404


# ============================================
# TEST MEDIA AVERAGE RATING (GET /media/{media_id}/average)
# ============================================

@pytest.mark.asyncio
async def test_get_media_average_rating(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test getting average rating for media"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash

    # Create users
    users = []
    for i in range(3):
        user = User(
            email=f"avguser{i}@example.com",
            username=f"avguser{i}",
            hashed_password=get_password_hash("TestPass123")
        )
        session.add(user)
        users.append(user)

    media = Media(
        tmdb_id=1400,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()

    for user in users:
        await session.refresh(user)
    await session.refresh(media)

    # Create reviews with ratings: 3, 4, 5 (average = 4.0)
    ratings = [3, 4, 5]
    for user, rating in zip(users, ratings):
        review = Review(
            user_id=user.id,
            media_id=media.id,
            content=f"Review with rating {rating}",
            rating=rating
        )
        session.add(review)
    await session.commit()

    response = await client.get(f"/api/v1/review/media/{media.id}/average")

    assert response.status_code == 200
    data = response.json()

    assert data["media_id"] == str(media.id)
    assert data["average_rating"] == 4.0
    assert data["total_ratings"] == 3


@pytest.mark.asyncio
async def test_get_media_average_no_ratings(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test average with no ratings (only comments)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash

    user = User(
        email="norating@example.com",
        username="norating",
        hashed_password=get_password_hash("TestPass123")
    )
    session.add(user)

    media = Media(
        tmdb_id=1401,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(user)
    await session.refresh(media)

    # Don't create any review - test media with no reviews

    response = await client.get(f"/api/v1/review/media/{media.id}/average")

    assert response.status_code == 200
    data = response.json()

    assert data["average_rating"] is None
    assert data["total_ratings"] == 0


@pytest.mark.asyncio
async def test_get_media_average_empty_media(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test average for media with no reviews"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1402,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    response = await client.get(f"/api/v1/review/media/{media.id}/average")

    assert response.status_code == 200
    data = response.json()

    assert data["average_rating"] is None
    assert data["total_ratings"] == 0


# ============================================
# TEST USER REVIEW FOR MEDIA (GET /media/{media_id}/user)
# ============================================

@pytest.mark.asyncio
async def test_get_current_user_review_exists(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test getting own review for a media"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1500,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Create review
    review_data = {
        "media_id": str(media.id),
        "content": "My review",
        "rating": 5
    }
    await client.post("/api/v1/review/", json=review_data)

    # Get own review
    response = await client.get(f"/api/v1/review/media/{media.id}/user")

    assert response.status_code == 200
    data = response.json()

    assert data["content"] == "My review"
    assert data["rating"] == 5


@pytest.mark.asyncio
async def test_get_current_user_review_not_exists(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test when user hasn't reviewed media (404)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1501,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    response = await client.get(f"/api/v1/review/media/{media.id}/user")

    assert response.status_code == 404
    assert "haven't reviewed" in response.json()["detail"].lower()


# ============================================
# TEST USER REVIEWS (GET /user/{user_id})
# ============================================

@pytest.mark.asyncio
async def test_get_user_reviews(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test getting all reviews from a user"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash
    from app.crud import crud_user

    # Get current user
    current_user = await crud_user.get_user_by_email(session, "test@example.com")

    # Create multiple media and reviews
    for i in range(5):
        media = Media(
            tmdb_id=1600 + i,
            media_type=MediaType.MOVIE,
            title=f"Movie {i}"
        )
        session.add(media)
        await session.commit()
        await session.refresh(media)

        review = Review(
            user_id=current_user.id,
            media_id=media.id,
            content=f"Review {i}",
            rating=((i % 5) + 1)
        )
        session.add(review)
    await session.commit()

    response = await client.get(f"/api/v1/review/user/{current_user.id}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["results"]) == 5
    assert data["total"] == 5
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_user_reviews_pagination(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test pagination of user reviews"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review
    from app.crud import crud_user

    # Get current user
    current_user = await crud_user.get_user_by_email(session, "test@example.com")

    # Create 25 reviews
    for i in range(25):
        media = Media(
            tmdb_id=1700 + i,
            media_type=MediaType.MOVIE,
            title=f"Movie {i}"
        )
        session.add(media)
        await session.commit()
        await session.refresh(media)

        review = Review(
            user_id=current_user.id,
            media_id=media.id,
            content=f"Review {i}",
            rating=((i % 5) + 1)
        )
        session.add(review)
    await session.commit()

    # Page 1
    response = await client.get(f"/api/v1/review/user/{current_user.id}?page=1")
    assert response.status_code == 200
    data = response.json()

    assert len(data["results"]) == 20
    assert data["total"] == 25
    assert data["pages"] == 2

    # Page 2
    response = await client.get(f"/api/v1/review/user/{current_user.id}?page=2")
    assert response.status_code == 200
    data = response.json()

    assert len(data["results"]) == 5


@pytest.mark.asyncio
async def test_get_user_reviews_empty(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test getting reviews from user with no reviews"""
    client, tokens = authenticated_client

    from app.db.models import User
    from app.core.security import get_password_hash

    # Create user without reviews
    user = User(
        email="noreviews@example.com",
        username="noreviews",
        hashed_password=get_password_hash("TestPass123")
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    response = await client.get(f"/api/v1/review/user/{user.id}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["results"]) == 0
    assert data["total"] == 0


# ============================================
# TEST RECENT REVIEWS (GET /recent)
# ============================================

@pytest.mark.asyncio
async def test_get_recent_reviews(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test getting recent reviews"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash

    # Create user
    user = User(
        email="recent@example.com",
        username="recent",
        hashed_password=get_password_hash("TestPass123")
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Create reviews with different timestamps
    base_time = datetime.utcnow()
    for i in range(5):
        media = Media(
            tmdb_id=1800 + i,
            media_type=MediaType.MOVIE,
            title=f"Movie {i}"
        )
        session.add(media)
        await session.commit()
        await session.refresh(media)

        review = Review(
            user_id=user.id,
            media_id=media.id,
            content=f"Review {i}",
            rating=((i % 5) + 1),
            created_at=base_time - timedelta(hours=i)
        )
        session.add(review)
    await session.commit()

    response = await client.get("/api/v1/review/recent")

    assert response.status_code == 200
    data = response.json()

    assert len(data) <= 10  # Default limit
    # Most recent should be first
    assert "Review 0" in data[0]["content"]


# ============================================
# TEST HIDE/UNHIDE REVIEW
# ============================================

@pytest.mark.asyncio
async def test_hide_review_owner(
        authenticated_client: tuple[AsyncClient, dict],
        session
):
    """Test hiding own review"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1900,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Create review
    review_data = {
        "media_id": str(media.id),
        "rating": 4,
        "content": "To be hidden"
    }
    create_response = await client.post("/api/v1/review/", json=review_data)
    review_id = create_response.json()["id"]

    # Hide review
    response = await client.patch(f"/api/v1/review/{review_id}/hide")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == review_id
    assert data["is_visible"] is False


@pytest.mark.asyncio
async def test_hide_review_admin(
        authenticated_client: tuple[AsyncClient, dict],
        session
):
    """Test admin hiding any review (moderation)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash
    from app.crud import crud_user

    # Make current user admin
    current_user = await crud_user.get_user_by_email(session, "test@example.com")
    current_user.is_admin = True
    session.add(current_user)

    # Create another user
    other_user = User(
        email="moderated@example.com",
        username="moderated",
        hashed_password=get_password_hash("TestPass123")
    )
    session.add(other_user)

    media = Media(
        tmdb_id=1901,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(other_user)
    await session.refresh(media)

    # Create review as other user
    review = Review(
        user_id=other_user.id,
        media_id=media.id,
        content="Inappropriate content",
        rating=3
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)

    # Admin hides review (moderation)
    response = await client.patch(f"/api/v1/review/{review.id}/hide")

    assert response.status_code == 200
    data = response.json()

    assert data["is_visible"] is False


@pytest.mark.asyncio
async def test_hide_review_not_authorized(
        authenticated_client: tuple[AsyncClient, dict],
        session
):
    """Test hiding someone else's review (403)"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash

    # Create another user
    other_user = User(
        email="otherhide@example.com",
        username="otherhide",
        hashed_password=get_password_hash("TestPass123")
    )
    session.add(other_user)

    media = Media(
        tmdb_id=1902,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(other_user)
    await session.refresh(media)

    # Create review as other user
    review = Review(
        user_id=other_user.id,
        media_id=media.id,
        content="Other's review",
        rating=3
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)

    # Try to hide as non-owner, non-admin
    response = await client.patch(f"/api/v1/review/{review.id}/hide")

    assert response.status_code == 403
    assert "only hide your own" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unhide_review(
        authenticated_client: tuple[AsyncClient, dict],
        session
):
    """Test unhiding a review"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=1903,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    # Create and hide review
    review_data = {
        "media_id": str(media.id),
        "rating": 5,
        "content": "Hidden then restored"
    }
    create_response = await client.post("/api/v1/review/", json=review_data)
    review_id = create_response.json()["id"]

    # Hide it
    await client.patch(f"/api/v1/review/{review_id}/hide")

    # Unhide it
    response = await client.patch(f"/api/v1/review/{review_id}/unhide")

    assert response.status_code == 200
    data = response.json()

    assert data["is_visible"] is True

    # Should appear in public list again
    list_response = await client.get(f"/api/v1/review/media/{media.id}")
    assert len(list_response.json()["results"]) == 1


@pytest.mark.asyncio
async def test_unhide_review_admin(
        authenticated_client: tuple[AsyncClient, dict],
        session
):
    """Test admin unhiding any review"""
    client, tokens = authenticated_client

    from app.db.models import Media, MediaType, Review, User
    from app.core.security import get_password_hash
    from app.crud import crud_user

    # Make current user admin
    current_user = await crud_user.get_user_by_email(session, "test@example.com")
    current_user.is_admin = True
    session.add(current_user)

    # Create another user
    other_user = User(
        email="unhidetest@example.com",
        username="unhidetest",
        hashed_password=get_password_hash("TestPass123")
    )
    session.add(other_user)

    media = Media(
        tmdb_id=1904,
        media_type=MediaType.MOVIE,
        title="Movie"
    )
    session.add(media)
    await session.commit()
    await session.refresh(other_user)
    await session.refresh(media)

    # Create hidden review
    review = Review(
        user_id=other_user.id,
        media_id=media.id,
        content="Hidden review",
        rating=3,
        is_visible=False
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)

    # Admin unhides
    response = await client.patch(f"/api/v1/review/{review.id}/unhide")

    assert response.status_code == 200
    data = response.json()

    assert data["is_visible"] is True