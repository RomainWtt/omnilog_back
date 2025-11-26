from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.schemas.user import UserRead, UserUpdate, UserPublic
from app.crud import crud_user
from app.core.deps import get_current_active_user, get_current_admin_user
from app.db.models import User

router = APIRouter()


@router.get("/search", response_model=list[UserPublic])
async def search_new_friends(
        q: str = Query(..., min_length=3, description="Pseudo à rechercher"),
        page: int = Query(1, ge=1, description="Page number"),
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    PAGE_SIZE = 20
    offset = (page - 1) * PAGE_SIZE

    users = await crud_user.search_users_by_username(
        session=session,
        username_query=q.strip(),
        current_user_id=current_user.id,
        limit=PAGE_SIZE,
        offset=offset,
    )

    return [
        UserPublic.model_validate({
            "id": u.id,
            "username": u.username,
            "avatar_url": u.avatar_url,
            "social_links": u.social_links,
            "is_public": u.is_public
        })
        for u in users
    ]


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
        current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's profile
    """
    return current_user


@router.put("/me", response_model=UserRead)
async def update_current_user_profile(
        user_update: UserUpdate,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Update current user's profile
    
    Can update: email, username, password, avatar_url, birth_date, social_links
    """
    if user_update.email and user_update.email != current_user.email:
        existing_user = await crud_user.get_user_by_email(session, user_update.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )

    if user_update.username and user_update.username != current_user.username:
        existing_user = await crud_user.get_user_by_username(session, user_update.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

    update_data = user_update.model_dump(exclude_unset=True)
    updated_user = await crud_user.update_user(
        session=session,
        user_id=current_user.id,
        **update_data
    )

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return updated_user


@router.get("/{user_id}", response_model=UserPublic)
async def get_user_by_id(
        user_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """
    Get public information about a user by ID
    """
    user = await crud_user.get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.get("/username/{username}", response_model=UserPublic)
async def get_user_by_username(
        username: str,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """
    Get public information about a user by username
    """
    user = await crud_user.get_user_by_username(session, username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.post("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
        user_id: UUID,
        session: AsyncSession = Depends(get_session),
        admin_user: User = Depends(get_current_admin_user)
):
    """
    Deactivate a user account (Admin only)
    """
    user = await crud_user.get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate admin users"
        )

    deactivated_user = await crud_user.deactivate_user(session, user_id)
    return deactivated_user


@router.post("/{user_id}/activate", response_model=UserRead)
async def activate_user(
        user_id: UUID,
        session: AsyncSession = Depends(get_session),
        admin_user: User = Depends(get_current_admin_user)
):
    """
    Activate a user account (Admin only)
    """
    user = await crud_user.get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    activated_user = await crud_user.activate_user(session, user_id)
    return activated_user


@router.get("/", response_model=list[UserRead])
async def get_all_users(
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        is_active: bool | None = None,
        session: AsyncSession = Depends(get_session)
):
    users = await crud_user.get_all_users(
        session=session,
        skip=skip,
        limit=limit,
        search=search,
        is_active=is_active
    )

    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No users found")

    return users


