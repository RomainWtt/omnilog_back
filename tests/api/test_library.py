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
    """Test adding media to user library - REMOVED progress"""
    client, tokens = authenticated_client
    
    entry_data = {
        "media_id": str(test_media.id),
        "list_status": "watching",
        "timecode": 0,  # Use timecode instead of progress
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
    """Test adding non-existent media to library - REMOVED progress"""
    client, tokens = authenticated_client
    
    from uuid import uuid4
    fake_id = str(uuid4())
    
    entry_data = {
        "media_id": fake_id,
        "list_status": "watching",
        "timecode": 0  # Use timecode instead of progress
    }
    
    response = await client.post("/api/v1/library/", json=entry_data)
    
    assert response.status_code == 404, f"Response: {response.status_code}, Body: {response.text}"

@pytest.mark.asyncio
async def test_update_library_entry(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test updating library entry - REMOVED progress"""
    client, tokens = authenticated_client
    
    # Add to library
    await client.post("/api/v1/library/", json={
        "media_id": str(test_media.id),
        "list_status": "watching",
        "timecode": 0
    })
    
    # Update entry
    update_data = {
        "list_status": "completed",
        "timecode": 8340,  # Use timecode instead of progress
        "score": 9
    }
    
    response = await client.put(
        f"/api/v1/library/{test_media.id}",
        json=update_data
    )
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert data["list_status"] == "completed"
    assert data["timecode"] == 8340
    assert data["score"] == 9


@pytest.mark.asyncio
async def test_update_progress(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test updating viewing progress - REMOVED progress field"""
    client, tokens = authenticated_client
    
    progress_data = {
        "timecode": 3600,  # Only timecode, no progress percentage
        "current_season": 1,
        "current_episode": 5
    }
    
    response = await client.put(
        f"/api/v1/library/{test_media.id}/progress",
        json=progress_data
    )
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert data["timecode"] == 3600
    assert data["current_season"] == 1
    assert data["current_episode"] == 5


@pytest.mark.asyncio
async def test_remove_from_library(
    authenticated_client: tuple[AsyncClient, dict],
    test_media
):
    """Test removing media from library - REMOVED progress"""
    client, tokens = authenticated_client
    
    # Add to library first
    await client.post("/api/v1/library/", json={
        "media_id": str(test_media.id),
        "list_status": "watching",
        "timecode": 0
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
    """Test getting specific library entry - REMOVED progress"""
    client, tokens = authenticated_client
    
    # Add to library
    await client.post("/api/v1/library/", json={
        "media_id": str(test_media.id),
        "list_status": "watching",
        "timecode": 3000  # Use timecode instead of progress
    })
    
    # Get specific entry
    response = await client.get(f"/api/v1/library/{test_media.id}")
    
    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert data["media_id"] == str(test_media.id)
    assert data["timecode"] == 3000