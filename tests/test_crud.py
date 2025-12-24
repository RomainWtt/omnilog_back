import pytest
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_user, crud_media
from app.db.models import MediaType

# Date de naissance par défaut pour les tests (utilisateur de 25 ans)
TEST_BIRTH_DATE = date(1999, 1, 1)


@pytest.mark.asyncio
async def test_create_user(session: AsyncSession):
    """Test creating a user"""
    user = await crud_user.create_user(
        session=session,
        email="crud@example.com",
        username="cruduser",
        password="TestPass123",
        birth_date=TEST_BIRTH_DATE,
    )

    assert user.email == "crud@example.com"
    assert user.username == "cruduser"
    assert user.hashed_password is not None
    assert user.id is not None
    assert user.birth_date == TEST_BIRTH_DATE


@pytest.mark.asyncio
async def test_get_user_by_email(session: AsyncSession):
    """Test retrieving user by email"""
    await crud_user.create_user(
        session=session,
        email="get@example.com",
        username="getuser",
        password="TestPass123",
        birth_date=TEST_BIRTH_DATE,
    )

    user = await crud_user.get_user_by_email(session, "get@example.com")

    assert user is not None
    assert user.email == "get@example.com"


@pytest.mark.asyncio
async def test_get_user_by_username(session: AsyncSession):
    """Test retrieving user by username"""
    await crud_user.create_user(
        session=session,
        email="username@example.com",
        username="findme",
        password="TestPass123",
        birth_date=TEST_BIRTH_DATE,
    )

    user = await crud_user.get_user_by_username(session, "findme")

    assert user is not None
    assert user.username == "findme"


@pytest.mark.asyncio
async def test_authenticate_user(session: AsyncSession):
    """Test user authentication"""
    password = "TestPass123"
    await crud_user.create_user(
        session=session,
        email="auth@example.com",
        username="authuser",
        password=password,
        birth_date=TEST_BIRTH_DATE,
    )

    # Correct password
    user = await crud_user.authenticate_user(session, "auth@example.com", password)
    assert user is not None

    # Wrong password
    user = await crud_user.authenticate_user(session, "auth@example.com", "wrong")
    assert user is None


@pytest.mark.asyncio
async def test_update_user(session: AsyncSession):
    """Test updating user"""
    user = await crud_user.create_user(
        session=session,
        email="update@example.com",
        username="updateuser",
        password="TestPass123",
        birth_date=TEST_BIRTH_DATE,
    )

    updated = await crud_user.update_user(
        session=session,
        user_id=user.id,
        username="newusername",
        avatar_url="https://example.com/avatar.jpg"
    )

    assert updated.username == "newusername"
    assert updated.avatar_url == "https://example.com/avatar.jpg"


@pytest.mark.asyncio
async def test_deactivate_user(session: AsyncSession):
    """Test deactivating user"""
    user = await crud_user.create_user(
        session=session,
        email="deactivate@example.com",
        username="deactivateuser",
        password="TestPass123",
        birth_date=TEST_BIRTH_DATE,
    )

    assert user.is_active is True

    deactivated = await crud_user.deactivate_user(session, user.id)

    assert deactivated.is_active is False


@pytest.mark.asyncio
async def test_create_media(session: AsyncSession):
    """Test creating media"""
    media = await crud_media.create_media(
        session=session,
        tmdb_id=550,
        media_type=MediaType.MOVIE,
        title="Fight Club",
        overview="Test overview",
        runtime=139
    )

    assert media.tmdb_id == 550
    assert media.title == "Fight Club"
    assert media.media_type == MediaType.MOVIE


@pytest.mark.asyncio
async def test_get_media_by_tmdb_id(session: AsyncSession):
    """Test retrieving media by TMDB ID"""
    await crud_media.create_media(
        session=session,
        tmdb_id=551,
        media_type=MediaType.MOVIE,
        title="Test Movie"
    )

    media = await crud_media.get_media_by_tmdb_id(session, 551, MediaType.MOVIE)

    assert media is not None
    assert media.tmdb_id == 551


