# app/api/routes/users.py - version mise à jour
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.schemas.user import UserRead, UserUpdate, UserPublic
from app.crud import crud_user
from app.core.deps import get_current_active_user, get_current_admin_user
from app.db.models import User
from app.core.security import verify_password

router = APIRouter()


@router.get(
    "/search",
    response_model=list[UserPublic],
    summary="Rechercher de nouveaux amis"
)
async def search_new_friends(
        q: str = Query(..., min_length=3, description="Pseudo à rechercher"),
        page: int = Query(1, ge=1, description="Page number"),
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Recherche des utilisateurs par pseudo pour ajouter de nouveaux amis avec pagination."""
    PAGE_SIZE = 20
    offset = (page - 1) * PAGE_SIZE

    users = await crud_user.search_users_friendship_by_username(
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


@router.get(
    "/admin/search",
    response_model=list[UserRead],
    summary="Rechercher des utilisateurs (admin)"
)
async def search_user_admin(
        query: str,
        is_active: bool | None = None,
        session: AsyncSession = Depends(get_session),
):
    """Recherche globale d'utilisateurs avec filtre optionnel sur le statut actif (réservé admin)."""
    return await crud_user.search_users_by_query(
        query=query,
        session=session,
        is_active=is_active,
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Récupérer mon profil"
)
async def get_current_user_profile(
        current_user: User = Depends(get_current_active_user)
):
    """Récupère le profil complet de l'utilisateur connecté."""
    return current_user


@router.put(
    "/me",
    response_model=UserRead,
    summary="Mettre à jour mon profil"
)
async def update_current_user_profile(
        user_update: UserUpdate,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Update current user's profile
    Can update: email, username, password, avatar_url, birth_date, social_links

    Note: Pour changer le mot de passe, current_password et password doivent être fournis
    """
    # Vérification email
    if user_update.email and user_update.email != current_user.email:
        existing_user = await crud_user.get_user_by_email(session, user_update.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )

    # Vérification username
    if user_update.username and user_update.username != current_user.username:
        existing_user = await crud_user.get_user_by_username(session, user_update.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

    # Gestion du changement de mot de passe
    if user_update.password:
        # Vérifier que current_password est fourni
        if not user_update.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to change password"
            )

        # Vérifier que le mot de passe actuel est correct
        if not verify_password(user_update.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )

    # Préparer les données de mise à jour
    update_data = user_update.model_dump(exclude_unset=True)

    # Retirer current_password des données de mise à jour (ne doit pas être stocké)
    if 'current_password' in update_data:
        del update_data['current_password']

    # Mettre à jour l'utilisateur
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


@router.get(
    "/{user_id}",
    response_model=UserPublic,
    summary="Récupérer un utilisateur par ID"
)
async def get_user_by_id(
        user_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Récupère les informations publiques d'un utilisateur par son identifiant."""
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


@router.get(
    "/username/{username}",
    response_model=UserPublic,
    summary="Récupérer un utilisateur par username"
)
async def get_user_by_username(
        username: str,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_active_user)
):
    """Récupère les informations publiques d'un utilisateur par son pseudo."""
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


@router.post(
    "/{user_id}/deactivate",
    response_model=UserRead,
    summary="Désactiver un utilisateur (admin)"
)
async def deactivate_user(
        user_id: UUID,
        session: AsyncSession = Depends(get_session),
        admin_user: User = Depends(get_current_admin_user)
):
    """Désactive un compte utilisateur (réservé admin)."""
    user = await crud_user.get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    deactivated_user = await crud_user.deactivate_user(session, user_id)
    return deactivated_user


@router.post(
    "/{user_id}/activate",
    response_model=UserRead,
    summary="Activer un utilisateur (admin)"
)
async def activate_user(
        user_id: UUID,
        session: AsyncSession = Depends(get_session),
        admin_user: User = Depends(get_current_admin_user)
):
    """Active un compte utilisateur désactivé (réservé admin)."""
    user = await crud_user.get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    activated_user = await crud_user.activate_user(session, user_id)
    return activated_user


@router.get(
    "/",
    response_model=list[UserRead],
    summary="Lister tous les utilisateurs"
)
async def get_all_users(
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        is_active: bool | None = None,
        session: AsyncSession = Depends(get_session)
):
    """Récupère la liste de tous les utilisateurs avec filtres optionnels (recherche, statut actif) et pagination."""
    users = await crud_user.get_users_list(
        session=session,
        skip=skip,
        limit=limit,
        search=search,
        is_active=is_active
    )

    return users
