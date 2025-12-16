import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_get_current_user(authenticated_client: tuple[AsyncClient, dict]):
    """Test getting current user profile"""
    client, tokens = authenticated_client
    
    response = await client.get("/api/v1/users/me")
    
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "email" in data
    assert "username" in data
    assert "is_active" in data


@pytest.mark.asyncio
async def test_update_user_profile(authenticated_client: tuple[AsyncClient, dict]):
    """Test updating user profile"""
    client, tokens = authenticated_client
    
    update_data = {
        "username": "updated_user",
        "avatar_url": "https://example.com/avatar.jpg"
    }
    
    response = await client.put("/api/v1/users/me", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "updated_user"
    assert data["avatar_url"] == update_data["avatar_url"]


@pytest.mark.asyncio
async def test_update_user_duplicate_username(
    client: AsyncClient,
    authenticated_client: tuple[AsyncClient, dict],
    test_user_data: dict
):
    """Test updating username to one that already exists"""
    auth_client, tokens = authenticated_client
    
    # Create another user
    other_user = {
        "email": "other@example.com",
        "username": "otheruser",
        "password": "TestPass123",
        "birth_date": "1990-01-01"
    }
    await client.post("/api/v1/auth/register", json=other_user)
    
    # Try to update to existing username
    response = await auth_client.put(
        "/api/v1/users/me",
        json={"username": "otheruser"}
    )
    
    assert response.status_code == 400
    assert "already taken" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_user_without_auth(client: AsyncClient):
    """Test accessing protected endpoint without authentication"""
    response = await client.get("/api/v1/users/me")
    
    assert response.status_code == 401  # No credentials provided


@pytest.mark.asyncio
async def test_get_user_with_invalid_token(client: AsyncClient):
    """Test accessing endpoint with invalid token"""
    client.headers["Authorization"] = "Bearer invalid_token_here"
    
    response = await client.get("/api/v1/users/me")
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_password(authenticated_client: tuple[AsyncClient, dict]):
    """Test updating user password"""
    client, tokens = authenticated_client

    # Need to provide both current_password and new password
    current_password = "TestPass123"  # Password from test_user_data fixture
    new_password = "NewTestPass456"

    response = await client.put(
        "/api/v1/users/me",
        json={
            "current_password": current_password,
            "password": new_password
        }
    )

    assert response.status_code == 200

    # Verify can login with new password
    client.headers.pop("Authorization")
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "test@example.com",
            "password": new_password
        }
    )

    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_get_user_by_id(
    client: AsyncClient,
    authenticated_client: tuple[AsyncClient, dict]
):
    """Test getting user by ID"""
    auth_client, tokens = authenticated_client
    
    # Get own profile to get ID
    me_response = await auth_client.get("/api/v1/users/me")
    user_id = me_response.json()["id"]
    
    # Get user by ID
    response = await auth_client.get(f"/api/v1/users/{user_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert "email" not in data  # Public profile shouldn't expose email


@pytest.mark.asyncio
async def test_get_nonexistent_user(authenticated_client: tuple[AsyncClient, dict]):
    """Test getting user that doesn't exist"""
    client, tokens = authenticated_client
    
    fake_id = str(uuid4())
    response = await client.get(f"/api/v1/users/{fake_id}")
    
    assert response.status_code == 404