@pytest.mark.asyncio
async def test_search_media_by_title(session: AsyncSession):
    """Test searching media by title"""
    await crud_media.create_media(
        session=session,
        tmdb_id=100,
        media_type=MediaType.MOVIE,
        title="Fight Club"
    )
    await crud_media.create_media(
        session=session,
        tmdb_id=101,
        media_type=MediaType.MOVIE,
        title="Fight Night"
    )

    results = await crud_media.search_media_by_title(session, "fight")

    assert len(results) == 2


@pytest.mark.asyncio
async def test_create_user_media_entry(session: AsyncSession):
    """Test creating user media entry - REMOVED progress field"""
    user = await crud_user.create_user(
        session=session,
        email="entry@example.com",
        username="entryuser",
        password="TestPass123",
        birth_date=TEST_BIRTH_DATE,
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=200,
        media_type=MediaType.MOVIE,
        title="Test"
    )

    entry = await crud_media.create_user_media_entry(
        session=session,
        user_id=user.id,
        media_id=media.id,
        list_status="watching",
        timecode=3000  # Use timecode instead of progress
    )

    assert entry.user_id == user.id
    assert entry.media_id == media.id
    assert entry.timecode == 3000


@pytest.mark.asyncio
async def test_update_user_media_entry(session: AsyncSession):
    """Test updating user media entry - REMOVED progress field"""
    user = await crud_user.create_user(
        session=session,
        email="updateentry@example.com",
        username="updateentryuser",
        password="TestPass123",
        birth_date=TEST_BIRTH_DATE,
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=201,
        media_type=MediaType.MOVIE,
        title="Test"
    )

    # Create entry
    await crud_media.create_user_media_entry(
        session=session,
        user_id=user.id,
        media_id=media.id,
        list_status="watching",
        timecode=0
    )

    # Update entry - use timecode instead of progress
    updated = await crud_media.update_user_media_entry(
        session=session,
        user_id=user.id,
        media_id=media.id,
        timecode=4500,
        score=8
    )

    assert updated.timecode == 4500
    assert updated.score == 8


@pytest.mark.asyncio
async def test_get_user_library(session: AsyncSession):
    """Test getting user's library"""
    user = await crud_user.create_user(
        session=session,
        email="library@example.com",
        username="libraryuser",
        password="TestPass123",
        birth_date=TEST_BIRTH_DATE,
    )

    # Add multiple media
    for i in range(5):
        media = await crud_media.create_media(
            session=session,
            tmdb_id=300 + i,
            media_type=MediaType.MOVIE,
            title=f"Movie {i}"
        )
        await crud_media.create_user_media_entry(
            session=session,
            user_id=user.id,
            media_id=media.id,
            list_status="completed" if i % 2 == 0 else "watching"
        )

    # Get all library
    library = await crud_media.get_user_library(session, user.id)
    assert len(library) == 5

    # Get filtered library
    completed = await crud_media.get_user_library(
        session, user.id, status="completed"
    )
    assert len(completed) == 3  # 0, 2, 4


@pytest.mark.asyncio
async def test_delete_user_media_entry(session: AsyncSession):
    """Test deleting user media entry"""
    user = await crud_user.create_user(
        session=session,
        email="delete@example.com",
        username="deleteuser",
        password="TestPass123",
        birth_date=TEST_BIRTH_DATE,
    )
    media = await crud_media.create_media(
        session=session,
        tmdb_id=400,
        media_type=MediaType.MOVIE,
        title="Test"
    )

    # Create entry
    await crud_media.create_user_media_entry(
        session=session,
        user_id=user.id,
        media_id=media.id,
        list_status="watching"
    )

    # Delete entry
    deleted = await crud_media.delete_user_media_entry(
        session=session,
        user_id=user.id,
        media_id=media.id
    )

    assert deleted is True

    # Verify deleted
    entry = await crud_media.get_user_media_entry(
        session=session,
        user_id=user.id,
        media_id=media.id
    )
    assert entry is None