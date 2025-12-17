from datetime import datetime, date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, Review
from app.core.security import get_password_hash, verify_password
from sqlalchemy import and_

from sqlalchemy import select, and_, or_

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
        birth_date: date,
        is_public: bool = True,
        avatar_url: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
) -> User:
    """Create a new user"""
    user = User(
        email=email,
        username=username,
        hashed_password=get_password_hash(password) if password else None,
        birth_date=birth_date,
        is_public=is_public,
        avatar_url=avatar_url,
        **kwargs
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(
        session: AsyncSession,
        user_id: UUID,
        allow_none: bool = False,  # Nouveau paramètre
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
        if hasattr(user, key):
            # Permettre None si allow_none=True OU si value n'est pas None
            if allow_none or value is not None:
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
    user = await get_user_by_id(session, user_id)
    if not user:
        return None

    if user.is_admin:
        raise HTTPException(400, "Admin accounts cannot be deactivated")

    user.is_active = False

    await session.execute(
        Review.__table__.update()
        .where(Review.user_id == user_id)
        .values(is_visible=False, updated_at=datetime.utcnow())
    )

    await session.commit()
    await session.refresh(user)
    return user


async def activate_user(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Activate user account"""
    user = await get_user_by_id(session, user_id)
    if not user:
        return None

    user.is_active = True

    await session.execute(
        Review.__table__.update()
        .where(Review.user_id == user_id)
        .values(is_visible=True, updated_at=datetime.utcnow())
    )

    await session.commit()
    await session.refresh(user)
    return user


async def get_users_list(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
) -> list[User]:
    query = select(User).where(User.is_admin == False)

    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (User.username.ilike(search_pattern)) |
            (User.email.ilike(search_pattern))
        )
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    query = query.offset(skip).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()


async def get_user_by_verification_token(
        session: AsyncSession,
        token: str
) -> Optional[User]:
    """Récupère un utilisateur par son token de vérification"""
    result = await session.execute(
        select(User).where(User.email_verification_token == token)
    )
    return result.scalar_one_or_none()


# rechercher un user (principalement pour trouver pour l'admin)
async def search_users_by_query(
    query: str,
    session: AsyncSession,
    is_active: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[User]:

    stmt = select(User).where(
        and_(
            or_(
                User.username.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%"),
            ),
            User.is_admin == False,
        )
    )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    stmt = stmt.offset(offset).limit(limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_users_friendship_by_username(
        session: AsyncSession,
        username_query: str,
        current_user_id: UUID,
        limit: int = 20,
        offset: int = 0,
) -> list[User]:
    """Recherche des utilisateurs actifs par pseudo, excluant les amis existants"""
    search_pattern = f"%{username_query.lower()}%"

    # Alias pour la table Friendship (si tu as un modèle)
    # Sinon, utilise directement la table
    from app.db.models import Friendship  # Ajuste selon ton import

    # Sous-requête pour vérifier l'existence d'une amitié
    # On vérifie les deux directions: (current_user, user) ET (user, current_user)
    friendship_exists = select(Friendship.user_one_id).where(
        or_(
            and_(
                Friendship.user_one_id == current_user_id,
                Friendship.user_two_id == User.id
            ),
            and_(
                Friendship.user_two_id == current_user_id,
                Friendship.user_one_id == User.id
            )
        )
    ).exists()

    # Requête principale
    query = (
        select(User)
        .where(
            and_(
                User.username.ilike(search_pattern),
                User.id != current_user_id,
                User.is_active == True,
                User.is_admin == False,
                ~friendship_exists  # Exclut si l'amitié existe
            )
        )
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(query)
    return list(result.scalars().all())

async def get_user_by_password_reset_token(
    session: AsyncSession,
    token: str
) -> Optional[User]:
    """Récupère un utilisateur par son token de réinitialisation"""
    result = await session.execute(
        select(User).where(User.password_reset_token == token)
    )
    return result.scalar_one_or_none()