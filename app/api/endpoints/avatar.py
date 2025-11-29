"""
Avatar upload endpoint
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import User
from app.core.deps import get_current_active_user
from app.crud import crud_user
from app.services.r2_storage import r2_storage
from app.schemas.user import UserRead

router = APIRouter()


@router.post("/avatar", response_model=UserRead)
async def upload_avatar(
    file: UploadFile = File(..., description="Image file (PNG, JPG, GIF, WEBP, max 5MB)"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Upload or update user avatar.
    
    - Accepts: PNG, JPG, JPEG, GIF, WEBP
    - Max size: 5MB
    - Old avatar is automatically deleted
    """
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
    if current_user.avatar_url:
        await r2_storage.delete_avatar(current_user.avatar_url)
    
    # Upload new avatar
    success, result = await r2_storage.upload_avatar(
        user_id=current_user.id,
        file_content=content,
        original_filename=file.filename or "avatar.jpg",
        content_type=file.content_type or "image/jpeg"
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result
        )
    
    # Update user with new avatar URL
    updated_user = await crud_user.update_user(
        session=session,
        user_id=current_user.id,
        avatar_url=result
    )
    
    return updated_user


@router.delete("/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete current user's avatar"""
    if current_user.avatar_url:
        await r2_storage.delete_avatar(current_user.avatar_url)
        
        await crud_user.update_user(
            session=session,
            user_id=current_user.id,
            avatar_url=None
        )
    
    return None