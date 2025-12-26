"""
Challenge avatar upload endpoint
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import User, Challenge
from app.core.deps import get_current_active_user
from app.crud.crud_challenge import get_challenge_by_id, update_challenge_avatar
from app.services.r2_storage import r2_storage
from app.schemas.challenge import ChallengeRead

router = APIRouter()


@router.post(
    "/{challenge_id}/avatar",
    response_model=ChallengeRead,
    summary="Télécharger un avatar de challenge"
)
async def upload_challenge_avatar(
    challenge_id: UUID,
    file: UploadFile = File(..., description="Image file (PNG, JPG, GIF, WEBP, max 5MB)"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Upload or update challenge avatar.
    Only challenge creator or admin can update.
    """
    # Get challenge
    challenge = await get_challenge_by_id(session, challenge_id)
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found"
        )

    # Check permissions
    if challenge.creator_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only challenge creator or admin can update avatar"
        )

    # Read file content
    content = await file.read()

    # Validate
    is_valid, message = r2_storage.validate_file(file.filename or "", len(content))
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    # Delete old avatar if exists
    if challenge.avatar_url:
        await r2_storage.delete_avatar(challenge.avatar_url)

    # Upload new avatar (use challenge_id as folder)
    success, result = await r2_storage.upload_challenge_avatar(
        challenge_id=challenge_id,
        file_content=content,
        original_filename=file.filename or "avatar.jpg",
        content_type=file.content_type or "image/jpeg"
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result
        )

    # Update challenge with new avatar URL
    updated_challenge = await update_challenge_avatar(
        session=session,
        challenge_id=challenge_id,
        avatar_url=result
    )

    return updated_challenge


@router.delete(
    "/{challenge_id}/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer l'avatar d'un challenge"
)
async def delete_challenge_avatar(
    challenge_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Supprime l'avatar d'un challenge (réservé au créateur ou admin)."""
    challenge = await get_challenge_by_id(session, challenge_id)
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found"
        )

    if challenge.creator_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only challenge creator or admin can delete avatar"
        )

    if challenge.avatar_url:
        await r2_storage.delete_avatar(challenge.avatar_url)
        await update_challenge_avatar(session, challenge_id, avatar_url=None)

    return None
