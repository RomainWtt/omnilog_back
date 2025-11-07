from typing import Optional
from uuid import UUID
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from app.core.security import get_password_hash, verify_password


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Get user by ID"""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Get user by email"""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """Get user by username"""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email_or_username(
    session: AsyncSession, 
    identifier: str
) -> Optional[User]:
    """Get user by email or username"""
    result = await session.execute(
        select(User).where(
            (User.email == identifier) | (User.username == identifier)
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_oauth_id(
    session: AsyncSession,
    provider: str,
    oauth_id: str
) -> Optional[User]:
    """Get user by OAuth provider ID"""
    if provider == "google":
        result = await session.execute(select(User).where(User.google_id == oauth_id))
    elif provider == "facebook":
        result = await session.execute(select(User).where(User.facebook_id == oauth_id))
    elif provider == "apple":
        result = await session.execute(select(User).where(User.apple_id == oauth_id))
    else:
        return None
    
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    email: str,
    username: str,
    password: Optional[str] = None,
    **kwargs
) -> User:
    """Create a new user"""
    user = User(
        email=email,
        username=username,
        hashed_password=get_password_hash(password) if password else None,
        **kwargs
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(
    session: AsyncSession,
    user_id: UUID,
    **update_data
) -> Optional[User]:
    """Update user information"""
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    
    # If password is being updated, hash it
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    for key, value in update_data.items():
        if hasattr(user, key) and value is not None:
            setattr(user, key, value)
    
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession,
    identifier: str,
    password: str
) -> Optional[User]:
    """Authenticate user with email/username and password"""
    user = await get_user_by_email_or_username(session, identifier)
    if not user:
        return None
    if not user.hashed_password:
        return None  # For OAuth user
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


async def deactivate_user(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Deactivate user account"""
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    
    user.is_active = False
    await session.commit()
    await session.refresh(user)
    return user


async def activate_user(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Activate user account"""
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    
    user.is_active = True
    await session.commit()
    await session.refresh(user)
    return user