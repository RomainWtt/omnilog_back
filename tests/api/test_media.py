import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from datetime import date


@pytest.mark.asyncio
async def test_search_media_authenticated(authenticated_client: tuple[AsyncClient, dict]):
    """Test searching media with authentication"""
    client, tokens = authenticated_client

    # Mock TMDB response
    mock_tmdb_response = {
        "results": [
            {
                "id": 550,
                "title": "Fight Club",
                "overview": "A ticking-time-bomb insomniac...",
                "poster_path": "/path.jpg",
                "release_date": "1999-10-15",
                "vote_average": 8.4,
                "media_type": "movie"
            }
        ],
        "page": 1,
        "total_pages": 1,
        "total_results": 1
    }

    with patch('app.api.endpoints.media.tmdb_service.search_multi',
               new_callable=AsyncMock, return_value=mock_tmdb_response):
        response = await client.get("/api/v1/media/search?query=fight+club")

    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0


@pytest.mark.asyncio
async def test_search_media_without_query(authenticated_client: tuple[AsyncClient, dict]):
    """Test search without query parameter"""
    client, tokens = authenticated_client

    response = await client.get("/api/v1/media/search")

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_media_by_type(authenticated_client: tuple[AsyncClient, dict]):
    """Test searching with media type filter"""
    client, tokens = authenticated_client

    mock_response = {"results": [], "page": 1}

    with patch('app.api.endpoints.media.tmdb_service.search_movie',
               new_callable=AsyncMock, return_value=mock_response):
        response = await client.get(
            "/api/v1/media/search?query=inception&media_type=movie"
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_media_details(authenticated_client: tuple[AsyncClient, dict], session):
    """Test getting media details"""
    client, tokens = authenticated_client

    # Create a media entry in database
    from app.db.models import Media, MediaType

    media = Media(
        tmdb_id=550,
        media_type=MediaType.MOVIE,
        title="Fight Club",
        overview="Test overview",
        release_date=date(1999, 10, 15)
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    response = await client.get(f"/api/v1/media/{media.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Fight Club"
    assert data["tmdb_id"] == 550


@pytest.mark.asyncio
async def test_get_nonexistent_media(authenticated_client: tuple[AsyncClient, dict]):
    """Test getting media that doesn't exist"""
    client, tokens = authenticated_client

    from uuid import uuid4
    fake_id = str(uuid4())

    response = await client.get(f"/api/v1/media/{fake_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_media_by_tmdb_id(authenticated_client: tuple[AsyncClient, dict]):
    """Test getting media by TMDB ID"""
    client, tokens = authenticated_client

    mock_movie = {
        "id": 550,
        "title": "Fight Club",
        "overview": "Test",
        "poster_path": "/path.jpg",
        "release_date": "1999-10-15",
        "runtime": 139,
        "genre_ids": [{"genre_id": [18, 53]}],
        "production_companies": [{"name": "Fox"}],
        "vote_average": 8.4,
        "vote_count": 10000,
        "original_language": "en",
        "credits": {
            "cast": [
                {"name": "Brad Pitt"},
                {"name": "Edward Norton"},
                {"name": "Helena Bonham Carter"}
            ],
            "crew": [
                {"name": "David Fincher", "job": "Director"}
            ]
        }
    }

    with patch('app.api.endpoints.media.tmdb_service.get_movie_details',
               new_callable=AsyncMock, return_value=mock_movie):
        response = await client.get(
            "/api/v1/media/tmdb/550?media_type=movie"
        )

    assert response.status_code == 200, f"Response: {response.status_code}, Body: {response.text}"
    data = response.json()
    assert data["tmdb_id"] == 550
    assert data["title"] == "Fight Club"
    assert "actors" in data
    assert "directors" in data
    assert len(data["actors"]) == 3
    assert data["actors"][0] == "Brad Pitt"
    assert data["directors"][0] == "David Fincher"


@pytest.mark.asyncio
async def test_get_top_movies(client: AsyncClient):
    """Test getting top movies (public endpoint)"""
    mock_response = {
        "results": [{"id": 1, "title": "Movie 1"}] * 20,
        "page": 1
    }

    with patch('app.api.endpoints.media.tmdb_service.get_top_rated_movies',
               new_callable=AsyncMock, return_value=mock_response):
        response = await client.get("/api/v1/media/top/movies?page=1")

    assert response.status_code == 200
    data = response.json()
    assert "results" in data


@pytest.mark.asyncio
async def test_search_empty_results(authenticated_client: tuple[AsyncClient, dict]):
    """Test search with no results"""
    client, tokens = authenticated_client

    mock_response = {"results": [], "page": 1, "total_results": 0}

    with patch('app.api.endpoints.media.tmdb_service.search_multi',
               new_callable=AsyncMock, return_value=mock_response):
        response = await client.get("/api/v1/media/search?query=xyznonexistent")

    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 0
