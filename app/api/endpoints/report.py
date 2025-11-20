from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.core.deps import get_current_active_user
from app.crud import crud_report
from app.db.session import get_session
from app.schemas.report import ReviewReportCreate, ReviewReportRead

router = APIRouter()

@router.post("/", response_model=ReviewReportRead)
async def report_review(
    payload: ReviewReportCreate,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_active_user)
):
    report = await crud_report.create_report(
        session=session,
        reporter_id=current_user.id,
        review_id=payload.review_id,
        reason=payload.reason
    )
    return report



@router.get("/review_reports/", response_model=list[ReviewReportRead])
async def list_reports_for_review(
    review_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_active_user)
):
    return await crud_report.get_reports_for_review(session, review_id)

