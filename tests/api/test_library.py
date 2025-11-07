import pytest
from httpx import AsyncClient
from datetime import date


@pytest.fixture
async def test_media(session):
    """Create test media for library tests"""
    from app.db.models import Media, MediaType
    
    media = Media(
        tmdb_id=550,
        media_type=MediaType.MOVIE,
        title="Fight Club",
        overview="Test movie",
        runtime=139,
        release_date=date(1999, 10, 15)
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)
    return media


@pytest.mark.asyncio
async def test_add_to_library(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test adding media to user library"""
    client, tokens = authenticated_client
    
    entry_data = {
        "media_id": str(test_media.id),
        "list_status": "watching",
        "progress": 0,
        "score": 8
    }
    
    response = await client.post("/api/v1/library/", json=entry_data)
    
    assert response.status_code == 201, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert data["media_id"] == str(test_media.id)
    assert data["list_status"] == "watching"
    assert data["score"] == 8


@pytest.mark.asyncio
async def test_add_nonexistent_media_to_library(
    authenticated_client: tuple[AsyncClient, dict]
):
    """Test adding non-existent media to library"""
    client, tokens = authenticated_client
    
    from uuid import uuid4
    fake_id = str(uuid4())
    
    entry_data = {
        "media_id": fake_id,
        "list_status": "watching",
        "progress": 0
    }
    
    response = await client.post("/api/v1/library/", json=entry_data)
    
    assert response.status_code == 404, f"Response: {response.status_code}, Body: {response.text}"


@pytest.mark.asyncio
async def test_get_library(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test getting user's library"""
    client, tokens = authenticated_client
    
    # Add media to library first
    await client.post("/api/v1/library/", json={
        "media_id": str(test_media.id),
        "list_status": "completed",
        "progress": 100
    })
    
    response = await client.get("/api/v1/library/")
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_library_filtered(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test getting filtered library"""
    client, tokens = authenticated_client
    
    # Add media with different statuses
    await client.post("/api/v1/library/", json={
        "media_id": str(test_media.id),
        "list_status": "completed",
        "progress": 100
    })
    
    response = await client.get("/api/v1/library/?status=completed")
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert all(item["list_status"] == "completed" for item in data)


@pytest.mark.asyncio
async def test_update_library_entry(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test updating library entry"""
    client, tokens = authenticated_client
    
    # Add to library
    await client.post("/api/v1/library/", json={
        "media_id": str(test_media.id),
        "list_status": "watching",
        "progress": 0
    })
    
    # Update entry
    update_data = {
        "list_status": "completed",
        "progress": 100,
        "score": 9
    }
    
    response = await client.put(
        f"/api/v1/library/{test_media.id}",
        json=update_data
    )
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert data["list_status"] == "completed"
    assert data["progress"] == 100
    assert data["score"] == 9


@pytest.mark.asyncio
async def test_update_progress(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test updating viewing progress"""
    client, tokens = authenticated_client
    
    progress_data = {
        "progress": 50,
        "timecode": 3600,
        "current_season": 1,
        "current_episode": 5
    }
    
    response = await client.put(
        f"/api/v1/library/{test_media.id}/progress",
        json=progress_data
    )
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert data["progress"] == 50
    assert data["timecode"] == 3600
    assert data["current_season"] == 1
    assert data["current_episode"] == 5


@pytest.mark.asyncio
async def test_remove_from_library(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test removing media from library"""
    client, tokens = authenticated_client
    
    # Add to library first
    await client.post("/api/v1/library/", json={
        "media_id": str(test_media.id),
        "list_status": "watching",
        "progress": 0
    })
    
    # Remove from library
    response = await client.delete(f"/api/v1/library/{test_media.id}")
    
    assert response.status_code == 204, f"Response: {response.status_code}, Body: {response.text}"
    
    # Verify it's gone
    get_response = await client.get(f"/api/v1/library/{test_media.id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_toggle_favorite(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test toggling favorite status"""
    client, tokens = authenticated_client
    
    # Toggle favorite (should create entry)
    response = await client.post(f"/api/v1/library/{test_media.id}/favorite")
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert data["is_favorite"] is True
    
    # Toggle again (should turn off)
    response = await client.post(f"/api/v1/library/{test_media.id}/favorite")
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_favorite"] is False


@pytest.mark.asyncio
async def test_get_library_entry(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test getting specific library entry"""
    client, tokens = authenticated_client
    
    # Add to library
    await client.post("/api/v1/library/", json={
        "media_id": str(test_media.id),
        "list_status": "watching",
        "progress": 50
    })
    
    # Get specific entry
    response = await client.get(f"/api/v1/library/{test_media.id}")
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert data["media_id"] == str(test_media.id)
    assert data["progress"] == 50


@pytest.mark.asyncio
async def test_library_pagination(
    authenticated_client: tuple[AsyncClient, dict],
    session
):
    """Test library pagination"""
    client, tokens = authenticated_client
    
    # Create multiple media entries
    from app.db.models import Media, MediaType
    
    for i in range(15):
        media = Media(
            tmdb_id=1000 + i,
            media_type=MediaType.MOVIE,
            title=f"Movie {i}",
            release_date=date(2020, 1, 1)
        )
        session.add(media)
    await session.commit()
    
    # Test with limit
    response = await client.get("/api/v1/library/?limit=10&offset=0")
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert len(data) <= 10