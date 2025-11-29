from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlmodel import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Media, MediaType, UserMediaEntry, ListStatus


async def get_media_by_id(session: AsyncSession, media_id: UUID) -> Optional[Media]:
    """Get media by ID"""
    result = await session.execute(select(Media).where(Media.id == media_id))
    return result.scalar_one_or_none()


async def get_media_by_tmdb_id(
        session: AsyncSession,
        tmdb_id: int,
        media_type: MediaType
) -> Optional[Media]:
    """Get media by TMDB ID"""
    result = await session.execute(
        select(Media).where(
            Media.tmdb_id == tmdb_id,
            Media.media_type == media_type
        )
    )
    return result.scalar_one_or_none()


async def create_media(session: AsyncSession, **media_data) -> Media:
    """Create new media entry"""
    media = Media(**media_data)
    session.add(media)
    await session.commit()
    await session.refresh(media)
    return media


async def update_media(
        session: AsyncSession,
        media_id: UUID,
        **update_data
) -> Optional[Media]:
    """Update media information"""
    media = await get_media_by_id(session, media_id)
    if not media:
        return None

    for key, value in update_data.items():
        if hasattr(media, key) and value is not None:
            setattr(media, key, value)

    media.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(media)
    return media


async def search_media_by_title(
        session: AsyncSession,
        query: str,
        limit: int = 20,
        offset: int = 0
) -> List[Media]:
    """Search media by title"""
    result = await session.execute(
        select(Media)
        .where(
            or_(
                Media.title.ilike(f"%{query}%"),
                Media.original_title.ilike(f"%{query}%")
            )
        )
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_user_media_entry(
        session: AsyncSession,
        user_id: UUID,
        media_id: UUID
) -> Optional[UserMediaEntry]:
    """Get user's media entry"""
    result = await session.execute(
        select(UserMediaEntry).where(
            UserMediaEntry.user_id == user_id,
            UserMediaEntry.media_id == media_id
        )
    )
    return result.scalar_one_or_none()


async def create_user_media_entry(
        session: AsyncSession,
        user_id: UUID,
        media_id: UUID,
        **entry_data
) -> UserMediaEntry:
    """Create or update user media entry"""
    existing = await get_user_media_entry(session, user_id, media_id)
    if existing:
        for key, value in entry_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(existing)
        return existing

    entry = UserMediaEntry(
        user_id=user_id,
        media_id=media_id,
        **entry_data
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def update_user_media_entry(
        session: AsyncSession,
        user_id: UUID,
        media_id: UUID,
        **update_data
) -> Optional[UserMediaEntry]:
    """Update user's media entry"""
    entry = await get_user_media_entry(session, user_id, media_id)
    if not entry:
        return None

    for key, value in update_data.items():
        if hasattr(entry, key):
            setattr(entry, key, value)

    entry.updated_at = datetime.utcnow()

    # Set completed_at if status changed to completed (obviously)
    if update_data.get("list_status") == ListStatus.COMPLETED and not entry.completed_at:
        entry.completed_at = datetime.utcnow()

    await session.commit()
    await session.refresh(entry)
    return entry


async def get_user_library(
        session: AsyncSession,
        user_id: UUID,
        status: Optional[ListStatus] = None,
        limit: int = 50,
        offset: int = 0
) -> List[UserMediaEntry]:
    """Get user's media library"""
    query = select(UserMediaEntry).where(UserMediaEntry.user_id == user_id)

    if status:
        query = query.where(UserMediaEntry.list_status == status)

    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())


async def delete_user_media_entry(
        session: AsyncSession,
        user_id: UUID,
        media_id: UUID
) -> bool:
    """Delete user's media entry"""
    entry = await get_user_media_entry(session, user_id, media_id)
    if not entry:
        return False

    await session.delete(entry)
    await session.commit()
    return True


async def get_top_rated_completed(
        session: AsyncSession,
        user_id: UUID,
        min_score: float = 4.0,
        limit: int = 50,
        offset: int = 0
) -> List[UserMediaEntry]:
    """Get user's completed media with score >= min_score"""
    query = select(UserMediaEntry).where(
        UserMediaEntry.user_id == user_id,
        UserMediaEntry.list_status == ListStatus.COMPLETED,
        UserMediaEntry.score >= min_score
    ).order_by(UserMediaEntry.score.desc(), UserMediaEntry.completed_at.desc())

    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())
