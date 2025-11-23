"""
CRUD operations for OAuth users - Adapted to existing User model
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import User
from uuid import UUID, uuid4
from datetime import datetime


# ============================================================================
# GOOGLE OAuth
# ============================================================================

async def get_user_by_google_id(
        session: AsyncSession,
        google_id: str
) -> Optional[User]:
    """Récupérer un utilisateur par son Google ID"""
    result = await session.execute(
        select(User).where(User.google_id == google_id)
    )
    return result.scalar_one_or_none()


async def create_google_user(
        session: AsyncSession,
        email: str,
        username: str,
        google_id: str,
        avatar_url: Optional[str] = None
) -> User:
    """Créer un nouvel utilisateur Google OAuth"""
    user = User(
        id=uuid4(),
        username=username,
        email=email,
        google_id=google_id,
        avatar_url=avatar_url,
        hashed_password=None,  # Pas de mot de passe pour OAuth
        email_verified=True,
        is_active=True,
        is_public=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def link_google_to_existing_user(
        session: AsyncSession,
        user: User,
        google_id: str
) -> User:
    """Lier un compte Google à un utilisateur existant"""
    user.google_id = google_id
    user.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(user)

    return user


# ============================================================================
# APPLE OAuth
# ============================================================================

async def get_user_by_apple_id(
        session: AsyncSession,
        apple_id: str
) -> Optional[User]:
    """Récupérer un utilisateur par son Apple ID"""
    result = await session.execute(
        select(User).where(User.apple_id == apple_id)
    )
    return result.scalar_one_or_none()


async def create_apple_user(
        session: AsyncSession,
        email: str,
        username: str,
        apple_id: str,
        avatar_url: Optional[str] = None
) -> User:
    """Créer un nouvel utilisateur Apple OAuth"""
    user = User(
        id=uuid4(),
        username=username,
        email=email,
        apple_id=apple_id,
        avatar_url=avatar_url,
        hashed_password=None,
        is_active=True,
        is_public=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def link_apple_to_existing_user(
        session: AsyncSession,
        user: User,
        apple_id: str
) -> User:
    """Lier un compte Apple à un utilisateur existant"""
    user.apple_id = apple_id
    user.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(user)

    return user


# ============================================================================
# FACEBOOK OAuth (pour usage futur)
# ============================================================================

async def get_user_by_facebook_id(
        session: AsyncSession,
        facebook_id: str
) -> Optional[User]:
    """Récupérer un utilisateur par son Facebook ID"""
    result = await session.execute(
        select(User).where(User.facebook_id == facebook_id)
    )
    return result.scalar_one_or_none()


async def create_facebook_user(
        session: AsyncSession,
        email: str,
        username: str,
        facebook_id: str,
        avatar_url: Optional[str] = None
) -> User:
    """Créer un nouvel utilisateur Facebook OAuth"""
    user = User(
        id=uuid4(),
        username=username,
        email=email,
        facebook_id=facebook_id,
        avatar_url=avatar_url,
        hashed_password=None,
        is_active=True,
        is_public=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def link_facebook_to_existing_user(
        session: AsyncSession,
        user: User,
        facebook_id: str
) -> User:
    """Lier un compte Facebook à un utilisateur existant"""
    user.facebook_id = facebook_id
    user.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(user)

    return user