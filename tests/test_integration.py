import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_user_journey(client: AsyncClient, session):
    """Test complete user journey from registration to tracking media - FIXED"""
    
    # 1. Register
    user_data = {
        "email": "journey@example.com",
        "username": "journeyuser",
        "password": "TestPass123",
        "birth_date": "1990-01-01"
    }
    register_response = await client.post("/api/v1/auth/register", json=user_data)
    assert register_response.status_code == 201
    
    # 2. Login
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": user_data["email"],
            "password": user_data["password"]
        }
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    client.headers["Authorization"] = f"Bearer {tokens['access_token']}"
    
    # 3. Get profile
    profile_response = await client.get("/api/v1/users/me")
    assert profile_response.status_code == 200
    user = profile_response.json()
    
    # 4. Update profile
    update_response = await client.put(
        "/api/v1/users/me",
        json={"username": "updated_journey"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["username"] == "updated_journey"
    
    # 5. Create test media directly
    from app.db.models import Media, MediaType
    from datetime import date
    
    media = Media(
        tmdb_id=550,
        media_type=MediaType.MOVIE,
        title="Fight Club",
        overview="Test",
        poster_path="/test.jpg",
        release_date=date(1999, 10, 15)
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)
    
    # 6. Add to library - REMOVED progress field
    library_response = await client.post(
        "/api/v1/library/",
        json={
            "media_id": str(media.id),
            "list_status": "watching",
            "timecode": 0  # Use timecode instead of progress
        }
    )
    assert library_response.status_code == 201, f"Body: {library_response.text}"
    
    # 7. Update progress - REMOVED progress field
    progress_response = await client.put(
        f"/api/v1/library/{media.id}/progress",
        json={"timecode": 3600}  # Only timecode, no progress percentage
    )
    assert progress_response.status_code == 200


@pytest.mark.asyncio
async def test_authentication_flow(client: AsyncClient):
    """Test complete authentication flow"""
    
    # Register
    user_data = {
        "email": "auth@example.com",
        "username": "authuser",
        "password": "TestPass123",
        "birth_date": "1990-01-01"
    }
    await client.post("/api/v1/auth/register", json=user_data)
    
    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user_data["email"], "password": user_data["password"]}
    )
    tokens = login_response.json()
    
    # Access protected endpoint
    client.headers["Authorization"] = f"Bearer {tokens['access_token']}"
    me_response = await client.get("/api/v1/users/me")
    assert me_response.status_code == 200
    
    # Refresh token
    import asyncio
    await asyncio.sleep(1)  # Ensure different timestamp
    
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    
    # Use new access token
    client.headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
    me_response2 = await client.get("/api/v1/users/me")
    assert me_response2.status_code == 200


@pytest.mark.asyncio
async def test_error_handling(client: AsyncClient):
    """Test various error scenarios"""
    
    # 1. Invalid email format
    response = await client.post("/api/v1/auth/register", json={
        "email": "not-an-email",
        "username": "test",
        "password": "TestPass123",
        "birth_date": "1990-01-01"
    })
    assert response.status_code == 422
    
    # 2. Weak password
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "username": "test",
        "password": "weak",
        "birth_date": "1990-01-01"
    })
    assert response.status_code == 422
    
    # 3. Invalid token
    client.headers["Authorization"] = "Bearer invalid_token"
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    
    # 4. Missing required fields
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_database_constraints(client: AsyncClient, session):
    """Test database constraints and integrity"""
    
    # Create user
    user_data = {
        "email": "constraint@example.com",
        "username": "constraintuser",
        "password": "TestPass123",
        "birth_date": "1990-01-01"
    }
    await client.post("/api/v1/auth/register", json=user_data)
    
    # Try to create duplicate email
    duplicate_email = user_data.copy()
    duplicate_email["username"] = "different"
    response = await client.post("/api/v1/auth/register", json=duplicate_email)
    assert response.status_code == 400
    
    # Try to create duplicate username
    duplicate_username = user_data.copy()
    duplicate_username["email"] = "different@example.com"
    response = await client.post("/api/v1/auth/register", json=duplicate_username)
    assert response.status_code == 400
