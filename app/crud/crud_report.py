from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.api.endpoints.review import hide_review
from app.crud.crud_user import get_user_by_id
from app.db.models import ReviewReport, Review
from app.schemas.report import ReviewReportRead


async def get_report_by_id(session: AsyncSession, report_id: UUID) -> Optional[ReviewReport]:
    result = await session.execute(select(ReviewReport).where(ReviewReport.id == report_id))
    return result.scalar_one_or_none()


async def get_reports_by_review_id(session: AsyncSession, review_id: UUID) -> List[ReviewReport]:
    result = await session.execute(select(ReviewReport).where(ReviewReport.review_id == review_id))
    return list(result.scalars().all())


"""
async def get_all_reports(session: AsyncSession) -> List[ReviewReport]:
    result = await session.execute(select(ReviewReport).order_by(ReviewReport.created_at.desc()))
    return list(result.scalars().all())
"""


async def get_all_reports(session: AsyncSession) -> list[ReviewReportRead]:
    reports_result = await session.execute(
        select(ReviewReport).order_by(ReviewReport.created_at.desc())
    )
    reports = reports_result.scalars().all()

    detailed_reports = []

    for report in reports:
        reporter = await get_user_by_id(session, report.reporter_id)
        reported_user = await get_user_by_id(session, report.reported_user_id)

        result = await session.execute(
            select(Review)
            .where(Review.id == report.review_id)
            .options(selectinload(Review.media))
        )
        review = result.scalar_one_or_none()
        media_name = review.media.title
        content = review.content

        detailed_reports.append(
            ReviewReportRead(
                id=report.id,
                reporter_id=report.reporter_id,
                reporter_username=reporter.username,
                reported_user_id=report.reported_user_id,
                reported_user_username=reported_user.username,
                review_id=report.review_id,
                reason=report.reason,
                created_at=report.created_at,
                media=media_name,
                content=review.content
            )
        )
    return detailed_reports


async def approve_report_by_id(session: AsyncSession, report_id: UUID) -> bool:
    report = await get_report_by_id(session, report_id)
    if not report:
        return False

    await delete_report(session, report_id)
    return True


async def reject_report_by_id(session: AsyncSession, report_id: UUID) -> bool:
    return await delete_report(session, report_id)


async def create_report(
        session: AsyncSession,
        reporter_id: UUID,
        review_id: UUID,
        reason: str
) -> ReviewReport:
    """Create a new report"""

    # Vérifier que la review existe
    result = await session.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(404, "Review not found")

    # Interdire le report de sa propre review
    if review.user_id == reporter_id:
        raise HTTPException(400, "Cannot report your own review")

    # Vérifier doublon
    result = await session.execute(
        select(ReviewReport).where(
            ReviewReport.reporter_id == reporter_id,
            ReviewReport.review_id == review_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "You have already reported this review")

    report = ReviewReport(
        id=uuid4(),
        reporter_id=reporter_id,
        review_id=review_id,
        reported_user_id=review.user_id,
        reason=reason,
        created_at=datetime.utcnow()
    )

    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def update_report(
        session: AsyncSession,
        report_id: UUID,
        **update_data
) -> Optional[ReviewReport]:
    report = await get_report_by_id(session, report_id)
    if not report:
        return None

    for key, value in update_data.items():
        if hasattr(report, key) and value is not None:
            setattr(report, key, value)

    report.created_at = datetime.utcnow()
    await session.commit()
    await session.refresh(report)
    return report


async def delete_report(session: AsyncSession, report_id: UUID) -> bool:  # TODO a garer ?
    report = await get_report_by_id(session, report_id)
    if not report:
        return False

    await session.delete(report)
    await session.commit()
    return True
