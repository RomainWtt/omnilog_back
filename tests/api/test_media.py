import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from datetime import date


@pytest.mark.asyncio
async def test_search_media_authenticated(authenticated_client: tuple[AsyncClient, dict]):
    """Test searching media with authentication"""
    client, tokens = authenticated_client

    # Mock TMDB response for simple search (no filters)
    mock_movie_response = {
        "results": [
            {
                "id": 550,
                "title": "Fight Club",
                "overview": "A ticking-time-bomb insomniac...",
                "poster_path": "/path.jpg",
                "release_date": "1999-10-15",
                "vote_average": 8.4,
                "popularity": 50.0,
                "media_type": "movie"
            }
        ],
        "page": 1,
        "total_pages": 1,
        "total_results": 1
    }

    mock_tv_response = {
        "results": [],
        "page": 1,
        "total_pages": 1,
        "total_results": 0
    }

    with patch('app.api.endpoints.media.tmdb_service.search_movie',
               new_callable=AsyncMock, return_value=mock_movie_response), \
            patch('app.api.endpoints.media.tmdb_service.search_tv',
                  new_callable=AsyncMock, return_value=mock_tv_response):
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

    mock_response = {
        "results": [{
            "id": 27205,
            "title": "Inception",
            "overview": "A thief who steals corporate secrets...",
            "poster_path": "/path.jpg",
            "release_date": "2010-07-16",
            "vote_average": 8.4,
            "popularity": 50.0,
            "media_type": "movie"
        }],
        "page": 1,
        "total_pages": 1,
        "total_results": 1
    }

    with patch('app.api.endpoints.media.tmdb_service.search_movie',
               new_callable=AsyncMock, return_value=mock_response):
        response = await client.get(
            "/api/v1/media/search?query=inception&media_type=movie"
        )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1


@pytest.mark.asyncio
async def test_search_with_filters(authenticated_client: tuple[AsyncClient, dict]):
    """Test search with genre and year filters"""
    client, tokens = authenticated_client

    # Mock pour retourner différentes réponses selon la page
    async def mock_search_movie(query, page):
        if page == 1:
            return {
                "results": [
                    {
                        "id": 550,
                        "title": "Fight Club",
                        "overview": "Test",
                        "poster_path": "/path.jpg",
                        "release_date": "1999-10-15",
                        "vote_average": 8.4,
                        "popularity": 50.0,
                        "genre_ids": [18, 53],  # Drama, Thriller
                        "media_type": "movie"
                    },
                    {
                        "id": 551,
                        "title": "Another Movie",
                        "overview": "Test",
                        "poster_path": "/path2.jpg",
                        "release_date": "1998-01-01",
                        "vote_average": 7.0,
                        "popularity": 30.0,
                        "genre_ids": [28],  # Action (ne match pas)
                        "media_type": "movie"
                    }
                ],
                "page": 1,
                "total_pages": 1,
                "total_results": 2
            }
        else:
            # Pages suivantes retournent vide pour arrêter la boucle
            return {
                "results": [],
                "page": page,
                "total_pages": 1,
                "total_results": 0
            }

    async def mock_search_tv(query, page):
        # Pas de résultats TV
        return {
            "results": [],
            "page": 1,
            "total_pages": 0,
            "total_results": 0
        }

    with patch('app.api.endpoints.media.tmdb_service.search_movie',
               side_effect=mock_search_movie), \
            patch('app.api.endpoints.media.tmdb_service.search_tv',
                  side_effect=mock_search_tv):
        response = await client.get(
            "/api/v1/media/search?query=fight&genre_ids=18,53&min_year=1999"
        )

    assert response.status_code == 200
    data = response.json()

    assert "results" in data
    assert "page" in data
    assert "total_pages" in data
    assert "total_results" in data

    assert len(data["results"]) == 1
    result = data["results"][0]

    assert result["tmdb_id"] == 550
    assert result["title"] == "Fight Club"
    assert result["media_type"] == "movie"

    assert "in_library" in result
    assert "library_status" in result
    assert result["in_library"] is False  # Pas dans la librairie du user
    assert result["library_status"] is None


@pytest.mark.asyncio
async def test_search_with_runtime_filter_error(authenticated_client: tuple[AsyncClient, dict]):
    """Test that runtime filters with keyword search return empty results"""
    client, tokens = authenticated_client

    response = await client.get(
        "/api/v1/media/search?query=inception&min_runtime=120"
    )

    assert response.status_code == 200
    data = response.json()

    assert "results" in data
    assert len(data["results"]) == 0
    assert data["page"] == 1
    assert data["total_pages"] == 0
    assert data["total_results"] == 0


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
        release_date=date(1999, 10, 15),
        runtime=139  # Ajouter runtime pour éviter le fetch TMDB
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
        "genres": [{"id": 18, "name": "Drama"}, {"id": 53, "name": "Thriller"}],
        "production_companies": [{"name": "Fox"}],
        "vote_average": 8.4,
        "vote_count": 10000,
        "original_language": "en",
        "popularity": 50.0,
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
        "results": [
            {
                "id": i,
                "title": f"Movie {i}",
                "overview": "Test",
                "poster_path": f"/path{i}.jpg",
                "release_date": "2020-01-01",
                "vote_average": 8.0,
                "popularity": 50.0,
                "media_type": "movie"
            }
            for i in range(1, 21)
        ],
        "page": 1,
        "total_pages": 25,
        "total_results": 500
    }

    with patch('app.api.endpoints.media.tmdb_service.get_top_rated_movies',
               new_callable=AsyncMock, return_value=mock_response), \
            patch('app.api.endpoints.media.redis_service.get_top_movies',
                  new_callable=AsyncMock, return_value=None), \
            patch('app.api.endpoints.media.redis_service.set_top_movies',
                  new_callable=AsyncMock):
        response = await client.get("/api/v1/media/top/movies?page=1")

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 20


@pytest.mark.asyncio
async def test_search_empty_results(authenticated_client: tuple[AsyncClient, dict]):
    """Test search with no results"""
    client, tokens = authenticated_client

    mock_movie_response = {"results": [], "page": 1, "total_results": 0, "total_pages": 0}
    mock_tv_response = {"results": [], "page": 1, "total_results": 0, "total_pages": 0}

    with patch('app.api.endpoints.media.tmdb_service.search_movie',
               new_callable=AsyncMock, return_value=mock_movie_response), \
            patch('app.api.endpoints.media.tmdb_service.search_tv',
                  new_callable=AsyncMock, return_value=mock_tv_response):
        response = await client.get("/api/v1/media/search?query=xyznonexistent")

    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 0


@pytest.mark.asyncio
async def test_discover_media(authenticated_client: tuple[AsyncClient, dict]):
    """Test discover endpoint with filters"""
    client, tokens = authenticated_client

    mock_discover_response = {
        "results": [
            {
                "id": 550,
                "title": "Fight Club",
                "overview": "Test",
                "poster_path": "/path.jpg",
                "release_date": "1999-10-15",
                "vote_average": 8.4,
                "popularity": 50.0,
                "genre_ids": [18, 53],
                "media_type": "movie"
            }
        ],
        "page": 1,
        "total_pages": 1,
        "total_results": 1
    }

    with patch('app.api.endpoints.media.tmdb_service.discover_media',
               new_callable=AsyncMock, return_value=mock_discover_response):
        response = await client.get(
            "/api/v1/media/discover?genre_ids=18&min_year=1999&min_rating=8.0"
        )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0