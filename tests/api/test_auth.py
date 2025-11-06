import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, test_user_data: dict):
    """Test successful user registration"""
    response = await client.post(
        "/api/v1/auth/register",
        json=test_user_data
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert data["username"] == test_user_data["username"]
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user_data: dict):
    """Test registration with duplicate email"""
    # First registration
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    # Try to register again with same email
    response = await client.post(
        "/api/v1/auth/register",
        json=test_user_data
    )
    
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient, test_user_data: dict):
    """Test registration with duplicate username"""
    # First registration
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    # Try to register with same username but different email
    duplicate_data = test_user_data.copy()
    duplicate_data["email"] = "another@example.com"
    
    response = await client.post(
        "/api/v1/auth/register",
        json=duplicate_data
    )
    
    assert response.status_code == 400
    assert "Username already taken" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient, test_user_data: dict):
    """Test registration with weak password"""
    weak_data = test_user_data.copy()
    weak_data["password"] = "weak"
    
    response = await client.post(
        "/api/v1/auth/register",
        json=weak_data
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user_data: dict):
    """Test successful login"""
    # Register first
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    # Login with email
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": test_user_data["email"],
            "password": test_user_data["password"]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_with_username(client: AsyncClient, test_user_data: dict):
    """Test login with username"""
    # Register first
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    # Login with username
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": test_user_data["username"],
            "password": test_user_data["password"]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user_data: dict):
    """Test login with wrong password"""
    # Register first
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    # Login with wrong password
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": test_user_data["email"],
            "password": "WrongPassword123"
        }
    )
    
    assert response.status_code == 401
    assert "Incorrect" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with nonexistent user"""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "nonexistent@example.com",
            "password": "SomePassword123"
        }
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, test_user_data: dict):
    """Test token refresh"""
    # Register and login
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": test_user_data["email"],
            "password": test_user_data["password"]
        }
    )
    
    tokens = login_response.json()
    
    # Wait a bit to ensure different timestamps
    import asyncio
    await asyncio.sleep(1)
    
    # Refresh token
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]}
    )
    
    assert response.status_code == 200
    new_tokens = response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    # Tokens should be different after waiting
    assert new_tokens["access_token"] != tokens["access_token"]