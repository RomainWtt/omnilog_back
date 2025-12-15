from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.crud import crud_activity
from app.db.models import User
from app.db.session import get_session

router = APIRouter()


@router.delete("/{activity_id}")
async def remove_activity_challenge(
    activity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    success = await crud_activity.delete_activity_by_id(session, activity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Activité impossible à supprimer")
    return None