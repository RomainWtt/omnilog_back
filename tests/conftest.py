import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.session import get_session
from app.core.config import settings
from uuid import uuid4
from app.db.models import User
from app.core.security import get_password_hash

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True
)

# Create test session factory
TestSessionLocal = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with mocked Redis"""
    async def override_get_session():
        yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    # Mock Redis service to avoid connection errors in tests
    with patch('app.services.redis_service.redis_service.get_top_movies', 
               new_callable=AsyncMock, return_value=None):
        with patch('app.services.redis_service.redis_service.set_top_movies',
                   new_callable=AsyncMock, return_value=True):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Test user data"""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPass123",
        "birth_date": "1990-01-01"
    }


@pytest.fixture
async def authenticated_client(
    client: AsyncClient,
    test_user_data: dict
) -> AsyncGenerator[tuple[AsyncClient, dict], None]:
    """Create authenticated client"""
    # Register user
    response = await client.post(
        "/api/v1/auth/register",
        json=test_user_data
    )
    assert response.status_code == 201
    
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": test_user_data["email"],
            "password": test_user_data["password"]
        }
    )
    assert response.status_code == 200
    tokens = response.json()
    
    # Set authorization header
    client.headers["Authorization"] = f"Bearer {tokens['access_token']}"
    
    yield client, tokens

@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Crée un utilisateur de test pour les notifications"""
    user = User(
        id=uuid4(),
        username="notifuser",
        email="notif@example.com",
        hashed_password=get_password_hash("TestPass123"),
        is_active=True,
        email_verified=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def test_user_2(session: AsyncSession) -> User:
    """Crée un deuxième utilisateur de test pour les notifications"""
    user = User(
        id=uuid4(),
        username="notifuser2",
        email="notif2@example.com",
        hashed_password=get_password_hash("TestPass123"),
        is_active=True,
        email_verified=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def test_user_3(session: AsyncSession) -> User:
    """Crée un troisième utilisateur de test pour les notifications"""
    user = User(
        id=uuid4(),
        username="notifuser3",
        email="notif3@example.com",
        hashed_password=get_password_hash("TestPass123"),
        is_active=True,
        email_verified=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
