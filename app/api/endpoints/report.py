from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.core.deps import get_current_active_user
from app.crud import crud_report
from app.crud import crud_review
from app.crud.crud_report import approve_report_by_id, reject_report_by_id
from app.crud.crud_review import toggle_is_report
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
    await crud_review.toggle_is_report(session, payload.review_id)
    return report


@router.get("/", response_model=list[ReviewReportRead])
async def list_reports_for_review(
        review_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user=Depends(get_current_active_user)
):
    return await crud_report.get_reports_by_review_id(session, review_id)


@router.get("/all", response_model=list[ReviewReportRead])
async def list_all_reports(
        session: AsyncSession = Depends(get_session),
        current_user=Depends(get_current_active_user)
):
    return await crud_report.get_all_reports(session)


@router.post("/{report_id}/approve")
async def approve_report(
        report_id: UUID,
        session: AsyncSession = Depends(get_session)
):
    id_review = await approve_report_by_id(session, report_id)
    await crud_review.toggle_is_report(session, id_review)
    return await crud_review.delete_review(session, id_review)


@router.post("/{report_id}/reject")
async def reject_report(
        report_id: UUID,
        session: AsyncSession = Depends(get_session)
):
    return await reject_report_by_id(session, report_id)


"""
@router.get("/by_ids", response_model=List[ReviewReportRead])
async def list_reports_for_reviews_by_id(
    review_ids: List[UUID] = Query(..., description="Liste des review_id à vérifier"),
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_active_user)
):
    if not review_ids:
        return []

    result = await session.execute(
        select(ReviewReport).where(ReviewReport.review_id.in_(review_ids))
    )
    reports = result.scalars().all()
    return reports
"""
